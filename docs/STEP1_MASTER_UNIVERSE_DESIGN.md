# Step 1: Master Universe and screening foundation — design

## Scope

Build the reproducible metadata layer for the historical corpus. This step
enumerates and stores PubMed records, computes recall-oriented deterministic
priority flags, defines structured LLM/human-review contracts, and exports
review queues. It does not run the complete historical backfill, call an LLM,
make final inclusion decisions, or download full text.

## Inputs

- `config/journals.json`: the locked multi-tier v1 whitelist.
- `config/journal_blacklist.json`: exact-journal and publisher-family default
  exclusions; pure review journals are omitted from the whitelist.
- PubMed E-utilities (`esearch.fcgi` and `efetch.fcgi`).
- Start/end dates supplied explicitly on every enumeration run.
- Optional NCBI API key read only from the environment.

## Method and contracts

### Journal-first enumeration

For each journal, query PubMed by exact journal title and publication-date
range. Do not include cancer, omics, or article-type terms in the discovery
query. `ESearch` obtains the complete PMID set using PubMed history; `EFetch`
retrieves XML in bounded batches. All returned article types are stored.

Each record preserves PMID, DOI, journal key/title, publication date and
precision, title, abstract, article types, authors, MeSH terms, source URL,
fetch run, and an update timestamp. Upsert by PMID makes retries idempotent.

### Deterministic screen

Versioned regular-expression groups separately detect cancer and omics
language in title, abstract, and MeSH. A record receives
`candidate_priority = true` only when both groups match. A miss receives
`unmatched`, never `excluded`; all records remain eligible for LLM review.

### Structured LLM screen

The export schema requires disease, study type, primary contribution, data
modalities, computational centrality (0–3), new experimental data, public data
reuse, relevance (`YES/MAYBE/NO`), confidence, rationale, model identifier,
prompt version, and timestamp. Import rejects unknown enum values and missing
provenance.

### Human audit

Every `YES` and `MAYBE` is reviewed. Exactly 10% of the current LLM `NO` set is
selected with a locked seed using a stable PMID hash, so reruns are reproducible
and additions do not reshuffle existing priorities. Human review records the
final decision, computational-story-centrality judgment, reason, reviewer, and
timestamp; no row is deleted.

## Coverage and validity checks

- ESearch reported count must equal the number of unique PMIDs returned.
- Every requested PMID must appear in parsed EFetch XML; missing IDs fail the
  run rather than silently shrinking the universe.
- DOI is normalized but never used as the sole identity because it may be
  absent.
- Journal aliases returned by PubMed are reconciled to the query's registry
  key and the raw returned title is retained.
- Re-running an identical range must not duplicate records.
- Exports include run metadata and row counts.
- The historical backfill step will independently compare annual per-journal
  counts with PubMed UI/API totals and investigate discrepancies.

## Expected outputs

Code in `src/article_blueprint_os/`, JSON schemas under `schemas/`, and tests.
Real SQLite databases, raw XML, TSV/JSONL queues, and full-text manifests are
written only below `ARTICLE_BLUEPRINT_DATA` and are not part of this PR.

## Open questions for review

- Whether v1 should retain all publication types in the Master Universe (the
  current recall-first design) or filter obvious non-research types during
  enumeration.
- Whether the `NO` audit fraction should remain 10% after the first measured
  false-negative confidence interval.
- Whether the historical cutoff should be the PR merge date or a separately
  locked date; CLI requires it explicitly to avoid moving-target runs.
