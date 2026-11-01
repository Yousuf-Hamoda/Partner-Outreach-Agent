"""
Data models for company research.
"""

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field


@dataclass
class Company:
    name: str
    website: str
    extra_fields: dict = field(default_factory=dict)  # Extra columns carried over from the import
    id: Optional[int] = None  # Primary key in the `companies` table


@dataclass
class CompanyResearch:
    company: Company
    description: str = ""
    mission: str = ""
    cold_email_hooks: str = ""
    industry: str = ""
    key_products: str = ""
    sources: list[str] = field(default_factory=list)  # URLs whose content grounded the answer
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class ResearchOutput(BaseModel):
    """Structured output schema the LLM must fill in."""

    description: str = Field(description="2-3 sentence overview of what this company does and who they serve")
    mission: str = Field(description="Their mission statement or core purpose (1-2 sentences)")
    industry: str = Field(description="Primary industry/sector, e.g. 'B2B SaaS', 'FinTech', 'Healthcare AI'")
    key_products: str = Field(description="Their main products or services (1-2 sentences)")
    cold_email_hooks: str = Field(
        description=(
            "3-5 specific, compelling talking points for a cold email to their CEO asking for a job: "
            "recent news, growth signals, pain points you could solve, or unique mission details. "
            "Concrete and personalized, not generic."
        )
    )
