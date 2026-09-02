# Step 2: Historical backfill and coverage validation — design

## Scope and locked inputs

Step 2 materializes the complete journal-first PubMed Master Universe for the
67-entry v1 registry and reconciles its coverage. The historical window is
locked to `2023-01-01` through `2026-09-02`, inclusive. The registry version,
date window, software commit, PubMed queries, run identifiers, counts, raw XML
checksums, and failures must be retained.

This step does not call an LLM, make final paper-inclusion decisions, retrieve
full text, or change the whitelist. All PubMed publication types remain in the
Master Universe.

## Payload boundary

All payloads are written beneath the external data root:

```text
${BIOWORKSPACE_ROOT}/DATA/1.Databases/article_blueprint_os/
├── raw/pubmed/                 # immutable XML batches by enumeration run
├── processed/metadata.sqlite3 # authoritative metadata/provenance database
└── result/step2/               # machine-readable coverage exports
```

No XML, SQLite, JSONL export, abstract corpus, or other payload is committed to
git. The repository may contain only aggregate results without article-level
content.

## Backfill orchestration

1. Create a backfill record with the locked registry, dates, and software
   revision.
2. Enumerate one journal at a time in registry priority order using the Step 1
   exact-journal query and PubMed history API.
3. Link each journal to its enumeration run and persist success or failure.
4. Make the operation resumable: a completed journal is not fetched again
   when the same backfill is resumed; a failed journal may be retried with a
   new enumeration run while its earlier failure remains auditable.
5. Stop the overall run with a failed status if any journal remains failed.
   Never silently report a partial universe as complete.

## Coverage reconciliation

Coverage has three independent gates:

- **Run gate**: for every journal, `fetched_count`, unique PMIDs, and PubMed's
  reported count must agree, as enforced by Step 1.
- **Registry gate**: exactly 67 distinct registry journals must have a linked,
  completed enumeration run for the locked window.
- **Annual gate**: for every journal and calendar-year slice intersecting the
  locked window, independently query PubMed ESearch and compare its count with
  the PMIDs from the linked full-window run whose parsed publication year is
  that year. Differences are retained as discrepancies for investigation; no
  records are deleted or fabricated to force agreement.

The annual comparison is a parser and boundary diagnostic. A discrepancy may
reflect imprecise/Medline publication dates rather than missing retrieval, so
the full-window run gate remains the authoritative completeness criterion.

## Outputs

- A versioned SQLite backfill record and journal/run linkage.
- Immutable raw XML batches with SHA-256 already recorded by Step 1.
- An external JSON coverage report containing aggregate journal/year counts,
  discrepancies, run status, and provenance.
- A small committed Step 2 results document containing only aggregate counts,
  checks performed, unresolved discrepancies, and the payload locations.

## Failure and retry policy

Network, NCBI, parsing, coverage, or filesystem errors are recorded against
the affected journal and fail the backfill. Resume operates only on the same
registry version and locked dates. It skips completed journals, retries failed
or absent journals, and never deletes prior enumeration runs or raw responses.

## Acceptance gates

Step 2 may be approved only when:

- all 67 journals have completed full-window runs;
- each run passes PubMed count and unique-PMID equality;
- every calendar-year coverage cell has been checked and discrepancies are
  explained or explicitly carried forward;
- deterministic screening has run over the full Master Universe without
  deleting any article;
- aggregate results and exact external payload paths are documented;
- unit tests and CI pass; and
- no database, XML, abstract, or article-level export is present in git.
