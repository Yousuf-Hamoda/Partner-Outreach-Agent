"""
Natural-language querying of the research database with LangChain's SQL toolkit.

Example: "Which fintech companies mention hiring?" → the agent inspects the schema,
writes SQL, checks it, runs it, and answers from the rows.
"""

import re
import warnings

warnings.filterwarnings("ignore", message=".*langchain-community.*", category=DeprecationWarning)

from langchain.agents import create_agent  # noqa: E402
from langchain_community.agent_toolkits import SQLDatabaseToolkit  # noqa: E402
from langchain_community.utilities import SQLDatabase  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from sqlalchemy.exc import StatementError  # noqa: E402

from src.config import Config  # noqa: E402
from src.database import Database  # noqa: E402

SYSTEM_PROMPT = """You are an agent that answers questions about a company-research database.
Given a question, write a syntactically correct {dialect} query, run it, and answer from the results.

Tables:
- companies(id, name, website, extra_fields JSON text, created_at)
- company_research(company_id -> companies.id, industry, description, mission, key_products,
  cold_email_hooks, sources JSON text, status 'success'|'error', error, researched_at)

Rules:
- Always list tables and look at the relevant schema before querying.
- Unless the user asks for more, limit results to {top_k} rows.
- Only select the columns you need. Use case-insensitive matching (LOWER(...) LIKE ...) for text.
- Double-check queries with the query checker before running them; if a query errors, fix and retry.
- NEVER run INSERT, UPDATE, DELETE, DROP, ALTER, or any other statement that modifies data.
- Answer concisely and include company names and websites when relevant."""

_READ_ONLY = re.compile(r"^\s*(select|with|explain|show|describe)\b", re.I)


class ReadOnlySQLDatabase(SQLDatabase):
    """SQLDatabase that refuses anything other than a single read query."""

    def run(self, command, *args, **kwargs):
        sql = str(command).strip().rstrip(";")
        if not _READ_ONLY.match(sql) or ";" in sql:
            # StatementError is a SQLAlchemyError, so the toolkit reports it back to the
            # agent as "Error: ..." instead of crashing the run.
            raise StatementError("Only single read-only SELECT queries are allowed.", sql, None, None)
        return super().run(sql, *args, **kwargs)


class SQLAgent:
    def __init__(self, config: Config, database: Database, top_k: int = 20):
        self.db = ReadOnlySQLDatabase(database.engine, include_tables=["companies", "company_research"])
        llm = ChatOpenAI(model=config.model, api_key=config.api_key, base_url=config.base_url,
                         temperature=0, max_retries=4)
        tools = SQLDatabaseToolkit(db=self.db, llm=llm).get_tools()
        self.agent = create_agent(
            llm,
            tools,
            system_prompt=SYSTEM_PROMPT.format(dialect=self.db.dialect, top_k=top_k),
        )

    def ask(self, question: str, verbose: bool = False) -> str:
        final = ""
        for step in self.agent.stream({"messages": [{"role": "user", "content": question}]},
                                      stream_mode="values"):
            msg = step["messages"][-1]
            if verbose:
                msg.pretty_print()
            final = msg.content if isinstance(msg.content, str) else str(msg.content)
        return final
