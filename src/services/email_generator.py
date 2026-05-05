import json
import os
import sys
from datetime import datetime

from openai import OpenAI, APIError

from models.partner import Company, Partner, OutreachEmail, EmailStatus


SYSTEM_PROMPT = (
    "You are an expert partnership manager who writes concise, warm, "
    "highly personalized outreach emails. You never use filler phrases like "
    "'I hope this email finds you well.' You write as a human, not a bot."
)


class EmailGenerationError(Exception):
    pass


class EmailGenerator:
    """Generates personalized outreach emails via the OpenAI API."""

    MODEL = "gpt-4o"
    MAX_TOKENS = 600
    TEMPERATURE = 0.8

    def __init__(self, company: Company, api_key: str | None = None):
        self.company = company
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            print("[error] Set OPENAI_API_KEY environment variable.")
            sys.exit(1)
        self.client = OpenAI(api_key=key)

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
            "Write a short, warm, personalized partnership outreach email.\n"
            "- Under 150 words\n"
            "- Reference their specific industry with a concrete observation\n"
            "- End with a clear, low-friction call-to-action\n"
            "- Sign off as the sender\n\n"
            "Respond ONLY with valid JSON — no markdown, no backticks:\n"
            '{"subject": "...", "body": "..."}'
        )

    def _parse_response(self, raw: str) -> dict:
        cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise EmailGenerationError(f"Failed to parse model response as JSON: {e}\nRaw: {raw}")

    def generate(self, partner: Partner) -> OutreachEmail:
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": self._build_prompt(partner)},
                ],
            )
            raw = response.choices[0].message.content or ""
            data = self._parse_response(raw)
            partner.status = EmailStatus.GENERATED
            partner.generated_at = datetime.now()
            return OutreachEmail(
                partner=partner,
                subject=data["subject"],
                body=data["body"],
            )

        except EmailGenerationError:
            raise
        except APIError as e:
            raise EmailGenerationError(f"OpenAI API error: {e}") from e
