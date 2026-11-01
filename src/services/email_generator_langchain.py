import json
import os
import sys
import time
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from models.partner import Company, Partner, OutreachEmail, EmailStatus


# ── Pydantic schema for structured output ────────────────────────────────────

class EmailOutput(BaseModel):
    """Structured email output from LLM."""
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text")


# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert partnership manager who writes concise, warm, "
    "highly personalized outreach emails. You never use filler phrases like "
    "'I hope this email finds you well.' You write as a human, not a bot."
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class EmailGenerationError(Exception):
    pass


class LangChainEmailGenerator:
    """
    Generates personalized outreach emails using LangChain + OpenAI-compatible API.

    Benefits over raw OpenAI client:
    - Automatic prompt templating and variable injection
    - Structured output parsing with retry logic built-in
    - Cleaner error handling via LangChain abstractions
    """

    MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
    MAX_TOKENS = 4096
    TEMPERATURE = 0.8
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, company: Company, api_key: str | None = None, model: str | None = None):
        self.company = company
        self.model = model or os.environ.get("OPENAI_MODEL", self.MODEL)

        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            print("[error] Set OPENAI_API_KEY environment variable.")
            sys.exit(1)

        base_url = os.environ.get("OPENAI_BASE_URL", OPENROUTER_BASE_URL)

        # Initialize LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.TEMPERATURE,
            max_tokens=self.MAX_TOKENS,
            openai_api_key=key,
            openai_api_base=base_url,
        )

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("user", self._get_user_template()),
        ])

        # JSON output parser with Pydantic schema
        self.parser = JsonOutputParser(pydantic_object=EmailOutput)

        # Build LangChain chain: prompt → LLM → parser
        self.chain = self.prompt | self.llm | self.parser

    def _get_user_template(self) -> str:
        return """Sender: {sender_name}, {sender_role} at {company_name} ({sender_email})
Value proposition: {value_proposition}

Target partner:
  Name:     {partner_name}
  Email:    {partner_email}
  Industry: {partner_industry}
  Website:  {partner_website}

Write a SHORT partnership outreach email — 80 words maximum in the body.
- Be specific to their industry
- End with one clear call-to-action
- Sign off as the sender

IMPORTANT: Respond with ONLY a JSON object. No preamble, no commentary.
Format: {format_instructions}"""

    def _build_variables(self, partner: Partner) -> dict:
        """Build template variables from company and partner data."""
        return {
            "sender_name": self.company.sender_name,
            "sender_role": self.company.sender_role,
            "company_name": self.company.name,
            "sender_email": self.company.sender_email,
            "value_proposition": self.company.value_proposition,
            "partner_name": partner.name,
            "partner_email": partner.email,
            "partner_industry": partner.industry,
            "partner_website": partner.website or "N/A",
            "format_instructions": self.parser.get_format_instructions(),
        }

    def generate(self, partner: Partner) -> OutreachEmail:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Invoke the LangChain chain
                variables = self._build_variables(partner)
                result = self.chain.invoke(variables)

                # LangChain parser returns dict, validate keys
                subject = result.get("subject")
                body = result.get("body")

                if not subject or not body:
                    raise EmailGenerationError(
                        f"Missing subject/body in parsed output: {result}"
                    )

                partner.status = EmailStatus.GENERATED
                partner.generated_at = datetime.now()
                return OutreachEmail(
                    partner=partner,
                    subject=subject,
                    body=body,
                )

            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY * (2 ** (attempt - 1))
                    print(f"\n  [retry {attempt}/{self.MAX_RETRIES}] {str(e)[:80]}… waiting {delay}s")
                    time.sleep(delay)
                    continue

        raise EmailGenerationError(
            f"Failed after {self.MAX_RETRIES} attempts.\nLast error: {last_error}"
        )