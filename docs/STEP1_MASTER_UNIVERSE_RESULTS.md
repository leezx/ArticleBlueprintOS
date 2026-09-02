# Step 1: Master Universe and screening foundation — results

## Compute record

- **Environment**: local Python 3, standard library only.
- **Unit validation**: 15 tests passed on 2026-09-02.
- **Live-source validation**: PubMed ESearch registry smoke test for calendar
  year 2025, performed 2026-09-02 against the 65 entries in the expanded list,
  followed by targeted checks for the two inherited core journals.
- **Full historical backfill**: not run in this step by design.

## Real findings

The first live registry pass produced nonzero 2025 PubMed counts for 64 of 65
journals. `Cancer Epidemiology, Biomarkers & Prevention` returned zero because
the configured long title did not exactly match PubMed's journal index. The
query was changed to the NLM abbreviation `Cancer Epidemiol Biomarkers Prev`
and independently re-run; it returned 263 records for 2025. Therefore all
67/67 non-review whitelist entries now pass the nonzero-hit smoke check.
The two inherited core entries omitted from the expanded user list were also
checked separately: Science Advances returned 3,171 records and Cell Genomics
returned 190 records for 2025.

The smoke counts are discovery-route checks, not corpus counts: they include
all PubMed publication types and must not be interpreted as numbers of eligible
cancer-omics original-research papers.

## Implemented artifacts

- `config/journals.json` — 67-entry Gold/Silver/Methods/Supplementary registry.
- `config/journal_blacklist.json` — exact and publisher-family exclusion policy.
- `config/screening_rules.json` — versioned recall-oriented cancer/omics rules.
- `src/article_blueprint_os/` — PubMed client, XML parser, SQLite provenance
  layer, screening, structured LLM import/export, and seeded `NO` audit sample.
- `schemas/` — LLM-screen and lawful-full-text manifest contracts.
- `prompts/llm_screen_v1.md` — versioned, schema-bound high-recall classifier
  prompt.
- `tests/` — 15 parser, registry, idempotency, screening, and audit tests.

## Data-boundary verification

The implementation rejects database and export paths inside the repository.
Enumeration writes immutable XML batches, sizes, and SHA-256 values only to an
explicit external `--raw-dir`. This PR contains no PubMed payload, database,
PDF, or full-text file.

## Unresolved items

- The complete 2023-to-cutoff historical run and annual count reconciliation
  remain Step 2.
- PubMed nonzero counts prove query reachability, not perfect journal identity;
  Step 2 will inspect returned journal titles and reconcile annual totals.
- The LLM classifier has not run, so false-negative performance is unknown.
- No full text has been downloaded; retrieval begins only after paper-level
  review queues exist.

## Review history

GitHub PR review is pending. No merge has occurred.
