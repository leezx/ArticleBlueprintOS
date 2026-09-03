# ArticleBlueprintOS

ArticleBlueprintOS builds a reproducible, journal-first corpus of recent
computationally led cancer-omics research. The first release enumerates the
complete 2023-present PubMed universe for a curated multi-tier journal
whitelist, preserves every
record, and adds high-recall machine screening plus auditable human review
queues. Full text is retrieved only after a paper-level inclusion list has been
reviewed.

## Start here

- [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) — scope, definition of
  done, data boundaries, and PR lifecycle.
- [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md) — current progress and
  open work.
- [`docs/STEP1_MASTER_UNIVERSE_DESIGN.md`](docs/STEP1_MASTER_UNIVERSE_DESIGN.md)
  — locked design for the first historical-backfill step.
- [`docs/STEP2_HISTORICAL_BACKFILL_DESIGN.md`](docs/STEP2_HISTORICAL_BACKFILL_DESIGN.md)
  — locked execution and coverage design for the complete backfill.
- [`docs/STEP2_PUBMED_PARTITION_AMENDMENT.md`](docs/STEP2_PUBMED_PARTITION_AMENDMENT.md)
  — reviewed recovery design for PubMed's 10,000-result query limit.
- [`docs/STEP2_PUBMED_DATE_OVERLAP_AMENDMENT.md`](docs/STEP2_PUBMED_DATE_OVERLAP_AMENDMENT.md)
  — evidence-based correction for PMIDs that match more than one date slice.
- [`Worklog.md`](Worklog.md) — append-only history after PRs are merged.

## Quick start

The code uses only the Python standard library and supports Python 3.11+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
article-blueprint init-db --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3"
article-blueprint validate-registry --start 2025-01-01 --end 2025-12-31 \
  --email you@example.org
article-blueprint enumerate --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3" \
  --raw-dir "$ARTICLE_BLUEPRINT_DATA/raw/pubmed" \
  --start 2023-01-01 --end 2026-09-02 --email you@example.org
article-blueprint screen --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3"
article-blueprint status --db "$ARTICLE_BLUEPRINT_DATA/metadata.sqlite3"
```

The reviewed Step 2 runner executes and resumes the complete registry, then
exports aggregate coverage outside the repository:

```bash
article-blueprint historical-backfill \
  --db "$ARTICLE_BLUEPRINT_DATA/processed/metadata.sqlite3" \
  --raw-dir "$ARTICLE_BLUEPRINT_DATA/raw/pubmed" \
  --report "$ARTICLE_BLUEPRINT_DATA/result/step2/coverage.json" \
  --start 2023-01-01 --end 2026-09-02 --email you@example.org
```

If a journal fails, rerun the same command with `--resume-id` set to the stored
backfill ID. Completed journals are skipped and prior failed enumeration runs
remain in the provenance database.

## Manual Web calibration bridge

The reviewed Step 3 amendment permits a human operator to use ChatGPT Web for
the locked 600-record calibration. ArticleBlueprintOS does not call a model,
control a browser, or transmit metadata. Prepare the deterministic external
packets locally (20 records per batch by default):

```bash
article-blueprint prepare-web-calibration-batches \
  --db "$ARTICLE_BLUEPRINT_DATA/processed/metadata.sqlite3" \
  --calibration-id CALIBRATION_ID \
  --out "$ARTICLE_BLUEPRINT_DATA/result/step3/calibration/web_batches" \
  --software-revision GIT_SHA
```

For each packet, a human starts a fresh ChatGPT conversation, pastes the whole
`web_prompt.txt`, and saves the response verbatim to a new file in that batch
directory. The model-visible packet contains only PMID, DOI, title, abstract,
article types, and MeSH terms; sampling strata and priority metadata remain
local provenance. Validate one attempt locally with the exact visible UI model
label and the actual execution time:

```bash
article-blueprint validate-web-calibration-batch \
  --db "$ARTICLE_BLUEPRINT_DATA/processed/metadata.sqlite3" \
  --manifest "$ARTICLE_BLUEPRINT_DATA/result/step3/calibration/web_batches/BATCH_ID/manifest.json" \
  --output "$ARTICLE_BLUEPRINT_DATA/result/step3/calibration/web_batches/BATCH_ID/output_raw.txt" \
  --model-display-name "VISIBLE CHATGPT UI LABEL" \
  --operator "OPERATOR NAME" \
  --executed-at "2026-09-03T12:00:00Z" \
  --fresh-chat-confirmed
```

Malformed output is never repaired or overwritten. Retain it and validate a
retry from a different raw-output path with `--attempt 2` (then 3, and so on).
Validation records every failed and valid attempt separately and imports only
complete schema-valid records. It does not mark calibration complete or relax
the independent human-reference and recall gates.

An additional reviewed amendment,
`docs/STEP3_AUTOMATED_CHATGPT_WEB_EXECUTION_AMENDMENT.md`, defines a controlled
Chrome UI route for user-authorized upload/read/save automation. It remains
Web-UI-only and stops on login, bot checks, unexpected navigation, or any
failure; it does not authorize an API or bypass access controls.

Set `ARTICLE_BLUEPRINT_DATA` to a directory outside this repository. In the
Stelligen workspace the canonical location is configured through
`BIOWORKSPACE_ROOT`:

```bash
export ARTICLE_BLUEPRINT_DATA="${BIOWORKSPACE_ROOT}/DATA/1.Databases/article_blueprint_os"
```

Do not put the SQLite database, downloaded PDFs, API responses, or exports in
this repository. See the [dataset manifest](datasets/cancer_computational_omics_corpus_v1/dataset.md).

## Journal policy

The v1 registry separates `Gold`, `Silver`, `Methods`, and `Supplementary`
whitelist tiers and maintains an explicit journal/publisher-family blacklist.
Pure review journals are not enumerated. Tiers control retrieval priority, not
automatic paper inclusion. See [`config/journals.json`](config/journals.json)
and [`config/journal_blacklist.json`](config/journal_blacklist.json).

## Screening contract

Deterministic rules only raise candidates; a missing keyword is never an
exclusion. Structured LLM screening and human figure/full-text review are
separate, provenance-bearing decisions. A seeded 10% sample of LLM `NO`
decisions is reserved for false-negative auditing.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Every change is developed on a branch and submitted as a GitHub PR. Nothing is
merged without explicit user approval for that PR.
