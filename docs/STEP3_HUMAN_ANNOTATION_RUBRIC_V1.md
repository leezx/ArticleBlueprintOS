# Step 3 human annotation rubric v1

Use this rubric only with title, abstract, MeSH terms, and PubMed article
types. It is the human semantic contract corresponding to
`schemas/llm_screen.schema.json`; it does not authorize inference from full
text, figures, author reputation, or journal tier. Cite the metadata evidence
for each non-`unclear` judgment.

## General rules

- Mark `unclear` when the supplied metadata does not establish a dimension.
- Record original research rather than a review only when article type or the
  abstract describes a study that generated or analyzed evidence.
- `YES`, `MAYBE`, and `NO` are queue-prioritization labels, not final corpus
  inclusion. Prefer `MAYBE` where computational centrality or disease scope is
  plausible but unresolved.
- Do not use absent keywords alone to issue `NO`.

## Dimension rules

| Field | Decision rule |
|---|---|
| `disease` | `cancer` requires a malignant tumor, cancer cohort, cancer model, or cancer clinical context stated in metadata. Use `non-cancer` for an explicit non-malignant focus; otherwise `unclear`. |
| `study` | Use `review`/`commentary` when publication type or wording identifies it. Use `method` when the primary claim is a tool or workflow. Use `original research` for data analysis or evidence-generating studies; otherwise `unclear`. |
| `primary_contribution` | Select one main claim: biological/clinical discovery, computational method, experimental mechanism, resource/atlas, or `other`. A mechanism experiment stays `experimental mechanism` even if it includes supporting omics. |
| `data_modalities` | Select only explicitly stated modalities. Map RNA sequencing without single-cell wording to `bulk RNA`; use `other` for a stated molecular modality outside the controlled list. Never infer a modality from a disease name. |
| `computational_centrality` | `0`: absent/peripheral descriptive statistics; `1`: computation supports a mainly experimental/clinical claim; `2`: computation and another evidence stream co-lead; `3`: omics/data analysis is the primary evidence engine or central deliverable. |
| `new_experimental_data` | `none`: public/previously generated data only; `limited`: small validation or ancillary experiments; `substantial`: newly generated experiments/data underpin the main claim; `unclear`: provenance is unstated. |
| `public_data_reuse` | `major`: reused public data are central to the main evidence; `minor`: a secondary validation/comparison; `none`: no reuse stated; `unclear`: provenance is unstated. |
| `relevance` | `YES`: cancer-omics original research or a cancer-applied method/resource where computation is clearly central. `MAYBE`: likely relevant but ambiguous. `NO`: clearly out of scope, including reviews/commentaries, pure wet-lab mechanism, pure pathology/radiology AI, AIDD/docking/structure/generative chemistry, or a method-only benchmark without substantive cancer discovery. |

## Adjudication

The third reviewer sees both independent records and resolves every
disagreement in `relevance` or `computational_centrality`; other differences
remain recorded and are summarized as agreement metrics. The adjudicator must
select one allowed value, preserve evidence citations, and state a brief
metadata-grounded reason. The adjudicated values form the calibration
reference standard.
