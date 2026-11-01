"""
CompanyResearcher — orchestrates RAG + LLM research for many companies concurrently
and persists each result to the SQL database as it completes.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ai_client import AIClient
from src.config import Config
from src.database import Database
from src.models import Company, CompanyResearch
from src.rag import RetrievedContext, WebsiteRAG


class CompanyResearcher:
    def __init__(self, config: Config, database: Database):
        self.config = config
        self.db = database
        self.client = AIClient(config)
        self.rag = WebsiteRAG(config) if config.use_rag else None

    def research_one(self, company: Company) -> CompanyResearch:
        """Retrieve website context, then ask the LLM for structured research."""
        result = CompanyResearch(company=company)
        try:
            context = RetrievedContext()
            if self.rag:
                try:
                    context = self.rag.retrieve(company.website)
                except Exception as e:  # embeddings/crawl failure shouldn't kill the row
                    print(f"\n  [warn] RAG failed for {company.name}: {e}")
            data = self.client.research_company(company.name, company.website, context)
            result.description = data.description
            result.mission = data.mission
            result.industry = data.industry
            result.key_products = data.key_products
            result.cold_email_hooks = data.cold_email_hooks
            result.sources = context.sources
        except Exception as e:
            result.error = str(e)
        return result

    def research_all(self, companies: list[Company], show_progress: bool = True) -> list[CompanyResearch]:
        """Research all companies concurrently; each result is saved as soon as it finishes."""
        total = len(companies)
        results: list[CompanyResearch] = [None] * total  # preserve order
        completed = 0

        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            future_to_idx = {executor.submit(self.research_one, c): i for i, c in enumerate(companies)}

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = CompanyResearch(company=companies[idx], error=str(e))

                # Writes happen on the main thread only, so SQLite never sees concurrent writers.
                self.db.save_research(result)
                results[idx] = result
                completed += 1
                if show_progress:
                    self._print_progress(result, completed, total)

        return results

    @staticmethod
    def _print_progress(result: CompanyResearch, completed: int, total: int):
        status = "✓" if result.success else "✗"
        pct = int(completed / total * 100)
        bar_len = 30
        filled = int(bar_len * completed / total)
        bar = "█" * filled + "░" * (bar_len - filled)

        name = result.company.name[:35].ljust(35)
        line = f"  [{bar}] {pct:3d}%  {status} {name}"
        if not result.success:
            line += f" [ERROR: {result.error[:40]}]"
        elif not result.sources:
            line += " [no website context]"

        print(f"\r{line}", end="", flush=True)
        if completed == total:
            print()
