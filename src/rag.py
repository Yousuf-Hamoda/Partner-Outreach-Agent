"""
RAG over a company's own website.

For each company: crawl the homepage plus a few high-signal same-domain pages
(about, mission, products, news, careers...), chunk the text, embed it into an
in-memory vector store, and retrieve the chunks most relevant to each research
question. The retrieved text grounds the LLM instead of relying on its memory.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import OPENAI_DEFAULT_BASE_URL, Config

USER_AGENT = "Mozilla/5.0 (compatible; CompanyResearcher/2.0)"

# Links whose path contains these words are crawled first.
PRIORITY_KEYWORDS = (
    "about", "mission", "company", "team", "story", "values", "product", "solution",
    "platform", "service", "customer", "news", "press", "blog", "careers", "jobs",
)

# One retrieval query per field we ask the LLM for.
RETRIEVAL_QUERIES = (
    "What does the company do, what products or services does it offer, and who are its customers?",
    "What is the company's mission, vision, purpose, or values?",
    "Recent company news, announcements, funding, growth, launches, partnerships, or hiring.",
    "Industry, market, and the problems the company solves for its customers.",
)


@dataclass
class RetrievedContext:
    text: str = ""
    sources: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.text


class WebsiteRAG:
    def __init__(self, config: Config, timeout: float = 15.0):
        self.config = config
        self.timeout = timeout
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

        is_openai = config.embedding_base_url.rstrip("/") == OPENAI_DEFAULT_BASE_URL
        self.embeddings = OpenAIEmbeddings(
            model=config.embedding_model,
            api_key=config.embedding_api_key,
            base_url=config.embedding_base_url,
            # Non-OpenAI servers (Ollama, vLLM, ...) expect raw strings, not tiktoken ids.
            check_embedding_ctx_length=is_openai,
        )

    # ── Crawling ───────────────────────────────────────────────────────────

    def _fetch(self, url: str) -> tuple[str, BeautifulSoup] | None:
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException:
            return None
        if "html" not in resp.headers.get("content-type", "html"):
            return None
        return resp.url, BeautifulSoup(resp.text, "html.parser")

    @staticmethod
    def _page_text(soup: BeautifulSoup) -> str:
        for tag in soup(["script", "style", "noscript", "svg", "iframe", "form"]):
            tag.decompose()
        title = soup.title.get_text(strip=True) if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{2,}", "\n", text)
        return f"{title}\n{text}" if title else text

    @staticmethod
    def _candidate_links(base_url: str, soup: BeautifulSoup) -> list[str]:
        host = urlparse(base_url).netloc.removeprefix("www.")
        seen, scored = set(), []
        for a in soup.find_all("a", href=True):
            url = urljoin(base_url, a["href"]).split("#")[0].split("?")[0].rstrip("/")
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or parsed.netloc.removeprefix("www.") != host:
                continue
            if url in seen or url == base_url.rstrip("/"):
                continue
            if re.search(r"\.(pdf|png|jpe?g|gif|svg|zip|mp4|webp)$", parsed.path, re.I):
                continue
            seen.add(url)
            path = parsed.path.lower()
            score = sum(kw in path for kw in PRIORITY_KEYWORDS)
            if score:
                scored.append((score, -path.count("/"), url))
        scored.sort(reverse=True)
        return [url for *_, url in scored]

    def crawl(self, website: str) -> list[Document]:
        first = self._fetch(website)
        if not first:
            return []
        home_url, home_soup = first
        links = self._candidate_links(home_url, home_soup)
        docs = [Document(page_content=self._page_text(home_soup), metadata={"source": home_url})]

        for url in links:
            if len(docs) >= self.config.max_pages:
                break
            page = self._fetch(url)
            if page:
                final_url, soup = page
                docs.append(Document(page_content=self._page_text(soup), metadata={"source": final_url}))
        return [d for d in docs if d.page_content.strip()]

    # ── Retrieval ──────────────────────────────────────────────────────────

    def retrieve(self, website: str) -> RetrievedContext:
        docs = self.crawl(website)
        if not docs:
            return RetrievedContext()

        chunks = self.splitter.split_documents(docs)
        store = InMemoryVectorStore(self.embeddings)
        store.add_documents(chunks)

        picked: dict[str, Document] = {}
        for query in RETRIEVAL_QUERIES:
            for doc in store.similarity_search(query, k=self.config.top_k):
                picked.setdefault(doc.page_content, doc)

        blocks = [f"[Source: {d.metadata['source']}]\n{d.page_content}" for d in picked.values()]
        sources = list(dict.fromkeys(d.metadata["source"] for d in picked.values()))
        return RetrievedContext(text="\n\n---\n\n".join(blocks), sources=sources)
