# Project Summary — ArticleBlueprintOS

## Founding question

Can we build a near-exhaustive, auditable 2023-present corpus of high-level,
computationally led cancer-omics original research and extract reusable article
blueprints from it?

## Status

Engineering is `55%` complete against the charter's five-step definition of
100%. Step 2 is closed; Step 3's 600-record Web calibration execution is
complete, while human audit remains open. Corpus/scientific readiness is
`10%`: all calibration papers have received a validated structured LLM screen,
but no paper has received human audit, been included, or been downloaded.

Step 1 was approved and merged as PR #1. The Step 2 runner and two
evidence-based PubMed partitioning amendments were reviewed and merged in
PRs #2–#4. The full historical backfill now has 67/67 completed journals,
195,706 distinct metadata records, and zero full-window coverage
discrepancies. Its aggregate results were approved and merged in PR #5.
Step 3's design, calibration-sample infrastructure, manual Web amendment,
bridge implementation, controlled-browser workflow, and automated-browser
audit trail were approved and merged in PRs #6–#12. Calibration
`425cf5b3-b150-43ed-80bf-b9226397e73b` has now completed all 30 deterministic
Web packets (600 records) under the canonical data root. All 30 attempts passed
schema and manifest validation and were imported with execution provenance.
The model assigned 144 `YES`, 36 `MAYBE`, and 420 `NO` decisions. Human audit
has not started, so these are prioritization labels rather than final corpus
exclusions.

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
| LLM calibration and human audit | 20% | 60% | 12% | Human-label calibration sample and audit model decisions |
| Full-text triage and retrieval | 15% | 0% | 0% | Reviewed paper list |
| Blueprint extraction and updates | 20% | 0% | 0% | Included full-text corpus |

## What's still open

- Human-label the calibration sample and measure `NO` false negatives — not started.
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
