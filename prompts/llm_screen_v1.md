# Cancer Computational Omics screen — prompt v1

Classify each paper only from the supplied PubMed title, abstract, MeSH terms,
article types, and identifiers. This is a high-recall screening stage, not a
final inclusion decision. Do not infer experiments, modalities, cohorts, or
mechanisms that are not stated. Use `unclear` when evidence is absent.

Return exactly one JSON object per input record, preserving `pmid`, with no
markdown wrapper or extra prose. The object must validate against
`schemas/llm_screen.schema.json`.

Answer these observable dimensions:

- `disease`: `cancer`, `non-cancer`, or `unclear`.
- `study`: `original research`, `review`, `commentary`, `method`, or `unclear`.
- `primary_contribution`: one allowed schema value reflecting the main claim,
  not every secondary result.
- `data_modalities`: one or more allowed schema values explicitly supported by
  the metadata.
- `computational_centrality`: `0` peripheral, `1` supportive, `2` co-leading,
  `3` computation/data analysis appears to be the primary evidence engine.
- `new_experimental_data`: `none`, `limited`, `substantial`, or `unclear`.
- `public_data_reuse`: `none`, `minor`, `major`, or `unclear`.
- `relevance`: `YES`, `MAYBE`, or `NO` for a cancer-omics blueprint corpus in
  which computation/data analysis is central. Prefer `MAYBE` over `NO` when
  the abstract is ambiguous.
- `confidence`: number from 0 to 1 calibrated to the evidence in the supplied
  metadata.
- `rationale`: one concise evidence-based sentence; do not mention hidden chain
  of thought.
- `model`, `prompt_version`, and `screened_at`: provenance fields supplied by
  the calling workflow. Use prompt version `v1`.

In-scope modalities include genomics, transcriptomics, single-cell, spatial,
epigenomics, proteomics, multi-omics, and large-scale molecular profiling.
Pure wet-lab mechanism, clinical trials without substantial omics analysis,
reviews/commentaries, pure pathology or radiology AI, AIDD, docking, protein
structure, generative chemistry, and algorithm-only benchmarks are out of the
v1 corpus. A method paper with a substantive cancer biological application may
be `YES` or `MAYBE`; a method benchmark without such an application is `NO`.

Never use missing keywords as the sole reason for `NO`. Final inclusion is
reserved for human full-text/figure triage.
