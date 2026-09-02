from __future__ import annotations

import json
import hashlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterator


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


@dataclass(frozen=True)
class SearchHistory:
    count: int
    query_key: str
    webenv: str


@dataclass(frozen=True)
class Article:
    pmid: str
    doi: str | None
    source_journal_title: str
    publication_date: str | None
    publication_date_precision: str
    publication_year: int | None
    title: str
    abstract: str
    article_types: tuple[str, ...]
    authors: tuple[dict[str, str], ...]
    mesh_terms: tuple[str, ...]


@dataclass(frozen=True)
class FetchBatch:
    retstart: int
    articles: tuple[Article, ...]
    raw_xml: bytes
    sha256: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    doi = value.strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.I).strip().rstrip(". ")
    return doi.casefold() or None


def element_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _first_text(root: ET.Element, paths: tuple[str, ...]) -> str | None:
    for path in paths:
        value = element_text(root.find(path))
        if value:
            return value
    return None


def _publication_date(article: ET.Element) -> tuple[str | None, str, int | None]:
    date_nodes = [
        article.find(".//Article/ArticleDate"),
        article.find(".//JournalIssue/PubDate"),
        article.find(".//PubmedData/History/PubMedPubDate[@PubStatus='pubmed']"),
        article.find(".//PubmedData/History/PubMedPubDate[@PubStatus='entrez']"),
    ]
    for node in date_nodes:
        if node is None:
            continue
        year_text = element_text(node.find("Year"))
        medline = element_text(node.find("MedlineDate"))
        if not year_text and medline:
            match = re.search(r"(?:19|20)\d{2}", medline)
            year_text = match.group(0) if match else ""
        if not year_text or not year_text.isdigit():
            continue
        year = int(year_text)
        month_text = element_text(node.find("Month"))
        day_text = element_text(node.find("Day"))
        if not month_text:
            return f"{year:04d}", "year", year
        month = int(month_text) if month_text.isdigit() else MONTHS.get(month_text[:3].casefold())
        if month is None or not 1 <= month <= 12:
            return f"{year:04d}", "year", year
        if not day_text or not day_text.isdigit():
            return f"{year:04d}-{month:02d}", "month", year
        day = int(day_text)
        if not 1 <= day <= 31:
            return f"{year:04d}-{month:02d}", "month", year
        return f"{year:04d}-{month:02d}-{day:02d}", "day", year
    return None, "unknown", None


def parse_pubmed_xml(xml_bytes: bytes) -> list[Article]:
    root = ET.fromstring(xml_bytes)
    parsed: list[Article] = []
    for item in root.findall(".//PubmedArticle"):
        pmid = element_text(item.find(".//MedlineCitation/PMID"))
        if not pmid:
            continue
        title = element_text(item.find(".//Article/ArticleTitle"))
        abstract_parts: list[str] = []
        for node in item.findall(".//Article/Abstract/AbstractText"):
            value = element_text(node)
            label = (node.attrib.get("Label") or "").strip()
            if value:
                abstract_parts.append(f"{label}: {value}" if label else value)
        doi = None
        for identifier in item.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if identifier.attrib.get("IdType") == "doi":
                doi = normalize_doi(element_text(identifier))
                break
        journal_title = _first_text(
            item,
            (".//Journal/Title", ".//MedlineJournalInfo/MedlineTA"),
        ) or "Unknown"
        publication_date, precision, year = _publication_date(item)
        article_types = tuple(
            dict.fromkeys(
                value
                for node in item.findall(".//Article/PublicationTypeList/PublicationType")
                if (value := element_text(node))
            )
        )
        authors: list[dict[str, str]] = []
        for author in item.findall(".//Article/AuthorList/Author"):
            collective = element_text(author.find("CollectiveName"))
            if collective:
                authors.append({"collective": collective})
                continue
            record = {
                "last": element_text(author.find("LastName")),
                "fore": element_text(author.find("ForeName")),
                "initials": element_text(author.find("Initials")),
            }
            for identifier in author.findall("Identifier"):
                if identifier.attrib.get("Source", "").casefold() == "orcid":
                    record["orcid"] = element_text(identifier)
            if any(record.values()):
                authors.append(record)
        mesh_terms = tuple(
            dict.fromkeys(
                value
                for heading in item.findall(".//MeshHeadingList/MeshHeading")
                if (value := element_text(heading.find("DescriptorName")))
            )
        )
        parsed.append(
            Article(
                pmid=pmid,
                doi=doi,
                source_journal_title=journal_title,
                publication_date=publication_date,
                publication_date_precision=precision,
                publication_year=year,
                title=title,
                abstract="\n".join(abstract_parts),
                article_types=article_types,
                authors=tuple(authors),
                mesh_terms=mesh_terms,
            )
        )
    return parsed


class PubMedClient:
    def __init__(
        self,
        *,
        email: str,
        api_key: str | None = None,
        tool: str = "article-blueprint-os",
        timeout: float = 60,
        max_retries: int = 5,
    ) -> None:
        if "@" not in email:
            raise ValueError("A valid contact email is required by NCBI guidance")
        self.email = email
        self.api_key = api_key
        self.tool = tool
        self.timeout = timeout
        self.max_retries = max_retries
        self.minimum_interval = 0.11 if api_key else 0.34
        self._last_request = 0.0

    def _request(self, endpoint: str, params: dict[str, Any]) -> bytes:
        merged = {"tool": self.tool, "email": self.email, **params}
        if self.api_key:
            merged["api_key"] = self.api_key
        data = urllib.parse.urlencode(merged).encode("utf-8")
        request = urllib.request.Request(
            f"{EUTILS_BASE}/{endpoint}",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": f"{self.tool}/0.1 ({self.email})",
            },
            method="POST",
        )
        for attempt in range(self.max_retries + 1):
            wait = self.minimum_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = response.read()
                self._last_request = time.monotonic()
                return payload
            except urllib.error.HTTPError as exc:
                self._last_request = time.monotonic()
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.max_retries:
                    raise
            except urllib.error.URLError:
                self._last_request = time.monotonic()
                if attempt == self.max_retries:
                    raise
            time.sleep(min(2**attempt, 30))
        raise RuntimeError("unreachable")

    def search_history(self, query: str) -> SearchHistory:
        payload = self._request(
            "esearch.fcgi",
            {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": 0,
                "usehistory": "y",
            },
        )
        result = json.loads(payload)["esearchresult"]
        return SearchHistory(
            count=int(result["count"]),
            query_key=str(result["querykey"]),
            webenv=str(result["webenv"]),
        )

    def fetch_history(
        self, history: SearchHistory, *, batch_size: int = 200
    ) -> Iterator[FetchBatch]:
        if batch_size < 1 or batch_size > 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        for start in range(0, history.count, batch_size):
            payload = self._request(
                "efetch.fcgi",
                {
                    "db": "pubmed",
                    "query_key": history.query_key,
                    "WebEnv": history.webenv,
                    "retstart": start,
                    "retmax": batch_size,
                    "retmode": "xml",
                },
            )
            yield FetchBatch(
                retstart=start,
                articles=tuple(parse_pubmed_xml(payload)),
                raw_xml=payload,
                sha256=hashlib.sha256(payload).hexdigest(),
            )
