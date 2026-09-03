# Step 3: LLM screening calibration and human audit — design

## Purpose and boundary

Step 3 turns the immutable Step 2 Master Universe into a reviewed queue for
later full-text triage. It evaluates a structured LLM classifier against
metadata-only human judgments before any full-corpus model run, then runs the
locked classifier only if its calibration acceptance gates pass.

This step does not alter the 195,706-record Master Universe, change the
journal registry, make final corpus-inclusion decisions, retrieve full text,
or upload article metadata outside the user-authorized model route. The LLM is
a queue-prioritization tool, never the inclusion authority.

All article-level queues, model inputs/outputs, reviewer worksheets, and
aggregate reports live outside git:

```text
/Volumes/Stelligen_SSD/Stelligen/DATA/1.Databases/article_blueprint_os/
├── processed/metadata.sqlite3
├── result/step3/calibration/
├── result/step3/llm-queues/
└── result/step3/human-audit/
```

The repository holds only the versioned prompt/schema, code, manifests without
article payloads, tests, and aggregate results.

## Locked classifier contract

The execution must use `prompts/llm_screen_v1.md` and
`schemas/llm_screen.schema.json`, identified as `prompt_version=v1`. The
runner supplies `model`, `prompt_version`, and ISO-8601 `screened_at`; the
model must return exactly one validating JSON object per PMID.

Before execution, record the exact model identifier, provider route,
temperature, maximum output tokens, batch size, input and output file
SHA-256 values, operator, and software revision. The model identifier is not
chosen in this design: it is a run-time, user-authorized provenance field.

Malformed records, duplicate PMIDs, unknown PMIDs, missing output records, or
extra output records fail the batch. Failed batches are retained with an error
state and may be retried as a new auditable attempt; no prior output is
overwritten.

## Calibration sample and human reference standard

Build a deterministic 600-record calibration set from the completed Step 2
database using seed `article-blueprint-os-step3-calibration-v1`:

| Stratum | Records | Rationale |
|---|---:|---|
| Deterministic candidate-priority | 300 | Enrich likely in-scope literature and boundary cases. |
| Not candidate-priority, original/unclear publication type | 200 | Detect keyword-driven false negatives. |
| Obvious non-original publication type | 100 | Verify review/commentary exclusion behavior. |

Within each stratum, rank PMIDs by SHA-256 of `seed:pmid` and take the first
eligible records. Persist stratum, seed, rank, query definition, and selection
time. The calibration set is not used to train or fine-tune the model.

Two human reviewers independently label every calibration record from the
same PubMed metadata shown to the model. They use the locked
`docs/STEP3_HUMAN_ANNOTATION_RUBRIC_V1.md`, record every schema dimension, a
provisional `YES`/`MAYBE`/`NO` relevance label, confidence, and a concise
evidence citation to title, abstract, MeSH, or article type. They must choose
`unclear` rather than infer unstated biology. Disagreements on relevance or
computational centrality are adjudicated by a named third reviewer; the
adjudicated record is the reference standard. All individual judgments and
adjudications are written to the external SQLite provenance tables.

## Calibration metrics and gates

Treat human `YES` and `MAYBE` together as the recall-positive class. The
fixed 300/200/100 mixture is an error-discovery benchmark, not a natural
sample of the Master Universe. Do not present its unweighted recall as corpus
recall.

At sample selection, persist each stratum's Master-Universe population size
`N_h` and calibration sample size `n_h`. Report both the benchmark metrics and
the stratified population estimate:

```text
estimated population recall =
  Σ_h (N_h / n_h) × true-positive LLM YES-or-MAYBE_h
  ───────────────────────────────────────────────────
  Σ_h (N_h / n_h) × adjudicated-positive_h
```

Use 10,000 deterministic stratified bootstrap replicates (with a recorded
seed) for its 95% interval. This is an estimate of false-negative risk under
the defined strata, not a claim of observed recall for every record in the
195,706-record universe. Report, with exact numerators and denominators,
overall benchmark, weighted estimate, and per-stratum:

- positive-class recall and precision;
- `NO` false-negative count and rate;
- exact agreement for disease, study, primary contribution, and relevance;
- weighted agreement for computational centrality (within one score vs exact);
- first-attempt JSON/schema validity, final schema-complete coverage, retry
  rate, and batch completion rate; and
- human-human agreement before adjudication.

The full-corpus model run is permitted only if all of these hold:

1. final schema-complete coverage is 100% (exactly one valid result per input
   PMID after auditable retries), and first-attempt validity plus retry rate
   are reported without being hidden by retries;
2. weighted estimated positive-class recall is at least 0.95, and the
   unweighted benchmark recall is reported only as a benchmark metric;
3. per-stratum recall is at least 0.90 only when the stratum contains at
   least 20 adjudicated positives. Smaller-positive strata are explicitly
   labeled underpowered and reported with a two-sided 95% Clopper-Pearson
   interval; they cannot independently establish a passing recall claim;
4. no systematic failure mode is identified in a calibration error review;
5. the human adjudication record and calibration report are complete; and
6. the Step 3 implementation PR is approved.

If any gate fails, do not run the full corpus. Revise the prompt, schema, or
workflow in a new reviewed version and repeat calibration with a new seed and
explicit comparison to the failed version.

## Full-corpus execution after calibration

Export the metadata queue only to the approved external path and process
batches of at most 100 records. Import only schema-valid, complete batches
into `llm_screens`, preserving per-record model/prompt/timestamp provenance.
The source Master Universe remains unchanged. A resumable manifest records
each batch's input PMID set, input/output checksum, attempt, status, and
error.

After all batches complete, create human-review queues for every latest-model
`YES`, every `MAYBE`, and a deterministic 10% sample of latest-model `NO`
decisions using `sample_no_audit`. The sample seed, population, hash ranks,
and exact ceiling-based sample size are persisted. Human review remains a
metadata-level provisional decision; a paper becomes included only after the
later full-text/figure-triage step.

## Outputs and acceptance gates

Step 3 produces external calibration and audit artifacts plus a small,
aggregate-only committed results document. It may close only when:

- calibration passes the gates above and its failures (if any) are reported;
- every Master-Universe PMID has one latest schema-valid LLM record from the
  accepted run;
- all latest-model `YES` and `MAYBE` records have human review;
- the seeded 10% latest-model `NO` sample has human review and its false
  negative findings are reported;
- the aggregate results document, external paths, prompt/model provenance,
  and tests/CI are documented; and
- no payload or article-level export is committed to git.
