"""
Company Researcher - Cold Email Intelligence Tool

Companies and research results live in a SQL database (SQLite by default).
Research is grounded with RAG over each company's website, and the database can be
queried in plain English through a LangChain SQL agent.
"""

import argparse
import sys
import warnings

warnings.filterwarnings("ignore", message=".*langchain-community.*", category=DeprecationWarning)

from src.config import Config  # noqa: E402
from src.database import Database  # noqa: E402


def add_llm_args(p: argparse.ArgumentParser):
    p.add_argument("--api-key", help="API key (or set OPENAI_API_KEY)")
    p.add_argument("--base-url", help="Base URL for an OpenAI-compatible API (or set OPENAI_BASE_URL)")
    p.add_argument("--model", help="Chat model name (or set OPENAI_MODEL)")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Research companies for cold email outreach using AI, backed by a SQL database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. Load companies into the database (one-time, or whenever you have new ones)
  python main.py import sample_companies.csv

  # 2. Research every company that doesn't have a successful result yet
  python main.py research

  # 3. Ask questions about the results in plain English
  python main.py ask "Which companies are in fintech and what are their hooks?"

  # Use Postgres instead of SQLite
  python main.py --db postgresql+psycopg://user:pass@localhost/leads research
        """,
    )
    parser.add_argument("--db", help="SQLAlchemy database URL (or set DATABASE_URL; default sqlite:///data/companies.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="Import companies from a CSV file into the database")
    p_import.add_argument("input_csv", help="CSV with company name and website columns")
    p_import.add_argument("--company-col", default="company", help="Company name column (default: 'company')")
    p_import.add_argument("--website-col", default="website", help="Website column (default: 'website')")

    p_add = sub.add_parser("add", help="Add a single company to the database")
    p_add.add_argument("name")
    p_add.add_argument("website")

    p_research = sub.add_parser("research", help="Research companies stored in the database")
    add_llm_args(p_research)
    p_research.add_argument("--all", action="store_true", help="Re-research companies that already succeeded")
    p_research.add_argument("--company", action="append", help="Only research this company name (repeatable)")
    p_research.add_argument("--limit", type=int, help="Research at most N companies")
    p_research.add_argument("--concurrency", type=int, default=3, help="Parallel companies (default: 3)")
    p_research.add_argument("--no-rag", action="store_true", help="Skip website retrieval; use model knowledge only")
    p_research.add_argument("--embedding-model", help="Embedding model for RAG (or set EMBEDDING_MODEL)")
    p_research.add_argument("--embedding-base-url", help="Embeddings API base URL (or EMBEDDING_BASE_URL; default --base-url)")
    p_research.add_argument("--max-pages", type=int, help="Website pages crawled per company (default: 5)")
    p_research.add_argument("--top-k", type=int, help="Chunks retrieved per research question (default: 4)")
    p_research.add_argument("--no-progress", action="store_true", help="Disable progress display")

    p_ask = sub.add_parser("ask", help="Ask a natural-language question answered via LangChain text-to-SQL")
    add_llm_args(p_ask)
    p_ask.add_argument("question")
    p_ask.add_argument("--verbose", "-v", action="store_true", help="Show the agent's SQL queries and tool calls")

    return parser.parse_args()


def fail(errors: list[str]):
    for err in errors:
        print(f"[ERROR] {err}", file=sys.stderr)
    sys.exit(1)


def cmd_import(args, db: Database):
    from src.csv_handler import CSVHandler

    companies = CSVHandler(args.input_csv, args.company_col, args.website_col).load()
    added, skipped = db.add_companies(companies)
    print(f"  Imported {added} companies ({skipped} already in the database) → {db.url}")


def cmd_add(args, db: Database):
    from src.models import Company

    added, _ = db.add_companies([Company(name=args.name, website=args.website)])
    print(f"  {'Added' if added else 'Already exists'}: {args.name}")


def cmd_research(args, config: Config, db: Database):
    from src.reporter import Reporter
    from src.researcher import CompanyResearcher

    companies = db.load_companies(pending_only=not args.all, names=args.company, limit=args.limit)
    if not companies:
        print("  Nothing to research. Import companies first, or pass --all to re-run finished ones.")
        return

    print(f"\n{'='*60}")
    print("  COMPANY RESEARCHER — Cold Email Intelligence")
    print(f"{'='*60}")
    print(f"  Model     : {config.model}")
    print(f"  Base URL  : {config.base_url}")
    print(f"  Database  : {config.database_url}")
    print(f"  RAG       : {f'{config.embedding_model} @ {config.embedding_base_url}' if config.use_rag else 'off'}")
    print(f"  Companies : {len(companies)}")
    print(f"{'='*60}\n")

    results = CompanyResearcher(config, db).research_all(companies, show_progress=not args.no_progress)
    Reporter.print_summary(results)
    print(f"\n  Results saved to the `company_research` table in {config.database_url}\n")


def cmd_ask(args, config: Config, db: Database):
    from src.sql_agent import SQLAgent

    answer = SQLAgent(config, db).ask(args.question, verbose=args.verbose)
    print(f"\n{answer}\n")


def main():
    args = parse_args()
    config = Config.from_args(args)
    errors = config.validate(needs_llm=args.command in ("research", "ask"))
    if errors:
        fail(errors)

    db = Database(config.database_url)

    if args.command == "import":
        cmd_import(args, db)
    elif args.command == "add":
        cmd_add(args, db)
    elif args.command == "research":
        cmd_research(args, config, db)
    elif args.command == "ask":
        cmd_ask(args, config, db)


if __name__ == "__main__":
    main()
