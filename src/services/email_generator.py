import json
import os
import sys
import time
from datetime import datetime

from openai import OpenAI, APIError

from models.partner import Company, Partner, OutreachEmail, EmailStatus


SYSTEM_PROMPT = (
    "You are an expert partnership manager who writes concise, warm, "
    "highly personalized outreach emails. You never use filler phrases like "
    "'I hope this email finds you well.' You write as a human, not a bot."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class EmailGenerationError(Exception):
    pass


class EmailGenerator:
    """
    Generates personalized outreach emails via the OpenAI-compatible API.

    Works with:
    - OpenAI directly        OPENAI_BASE_URL=https://api.openai.com/v1
    - OpenRouter / Nvidia    OPENAI_BASE_URL=https://openrouter.ai/api/v1  (default)
    - Ollama locally         OPENAI_BASE_URL=http://localhost:11434/v1
    """

    MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    MAX_TOKENS = 4096   # generous — truncation was the main failure cause
    TEMPERATURE = 0.8
    MAX_RETRIES = 3
    RETRY_DELAY = 2     # seconds between retries (doubles each attempt)

    def __init__(self, company: Company, api_key: str | None = None, model: str | None = None):
        self.company = company
        self.model = model or os.environ.get("OPENAI_MODEL", self.MODEL)

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            print("[error] Set OPENAI_API_KEY environment variable.")
            sys.exit(1)

        base_url = os.environ.get("OPENAI_BASE_URL", OPENROUTER_BASE_URL)
        self.client = OpenAI(api_key=key, base_url=base_url)

    def _build_prompt(self, partner: Partner) -> str:
        return (
            f"Sender: {self.company.sender_name}, {self.company.sender_role} "
            f"at {self.company.name} ({self.company.sender_email})\n"
            f"Value proposition: {self.company.value_proposition}\n\n"
            f"Target partner:\n"
            f"  Name:     {partner.name}\n"
            f"  Email:    {partner.email}\n"
            f"  Industry: {partner.industry}\n"
            f"  Website:  {partner.website or 'N/A'}\n\n"
            "Write a SHORT partnership outreach email — 80 words maximum in the body.\n"
            "- Be specific to their industry\n"
            "- End with one clear call-to-action\n"
            "- Sign off as the sender\n\n"
            "IMPORTANT: Respond with ONLY a JSON object. No preamble, no commentary.\n"
            "Keep the body under 80 words so the response stays short.\n"
            'Format: {"subject": "...", "body": "..."}'
        )

    def _extract_content(self, response) -> str:
        choice = response.choices[0]
        message = choice.message

        content = message.content or ""

        if not content and hasattr(message, "reasoning_content"):
            content = getattr(message, "reasoning_content", "") or ""

        if not content and hasattr(message, "model_extra") and message.model_extra:
            content = (
                message.model_extra.get("content")
                or message.model_extra.get("reasoning_content")
                or ""
            )

        # Strip <think> reasoning blocks emitted by reasoning models
        if "</think>" in content:
            content = content.split("</think>", 1)[-1].strip()

        return content

    def _parse_response(self, raw: str) -> dict:
        if not raw.strip():
            raise EmailGenerationError("empty_response")

        cleaned = raw.strip()

        # Strip markdown code fences
        if "```" in cleaned:
            for part in cleaned.split("```"):
                part = part.lstrip("json").strip()
                if part.startswith("{"):
                    cleaned = part
                    break

        # Extract the outermost { ... } block
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Truncated JSON — signal for retry
            raise EmailGenerationError(f"truncated_json: {e}\nRaw:\n{raw}")

        # Flexible key matching — model may use different casing/names
        subject = (
            data.get("subject") or data.get("Subject") or data.get("email_subject")
            or data.get("subjectLine")
            or next((v for k, v in data.items() if "subject" in k.lower()), None)
        )
        body = (
            data.get("body") or data.get("Body") or data.get("email_body")
            or data.get("emailBody") or data.get("content") or data.get("message")
            or next((v for k, v in data.items() if any(
                w in k.lower() for w in ("body", "content", "message", "text")
            )), None)
        )

        if not subject or not body:
            raise EmailGenerationError(
                f"missing_keys — got: {list(data.keys())}\nRaw:\n{raw}"
            )

        return {"subject": subject, "body": body}

    def generate(self, partner: Partner) -> OutreachEmail:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.MAX_TOKENS,
                    temperature=self.TEMPERATURE,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": self._build_prompt(partner)},
                    ],
                )
                raw = self._extract_content(response)
                data = self._parse_response(raw)

                partner.status = EmailStatus.GENERATED
                partner.generated_at = datetime.now()
                return OutreachEmail(
                    partner=partner,
                    subject=data["subject"],
                    body=data["body"],
                )

            except EmailGenerationError as e:
                last_error = e
                msg = str(e)
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY * (2 ** (attempt - 1))
                    print(f"\n  [retry {attempt}/{self.MAX_RETRIES}] {msg[:80]}… waiting {delay}s")
                    time.sleep(delay)
                continue

            except APIError as e:
                raise EmailGenerationError(f"OpenAI API error: {e}") from e

        raise EmailGenerationError(
            f"Failed after {self.MAX_RETRIES} attempts.\nLast error: {last_error}"
        )