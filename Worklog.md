# Worklog — ArticleBlueprintOS

This log is append-only in spirit. Add one entry after each merged PR, including
what changed, why, real findings, review history, and the merge commit.

## Progress tracker

| Step | Status | PR | Notes |
|---|---|---:|---|
| 1. Master Universe and screening foundation | merged | [#1](https://github.com/leezx/ArticleBlueprintOS/pull/1) | Approved; merge commit `90ab9f0` |
| 2. Historical backfill and coverage validation | merged | [#5](https://github.com/leezx/ArticleBlueprintOS/pull/5) | 67/67 journal backfill, full-window reconciliation, and deterministic screening results approved |
| 3. LLM screening calibration and human audit | not started | — | Measure false-negative rate |
| 4. Full-text triage and lawful retrieval | not started | — | Small reviewed batches only |
| 5. Blueprint extraction and prospective updates | not started | — | Living corpus and architecture library |

Overall: `45%` engineering completion against the charter definition of 100%;
scientific corpus readiness remains `0%` until structured screening and human
audit results exist.

## 2026-09-02 — Step 1 merged

- **PR**: [#1 — Step 1: build journal-first Master Universe foundation](https://github.com/leezx/ArticleBlueprintOS/pull/1)
- **Merge commit**: `90ab9f0812920caca7df9d4ad90c2723e24ea7e2`
- **Delivered**: 67-journal registry, blacklist policy, PubMed enumeration and
  XML parsing, SQLite provenance, deterministic high-recall screening,
  structured LLM/audit contracts, and 15 unit tests.
- **Validation**: all 67 registry entries returned nonzero 2025 PubMed counts;
  the Cancer Epidemiology, Biomarkers & Prevention query alias was corrected.
- **External review**: `APPROVE`; no P0/P1 findings. Non-blocking observations
  were to add CI and to describe the deterministic NO sample precisely.
- **Data boundary**: no historical payload or full text was acquired in Step 1.

## 2026-09-02 — Step 2 runner merged

- **PR**: [#2 — Step 2: add resumable historical backfill runner](https://github.com/leezx/ArticleBlueprintOS/pull/2)
- **Merge commit**: `5b2daad0aa8531bdecaca3cecf30a09427452a43`
- **Delivered**: resumable backfill provenance, aggregate coverage reports,
  additive schema v2, synthetic parser fixtures, and Python 3.11/3.12 CI.
- **Review cycle**: initial `REQUEST CHANGES` for a missing package install;
  the repaired head passed both CI jobs and received `APPROVE`.
- **Execution finding**: the first real run failed closed when Nature exceeded
  PubMed's 10,000 accessible-result limit. No partial journal was accepted.

## 2026-09-02 — PubMed large-query partition fix merged

- **PR**: [#3 — Step 2: partition PubMed queries above 10,000 records](https://github.com/leezx/ArticleBlueprintOS/pull/3)
- **Merge commit**: `8c0a91d6579f3484ffb6c158c61a56e81546127e`
- **Delivered**: recursive date slicing, slice-level provenance and resume,
  full-window distinct-PMID union validation, additive schema v3, and 20 tests.
- **Review**: `APPROVE`; both Python 3.11 and 3.12 CI jobs passed.
- **Execution finding**: Nature's non-overlapping date ranges produced
  overlapping PMID result sets (slice counts 15,569 vs full count 15,540), so
  raw slice-count additivity is not a valid completeness gate.

## 2026-09-02 — PubMed date-slice overlap correction merged

- **PR**: [#4 — Step 2: allow overlapping PubMed date slices](https://github.com/leezx/ArticleBlueprintOS/pull/4)
- **Merge commit**: `0845f4760516f8a10a4f062cf57b6c9cb3731380`
- **Delivered**: a corrected completeness contract that accepts overlap across
  date slices only when the distinct PMID union equals PubMed's authoritative
  full-window count; resume uses stable slice boundaries rather than volatile
  counts.
- **Review and validation**: external `APPROVE`; Python 3.11 and 3.12 CI
  passed. The correction enabled the same provenance-preserving backfill to
  complete without treating legitimate PubMed date semantics as data loss.

## 2026-09-03 — Step 2 results merged

- **PR**: [#5 — record completed Step 2 backfill results](https://github.com/leezx/ArticleBlueprintOS/pull/5)
- **Merge commit**: `3b481b61696e7349836cbbd7673adb6ba9c8c37a`
- **Delivered**: aggregate-only documentation of a completed 67-journal
  backfill, 195,706 distinct metadata records, 67/67 authoritative
  full-window reconciliations, 0 full-window discrepancies, and deterministic
  screening for every record.
- **Review and validation**: external `APPROVE`; GitHub Actions Python 3.11
  and 3.12 tests passed. The 159 annual diagnostic discrepancies remain
  explicitly carried forward as provenance observations, not hidden or forced
  into an invalid completeness rule.
