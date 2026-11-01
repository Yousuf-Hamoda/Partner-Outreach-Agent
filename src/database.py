"""
SQL storage — replaces the CSV/spreadsheet input and output.

Uses SQLAlchemy so any database with a SQLAlchemy URL works
(SQLite by default, Postgres/MySQL via DATABASE_URL), and exposes the same
engine to LangChain's SQLDatabase for natural-language querying.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text,
    UniqueConstraint, create_engine, delete, insert, select,
)
from sqlalchemy.engine import Engine, make_url

from src.models import Company, CompanyResearch

metadata = MetaData()

companies_table = Table(
    "companies",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("website", String(512), nullable=False),
    Column("extra_fields", Text, nullable=False, default="{}"),  # JSON of extra import columns
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("website", name="uq_companies_website"),
)

research_table = Table(
    "company_research",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("company_id", Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("industry", Text),
    Column("description", Text),
    Column("mission", Text),
    Column("key_products", Text),
    Column("cold_email_hooks", Text),
    Column("sources", Text),  # JSON list of URLs used as RAG context
    Column("status", String(16), nullable=False),  # 'success' | 'error'
    Column("error", Text),
    Column("researched_at", DateTime(timezone=True), nullable=False),
)


def normalize_website(website: str) -> str:
    website = website.strip()
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website.rstrip("/")


class Database:
    def __init__(self, url: str):
        parsed = make_url(url)
        if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        self.url = url
        self.engine: Engine = create_engine(url)
        metadata.create_all(self.engine)

    # ── Companies ──────────────────────────────────────────────────────────

    def add_companies(self, companies: list[Company]) -> tuple[int, int]:
        """Insert companies, skipping websites already present. Returns (added, skipped)."""
        added = skipped = 0
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            existing = set(conn.execute(select(companies_table.c.website)).scalars())
            for c in companies:
                website = normalize_website(c.website)
                if website in existing:
                    skipped += 1
                    continue
                conn.execute(insert(companies_table).values(
                    name=c.name or website,
                    website=website,
                    extra_fields=json.dumps(c.extra_fields or {}),
                    created_at=now,
                ))
                existing.add(website)
                added += 1
        return added, skipped

    def load_companies(self, pending_only: bool = True, names: list[str] | None = None,
                       limit: int | None = None) -> list[Company]:
        """Load companies to research. By default only those without a successful result."""
        c, r = companies_table, research_table
        stmt = select(c).order_by(c.c.id)
        if pending_only:
            done = select(r.c.company_id).where(r.c.status == "success")
            stmt = stmt.where(c.c.id.not_in(done))
        if names:
            stmt = stmt.where(c.c.name.in_(names))
        if limit:
            stmt = stmt.limit(limit)
        with self.engine.connect() as conn:
            return [
                Company(id=row.id, name=row.name, website=row.website,
                        extra_fields=json.loads(row.extra_fields or "{}"))
                for row in conn.execute(stmt)
            ]

    # ── Research results ───────────────────────────────────────────────────

    def save_research(self, result: CompanyResearch) -> None:
        """Upsert the research row for a company (portable delete+insert)."""
        if result.company.id is None:
            raise ValueError("Company must be persisted before saving research.")
        with self.engine.begin() as conn:
            conn.execute(delete(research_table).where(research_table.c.company_id == result.company.id))
            conn.execute(insert(research_table).values(
                company_id=result.company.id,
                industry=result.industry,
                description=result.description,
                mission=result.mission,
                key_products=result.key_products,
                cold_email_hooks=result.cold_email_hooks,
                sources=json.dumps(result.sources),
                status="success" if result.success else "error",
                error=result.error,
                researched_at=datetime.now(timezone.utc),
            ))
