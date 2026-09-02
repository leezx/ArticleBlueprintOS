# Project Summary — ArticleBlueprintOS

## Founding question

Can we build a near-exhaustive, auditable 2023-present corpus of high-level,
computationally led cancer-omics original research and extract reusable article
blueprints from it?

## Status

Engineering is `8% → 16% (+8%)` complete against the charter's five-step
definition of 100%. Corpus/scientific readiness is `0%`: the historical
backfill has not run and no paper has been included or downloaded.

The v1 scope, first-step data contracts, implementation, unit tests, and live
PubMed registry smoke test are complete. The immediate milestone is GitHub PR
review; the historical backfill remains unrun.

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
| Registry and pipeline foundation | 20% | 80% | 16% | PR approval and merge |
| Historical backfill and coverage | 25% | 0% | 0% | Run 2023-cutoff enumeration |
| LLM calibration and human audit | 20% | 0% | 0% | Produce reviewed queues |
| Full-text triage and retrieval | 15% | 0% | 0% | Reviewed paper list |
| Blueprint extraction and updates | 20% | 0% | 0% | Included full-text corpus |

## What's still open

- Review and merge Step 1 — implementation complete, PR pending.
- Run the complete historical backfill and reconcile coverage — not started.
- Calibrate LLM screening and measure `NO` false negatives — not started.
- Retrieve lawful full text for reviewed inclusions — not started.
- Validate blueprint extraction and prospective updates — not started.
- Record a persistent ChatGPT PR-review conversation URL — awaiting user input,
  but not blocking GitHub PR creation.

## Steps closed so far

No step has been merged.

## Scope boundaries

See `docs/PROJECT_CHARTER.md`. AIDD, drug repurposing, pure algorithm papers,
pure imaging AI, reviews, and experimental-led mechanism papers are deferred.
