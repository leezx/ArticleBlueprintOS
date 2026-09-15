# Project Summary — ArticleBlueprintOS

## Founding question

Can we build a near-exhaustive, auditable 2023-present corpus of high-level,
computationally led cancer-omics original research and extract reusable article
blueprints from it?

## Status

Engineering is `55%` complete against the charter's five-step definition of
100%. Step 2 is closed; Step 3's 600-record Web model-execution phase is
complete, while single-reviewer provisional annotation and calibration
assessment remain open. Corpus/scientific readiness remains `0%`: no paper has
received human review, been included, or been downloaded.

Step 1 was approved and merged as PR #1. The Step 2 runner and two
evidence-based PubMed partitioning amendments were reviewed and merged in
PRs #2–#4. The full historical backfill now has 67/67 completed journals,
195,706 distinct metadata records, and zero full-window coverage
discrepancies. Its aggregate results were approved and merged in PR #5.
Step 3's design, calibration-sample infrastructure, manual Web amendment,
bridge implementation, controlled-browser workflow, and automated-browser
audit trail were approved and merged in PRs #6–#12. Calibration
`425cf5b3-b150-43ed-80bf-b9226397e73b` has now completed the model-execution
phase for all 30 deterministic Web packets (600 records) under the canonical
data root. First-attempt validity was 25/30 (83.3%); five batches required a
retry, including one that required a third attempt, for 6 failed attempts and
36 total attempts. Final schema-complete coverage is 600/600 records, batch
completion is 30/30, and the batch retry rate is 5/30 (16.7%). The validated
model output assigned 144 `YES`, 36 `MAYBE`, and 420 `NO` decisions.

Attempt-level provenance in the external SQLite database records prompt
version, visible model label, provider route, execution mode, software
revision, batch size, input/output paths and checksums, timestamps, status and
errors. Automated-browser attempts additionally record wrapper version and
checksum; the canonical wrapper is `ABOS-WEB-WRAPPER-v1`. Validated screens use
prompt `v1` and visible model label `5.6sol high`. Model identity precision is
`ui-display-name-only`; no backend or API model identifier was inferred.
Temperature and maximum output tokens were not exposed by the ChatGPT Web UI
and are recorded as `unavailable_not_exposed_by_ui`. Attempt provenance also
records operator, fresh-chat confirmation, and batch/attempt identity. Human
reference review has not started, so these are prioritization labels rather
than final corpus exclusions, and this milestone does not mean that
calibration has passed.
Because only one human reviewer is currently available, the active Step 3
amendment uses a blinded single-reviewer provisional reference plus a delayed
60-record repeat pass. It explicitly accepts lower evidentiary confidence and
does not describe the result as a gold standard, consensus, independent human
validation, or adjudicated reference standard.

## What's been answered

- **v1 scope**: a reviewed Gold/Silver/Methods/Supplementary whitelist,
  2023-01-01 onward, cancer × omics,
  computational/data-led original research.
- **system architecture**: journal-first enumeration → immutable Master
  Universe → deterministic priority flags → structured LLM decisions → human
  false-negative audit → full-text/figure triage → blueprint extraction.
- **retrieval boundary**: metadata first; no bulk full-text retrieval before a
  paper-level review list exists.
- **registry reachability**: all 67 non-review whitelist entries returned
  nonzero 2025 PubMed counts after correcting one NLM journal-title query. See
  `docs/STEP1_MASTER_UNIVERSE_RESULTS.md`.

## Progress by workstream

| Workstream | Weight | Completion | Weighted progress | Next gate |
|---|---:|---:|---:|---|
| Registry and pipeline foundation | 20% | 100% | 20% | Prospective maintenance later |
| Historical backfill and coverage | 25% | 100% | 25% | Prospective maintenance later |
| LLM calibration and human audit | 20% | 50% | 10% | Build the single-reviewer provisional reference and evaluate its operational gates |
| Full-text triage and retrieval | 15% | 0% | 0% | Reviewed paper list |
| Blueprint extraction and updates | 20% | 0% | 0% | Included full-text corpus |

## What's still open

- Complete one blinded review of all 600 calibration records, followed after
  at least seven days by a deterministic blinded repeat of 60 records and
  documented self-reconciliation — not started.
- Compute the benchmark and stratified weighted recall, 10,000-bootstrap 95%
  confidence interval, per-stratum recall with Clopper-Pearson intervals,
  false-negative rate, intra-rater stability, and error review. These are
  provisional operational estimates, not independent human validation.
  Full-corpus queue generation remains blocked until weighted positive recall
  is at least 0.95 and every amended Step 3 gate passes.
- Retrieve lawful full text for reviewed inclusions — not started.
- Validate blueprint extraction and prospective updates — not started.
- Add baseline CI, a non-blocking Step 1 review observation.

## Steps closed so far

- Step 1 — Master Universe and screening foundation: merged in PR #1 at
  `90ab9f0812920caca7df9d4ad90c2723e24ea7e2` after external `APPROVE` review.
- Step 2 — Historical backfill and coverage validation: merged in PR #5 at
  `3b481b61696e7349836cbbd7673adb6ba9c8c37a` after external `APPROVE` review.

## Scope boundaries

See `docs/PROJECT_CHARTER.md`. AIDD, drug repurposing, pure algorithm papers,
pure imaging AI, reviews, and experimental-led mechanism papers are deferred.
