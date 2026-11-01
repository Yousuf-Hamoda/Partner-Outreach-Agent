"""
Configuration management — reads from args or environment variables.
"""

import os
from dataclasses import dataclass

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


@dataclass
class Config:
    # Chat model (any OpenAI-compatible API)
    api_key: str = ""
    base_url: str = OPENAI_DEFAULT_BASE_URL
    model: str = "gpt-4o-mini"

    # Storage
    database_url: str = "sqlite:///data/companies.db"

    # RAG
    use_rag: bool = True
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = ""  # defaults to base_url
    embedding_api_key: str = ""   # defaults to api_key
    max_pages: int = 5            # pages crawled per company website
    top_k: int = 4                # chunks retrieved per retrieval query

    concurrency: int = 3

    @classmethod
    def from_args(cls, args) -> "Config":
        def arg(name):
            return getattr(args, name, None)

        api_key = arg("api_key") or os.getenv("OPENAI_API_KEY", "")
        base_url = arg("base_url") or os.getenv("OPENAI_BASE_URL", OPENAI_DEFAULT_BASE_URL)
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=arg("model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            database_url=arg("db") or os.getenv("DATABASE_URL", "sqlite:///data/companies.db"),
            use_rag=not arg("no_rag"),
            embedding_model=arg("embedding_model") or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_base_url=arg("embedding_base_url") or os.getenv("EMBEDDING_BASE_URL", "") or base_url,
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", "") or api_key,
            max_pages=arg("max_pages") or int(os.getenv("RAG_MAX_PAGES", "5")),
            top_k=arg("top_k") or int(os.getenv("RAG_TOP_K", "4")),
            concurrency=arg("concurrency") or 3,
        )

    def validate(self, needs_llm: bool = True) -> list[str]:
        errors = []
        if needs_llm:
            if not self.api_key:
                errors.append("API key is required. Pass --api-key or set OPENAI_API_KEY.")
            if not self.model:
                errors.append("Model name is required. Pass --model or set OPENAI_MODEL.")
        if self.concurrency < 1:
            errors.append("Concurrency must be at least 1.")
        if self.max_pages < 1:
            errors.append("--max-pages must be at least 1.")
        return errors
