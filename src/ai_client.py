"""
LangChain chat client for any OpenAI-compatible API
(OpenAI, Groq, Together, Ollama, vLLM, Anthropic via proxy, ...).
"""

import json
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.config import Config
from src.models import ResearchOutput
from src.rag import RetrievedContext

SYSTEM_PROMPT = """You are a business intelligence analyst specializing in cold email research.
Your job is to research companies and extract information useful for personalized outreach.
Prefer facts from the provided website context over your own memory. Never invent news,
funding rounds, or numbers that are not in the context or that you are not confident about."""

RESEARCH_PROMPT = """Research the company "{company_name}" with website {website}.

{context_section}

Fill in every field. Focus on information that would make a cold email feel researched and
genuine, not templated."""

CONTEXT_WITH_RAG = """Below are excerpts retrieved from the company's own website. Base your answer on them:

<website_context>
{context}
</website_context>"""

CONTEXT_WITHOUT_RAG = """No website content could be retrieved. Use what you know about this company, or make
reasonable inferences from its name and domain, and keep claims general where unsure."""

JSON_FALLBACK_SUFFIX = """

Respond with ONLY a JSON object with these keys: description, mission, industry, key_products,
cold_email_hooks. All values are strings. No markdown, no other text."""


class AIClient:
    def __init__(self, config: Config):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0.3,
            max_tokens=1200,
            max_retries=4,  # built-in exponential backoff for rate limits/timeouts
            timeout=90,
        )
        self.prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", RESEARCH_PROMPT)])
        # Tool calling is the most widely supported structured-output mode across compatible APIs.
        self.structured_chain = self.prompt | self.llm.with_structured_output(ResearchOutput, method="function_calling")
        self.plain_chain = self.prompt | self.llm

    def research_company(self, company_name: str, website: str, context: RetrievedContext) -> ResearchOutput:
        inputs = {
            "company_name": company_name,
            "website": website,
            "context_section": CONTEXT_WITHOUT_RAG if context.empty else CONTEXT_WITH_RAG.format(context=context.text),
        }
        try:
            result = self.structured_chain.invoke(inputs)
            if result is not None:
                return result
        except Exception:
            pass  # API may not support tool calling — fall back to plain JSON prompting
        return self._research_plain_json(inputs)

    def _research_plain_json(self, inputs: dict) -> ResearchOutput:
        inputs = {**inputs, "context_section": inputs["context_section"] + JSON_FALLBACK_SUFFIX}
        content = self.plain_chain.invoke(inputs).content.strip()
        match = re.search(r"\{.*\}", content, re.S)  # strip code fences / chatter
        if not match:
            raise ValueError(f"Model did not return JSON: {content[:120]!r}")
        data = json.loads(match.group(0))
        return ResearchOutput(**{k: _as_text(data.get(k, "")) for k in ResearchOutput.model_fields})


def _as_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {v}" for v in value)
    return str(value)
