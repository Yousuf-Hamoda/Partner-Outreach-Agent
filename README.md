# Company Researcher 🔍
### Cold Email Intelligence Tool

Stores companies in a SQL database → crawls their websites (RAG) → uses AI to generate research for personalized cold emails to their CEO → lets you query the results in plain English.

---

## Features

- **SQL storage instead of spreadsheets** — companies and results live in a database (SQLite by default, any SQLAlchemy URL such as Postgres/MySQL via `--db` / `DATABASE_URL`)
- **RAG-grounded research** — crawls each company's homepage plus high-signal pages (about, mission, products, news, careers), embeds the chunks, and retrieves the most relevant ones for every research question, so the LLM works from real website content instead of memory
- **Ask your data in plain English** — a LangChain SQL agent (`SQLDatabaseToolkit`) turns questions into read-only SQL against the results
- **Works with any OpenAI-compatible API** — OpenAI, OpenRouter, Groq, Together AI, Ollama, etc. (via `langchain-openai`)
- **Structured output** — tool-calling structured output, with a plain-JSON fallback for APIs that lack tool support
- **Resumable** — `research` only picks up companies without a successful result; results are saved as each one finishes

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Workflow

```bash
export OPENAI_API_KEY=sk-...

# 1. Load companies into the database (CSV is only an import format now)
python main.py import sample_companies.csv
python main.py add "Linear" linear.app        # or add one at a time

# 2. Research every company that doesn't have a successful result yet
python main.py research

# 3. Query the results in plain English
python main.py ask "Which fintech companies mention hiring, and what are their hooks?"
python main.py ask "List companies whose research failed and why" -v   # -v shows the SQL
```

The CSV needs a company name column and a website column (`name`, `company_name`, `url`, `site` are auto-detected; or use `--company-col` / `--website-col`). Extra columns are kept in `companies.extra_fields` as JSON. Re-importing skips websites that are already in the database.

---

## Commands & options

```bash
python main.py [--db URL] import FILE.csv [--company-col C] [--website-col W]
python main.py [--db URL] add NAME WEBSITE
python main.py [--db URL] research \
  --api-key sk-...                 # API key
  --base-url https://...           # OpenAI-compatible base URL
  --model gpt-4o-mini              # Chat model
  --all                            # Re-research companies that already succeeded
  --company "Stripe"               # Only these companies (repeatable)
  --limit 10                       # At most N companies
  --concurrency 5                  # Parallel companies (default: 3)
  --no-rag                         # Skip website retrieval
  --embedding-model NAME           # Embedding model for RAG
  --embedding-base-url https://... # Separate embeddings endpoint (default: --base-url)
  --max-pages 5                    # Pages crawled per website
  --top-k 4                        # Chunks retrieved per research question
  --no-progress
python main.py [--db URL] ask "QUESTION" [-v] [--api-key/--base-url/--model]
```

### Other providers

```bash
# OpenRouter (embedding models need the provider prefix)
python main.py research --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-4o-mini --embedding-model openai/text-embedding-3-small

# Groq for chat (no embeddings API) + local Ollama for embeddings
EMBEDDING_API_KEY=ollama python main.py research \
  --base-url https://api.groq.com/openai/v1 --model llama-3.3-70b-versatile \
  --embedding-base-url http://localhost:11434/v1 --embedding-model nomic-embed-text

# Fully local
python main.py research --api-key ollama --base-url http://localhost:11434/v1 \
  --model llama3.2 --embedding-model nomic-embed-text
```

If your provider has no embeddings endpoint and you don't want a separate one, use `--no-rag`.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the chat model |
| `OPENAI_BASE_URL` | Base URL (default: `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Chat model (default: `gpt-4o-mini`) |
| `DATABASE_URL` | SQLAlchemy URL (default: `sqlite:///data/companies.db`) |
| `EMBEDDING_MODEL` | Embedding model (default: `text-embedding-3-small`) |
| `EMBEDDING_BASE_URL` | Embeddings base URL (default: `OPENAI_BASE_URL`) |
| `EMBEDDING_API_KEY` | Embeddings API key (default: `OPENAI_API_KEY`) |
| `RAG_MAX_PAGES` / `RAG_TOP_K` | Crawl and retrieval sizes (defaults: 5 / 4) |

---

## Database schema

**`companies`** — `id`, `name`, `website` (unique), `extra_fields` (JSON), `created_at`

**`company_research`** — one row per company:

| Column | Description |
|--------|-------------|
| `company_id` | FK → `companies.id` |
| `industry` | Industry/sector |
| `description` | What the company does and who they serve |
| `mission` | Mission statement or core purpose |
| `key_products` | Main products or services |
| `cold_email_hooks` | Specific talking points for a CEO cold email |
| `sources` | JSON list of website pages used as RAG context |
| `status` / `error` | `success` or `error`, with the error message |
| `researched_at` | Timestamp |

Need a spreadsheet? `sqlite3 -header -csv data/companies.db "SELECT c.name, c.website, r.* FROM companies c JOIN company_research r ON r.company_id = c.id" > results.csv`

The `ask` agent rejects anything but single read-only queries; for Postgres/MySQL, also point it at a read-only database user.

---

## Project Structure

```
company_researcher/
├── main.py                  # CLI: import / add / research / ask
├── requirements.txt
├── sample_companies.csv     # Example import file
├── data/companies.db        # Default SQLite database (created on first run)
└── src/
    ├── config.py            # Config from args/env vars
    ├── models.py            # Dataclasses + structured-output schema
    ├── csv_handler.py       # CSV import parsing
    ├── database.py          # SQLAlchemy tables and persistence
    ├── rag.py               # Website crawl → chunk → embed → retrieve
    ├── ai_client.py         # LangChain ChatOpenAI research chain
    ├── sql_agent.py         # LangChain text-to-SQL agent (read-only)
    ├── researcher.py        # Concurrent RAG + LLM orchestration
    └── reporter.py          # Run summary
```

---

## Recommended Models

| Provider | Model | Notes |
|----------|-------|-------|
| OpenAI | `gpt-4o-mini` | Best value, fast |
| OpenAI | `gpt-4o` | Higher quality |
| Groq | `llama3-70b-8192` | Very fast, free tier |
| Together | `meta-llama/Llama-3-70b-chat-hf` | Good quality |
| Ollama | `llama3.2` | Fully local, free |
