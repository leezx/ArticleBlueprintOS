# Step 3 amendment: manual ChatGPT Web calibration execution

## Trigger and scope

No paid model API is available. This amendment authorizes a controlled,
human-mediated ChatGPT Web route for the existing 600-record calibration only.
It does not authorize a full-corpus run, browser automation, API use, or any
automatic transmission of article metadata.

This amendment supplements, rather than rewrites, the approved Step 3 design.
All existing calibration gates, human-reference requirements, recall
definitions, and stop-on-failure rules remain unchanged.

## Provider and model provenance

Every attempt records `provider_route="ChatGPT Web UI"` and
`execution_mode="manual"`. ArticleBlueprintOS makes no API call and performs
no browser automation. A human operator copies one locally generated packet
into a fresh ChatGPT conversation, then saves returned text verbatim to the
external result path.

The operator supplies the exact visible `model_display_name`; code must never
invent a backend/API identifier. When only a UI label is visible, provenance
records `model_identifier_precision="ui-display-name-only"`. Each attempt
also records executed time, operator, prompt version, software revision,
batch/attempt identity, input/output SHA-256, and fresh-chat confirmation.
For this Web route, hidden parameters not exposed by the UI are recorded as
`unavailable_not_exposed_by_ui` (including temperature and maximum output
tokens), never inferred. This limitation is reported in aggregate provenance
and is not itself a calibration acceptance gate.

## Packet contract

The calibration sample is split deterministically into batches of 20 records
(never more than 50 without a new reviewed amendment). A batch ID is derived
from calibration ID, ordered PMIDs, and prompt version; a UUID alone is not a
valid identity. Packets stay outside git at:

```text
${ARTICLE_BLUEPRINT_DATA}/result/step3/calibration/web_batches/<batch_id>/
```

Each contains `manifest.json`, `input.jsonl`, and `web_prompt.txt`; raw output
and validation results are added externally after manual operation. Manifests
hold ordered PMIDs, strata, record count, checksum, prompt/schema versions,
software revision, attempt, timestamp, and lifecycle status.
The model-visible `input.jsonl` is a strict allowlist containing only PMID,
DOI, title, abstract, article types, and MeSH terms. Sampling strata,
priority flags, journal keys, ranks, and population counts remain local
provenance only and must never be included in the Web prompt.

`web_prompt.txt` embeds the semantic requirements of `llm_screen_v1.md` and
requires metadata-only classification, same-order JSONL, exactly one object
per input PMID, no markdown/prose, no omissions/additions, and no guessed
model provenance. Trusted model/operator provenance is injected locally only
after validation.

Validation is explicitly two-stage. Stage A validates raw Web semantic JSONL
against a Web semantic-output contract containing PMID and classifier fields
only; it forbids model-generated provenance. Stage B locally injects trusted
operator provenance (`model`, `prompt_version`, and `screened_at` only), then
validates the enriched object against the existing `llm_screen.schema.json`
before import into `llm_screens`. Web-route execution provenance
(provider route, UI label, operator, unavailable parameters, fresh-chat flag,
batch/attempt identity, paths, and checksums) remains exclusively in the
batch manifest/attempt record and is linked by batch/attempt, never added to
the article-level JSON object.

## Fresh-chat, immutability, and validation

Each batch requires a fresh conversation and
`fresh_chat_confirmed=true`; no conversation URL or account/session material is
stored. Operators save `output_raw.txt` verbatim. Malformed output is never
repaired: it is checksummed, retained as failed, and retried in a new auditable
attempt.

Local validation fails closed on invalid JSON, markdown/prose wrappers,
schema violations, wrong count, duplicate/missing/unexpected/reordered PMIDs,
wrong prompt version, invalid provenance, or any path inside git. A valid
attempt preserves raw output, records checksum and trusted operator provenance,
and imports only validated records without modifying the Master Universe.

## Execution boundary

This amendment and its implementation may create external packets and validate
synthetic outputs. Validation of real operator-saved calibration outputs begins
only after both amendment and implementation PRs are separately approved. They
may not submit data to ChatGPT,
call a model API, claim calibration passed, conduct human adjudication, run the
195,706-record corpus, retrieve full text, or make final paper-inclusion
decisions. Real 600-record calibration requires this amendment and its
implementation to be reviewed and explicitly approved.
