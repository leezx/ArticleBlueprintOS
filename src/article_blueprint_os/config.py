from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Journal:
    key: str
    title: str
    pubmed_title: str
    tier: str
    tracks: tuple[str, ...]
    priority: float

    @property
    def pubmed_term(self) -> str:
        escaped = self.pubmed_title.replace('"', '\\"')
        return f'"{escaped}"[jour]'


@dataclass(frozen=True)
class JournalRegistry:
    version: str
    effective_from: str
    journals: tuple[Journal, ...]

    def by_key(self, key: str) -> Journal:
        for journal in self.journals:
            if journal.key == key:
                return journal
        valid = ", ".join(j.key for j in self.journals)
        raise ValueError(f"Unknown journal key {key!r}; expected one of: {valid}")


@dataclass(frozen=True)
class ScreeningRules:
    version: str
    cancer: tuple[str, ...]
    omics: tuple[str, ...]


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def load_journals(path: str | Path) -> JournalRegistry:
    raw = _read_json(path)
    journals = tuple(
        Journal(
            key=str(item["key"]),
            title=str(item["title"]),
            pubmed_title=str(item["pubmed_title"]),
            tier=str(item["tier"]),
            tracks=tuple(str(track) for track in item["tracks"]),
            priority=float(item["priority"]),
        )
        for item in raw["journals"]
    )
    keys = [journal.key for journal in journals]
    titles = [journal.title.casefold() for journal in journals]
    if len(keys) != len(set(keys)) or len(titles) != len(set(titles)):
        raise ValueError("Journal keys and titles must be unique")
    if [j.priority for j in journals] != sorted(j.priority for j in journals):
        raise ValueError("Journal registry must be ordered by ascending priority")
    return JournalRegistry(
        version=str(raw["version"]),
        effective_from=str(raw["effective_from"]),
        journals=journals,
    )


def load_screening_rules(path: str | Path) -> ScreeningRules:
    raw = _read_json(path)
    cancer = tuple(str(pattern) for pattern in raw["cancer"])
    omics = tuple(str(pattern) for pattern in raw["omics"])
    if not cancer or not omics:
        raise ValueError("Both cancer and omics rule groups must be non-empty")
    return ScreeningRules(version=str(raw["version"]), cancer=cancer, omics=omics)
