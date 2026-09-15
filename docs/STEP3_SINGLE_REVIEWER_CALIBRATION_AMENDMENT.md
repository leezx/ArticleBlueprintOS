# Step 3 amendment: single-reviewer provisional calibration

## Status and authority

This amendment changes only the human-reference and calibration-gate portions
of `STEP3_LLM_CALIBRATION_AND_HUMAN_AUDIT_DESIGN.md`. It applies because the
project currently has one available human reviewer. The original two-reviewer
plus third-reviewer adjudication design remains the preferred validation
standard and is not represented as completed.

The 600-record model execution, immutable Master Universe, classifier schema,
provenance requirements, full-corpus batching, lawful-access boundary, and
final human-inclusion authority are unchanged.

## Explicit evidence limitation

One reviewer's labels are a **single-reviewer provisional reference**, not a
gold standard, independent consensus, or adjudicated reference standard. This
design cannot estimate human-human agreement, inter-rater reliability, or the
error rate of the reviewer. Repeated labels from the same person measure only
intra-rater stability and do not replace an independent second opinion.

All reports, database fields, CLI output, and committed summaries must use the
term `single-reviewer provisional reference`. They must not use `gold
standard`, `adjudicated reference standard`, `consensus`, or `independent
human validation` for this dataset. Performance estimates are operational and
provisional; they are not publication-grade validation claims.

## Primary review protocol

The available reviewer labels all 600 calibration records using
`STEP3_HUMAN_ANNOTATION_RUBRIC_V1.md` and only the PubMed metadata available to
the model. The review interface must hide:

- the model's labels, confidence, and rationale;
- calibration stratum and deterministic priority flags; and
- any aggregate model-performance result that could anchor a decision.

For every record, store reviewer identity, rubric version, review pass,
blinding status, timestamp, every required schema dimension, relevance,
confidence, evidence note, and an explicit `needs_recheck` flag. Missing or
ambiguous evidence must be labeled `unclear` or `MAYBE`, not guessed. The
reviewer may pause and resume; record order and saved decisions must remain
stable and auditable.

## Intra-rater quality-control pass

After the primary pass is complete, wait at least seven calendar days before
a blinded repeat review of 60 records. Select these records deterministically
with seed `article-blueprint-os-step3-single-reviewer-repeat-v1`, comprising
30 candidate-priority, 20 non-candidate original/unclear, and 10 obvious
non-original records. Re-randomize their presentation order and hide the
reviewer's first-pass labels.

Report exact and class-collapsed agreement for relevance, exact agreement for
study type, and exact plus within-one agreement for computational centrality.
Every relevance disagreement, every computational-centrality difference
greater than one, and every record marked `needs_recheck` receives a documented
final self-reconciliation. The final value remains a single-reviewer decision;
self-reconciliation is not adjudication.

## Provisional metrics and operational gates

Compute the metrics required by the original design against the provisional
reference, retaining exact numerators, denominators, stratum weights, the
10,000-replicate deterministic bootstrap, and per-stratum Clopper-Pearson
intervals. Replace `adjudicated-positive` with `provisional-reference-positive`
in metric labels. Omit human-human agreement and explicitly state that it is
unavailable under the one-reviewer design.

A full-corpus model run may proceed only as a **provisional queue-generation
run**, not as validated automated exclusion, when all of these hold:

1. all 600 primary reviews and all 60 repeat reviews are complete with their
   provenance;
2. relevance agreement between the two passes is at least 0.90, and all
   material repeat-pass disagreements are reconciled and reported;
3. final schema-complete model coverage is 100%, with first-attempt validity
   and retry rate reported;
4. weighted estimated positive-class recall against the provisional reference
   is at least 0.95;
5. the original per-stratum recall, uncertainty, and systematic-error gates
   pass after replacing adjudicated labels with provisional labels; and
6. the single-reviewer calibration report and its limitations receive PR
   approval.

Failure of any gate blocks the full-corpus run and requires a reviewed prompt,
schema, workflow, or sampling revision. Passing these gates does not establish
classifier validity against independent human truth.

## Downstream safeguards

The classifier remains a prioritization tool. No `NO` decision may delete,
hide, or permanently exclude a Master-Universe record. After the provisional
full-corpus run, the same reviewer may audit all `YES`, all `MAYBE`, and the
seeded 10% sample of `NO` records, but those decisions remain single-reviewer
provisional metadata judgments. Final inclusion still requires later
full-text or figure triage.

Reports must keep the following limitations visible:

- only one human reviewer was available;
- review errors may be correlated across the primary and repeat passes;
- no inter-rater agreement or independent adjudication was measured;
- recall and false-negative estimates inherit single-reviewer label error; and
- a second independent reviewer may change the reference labels and reported
  performance.

## Future upgrade path

When another qualified reviewer becomes available, preserve all existing
single-reviewer provenance and run an independent blinded review. A named
third reviewer must adjudicate relevance and computational-centrality
disagreements before the project describes the result as an adjudicated
reference standard. Recompute every calibration metric and version the report;
do not overwrite the provisional results.
