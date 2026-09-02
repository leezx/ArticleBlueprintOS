# Project Charter — ArticleBlueprintOS

## Part 1 — Project definition

- **Project name / repo**: `ArticleBlueprintOS` — GitHub repository under the
  authenticated `leezx` account.
- **Founding question**: Can we build a near-exhaustive, auditable corpus of
  2023-present high-level cancer-omics original research in which computation
  or data analysis is central to the evidence architecture, then reverse
  engineer reusable successful article blueprints from the included papers?
- **Definition of 100%**: all journals in the locked multi-tier v1 whitelist are enumerated from 2023-01-01
  through the locked historical cutoff; metadata coverage is reconciled;
  deterministic and structured LLM screening has completed; all `YES` and
  `MAYBE` records plus a seeded 10% sample of `NO` records have received human
  audit; included papers have lawful full text or a documented access status;
  each included paper has a validated blueprint extraction; and a prospective
  update workflow is documented and tested.
- **Explicit non-goals / deferred scope**: AIDD, drug repurposing, pure
  algorithm benchmarks without substantive cancer discovery, molecular
  docking, protein structure, generative chemistry, pure pathology AI, pure
  radiology AI, reviews/commentaries, and experimental-led mechanism papers.
  Broadening beyond the reviewed whitelist is deferred until v1 calibration;
  pure review journals are excluded from enumeration.
- **Review policy**: every implementation step is submitted as a GitHub PR.
  The persistent ChatGPT review URL has not yet been supplied; until it is,
  GitHub PR review remains the formal gate. No merge is permitted without the
  user's explicit approval for the specific PR.
- **Compute location**: local for metadata I/O and lightweight screening;
  Argos only if later extraction or model workloads become heavy.

## Part 2 — Standing operating rules

### 2.1 Repository shape

```text
ArticleBlueprintOS/
├── README.md
├── Worklog.md
├── config/                 # small, reviewed registries and rules
├── datasets/               # manifests only; no payloads
├── docs/                   # charter, designs, results, summary
├── prompts/                # versioned classifier/extractor prompts
├── schemas/                # machine-readable data contracts
├── scripts/<NN>_<step>/    # thin runnable entry points
├── src/article_blueprint_os/
└── tests/
```

### 2.2 Step lifecycle

1. Lock a design document before data acquisition or compute.
2. Create one branch per step from the latest `main`.
3. Implement with small, verifiable commits and real tests.
4. Push and open a GitHub PR against `main`.
5. Review findings against committed code and real evidence; do not accept or
   reject feedback by intuition.
6. Iterate until approval, report the final head, and stop.
7. Merge only after a separate, explicit user confirmation for that PR.
8. After merge, append `Worklog.md` and update the project summary when the
   step closes a milestone.

### 2.3 Data separation

No database, API response, PDF, HTML full text, extracted text, cache, or bulk
export may be written under this repository. In the Stelligen workspace, the
canonical payload root is:

```text
${BIOWORKSPACE_ROOT}/DATA/1.Databases/article_blueprint_os/
├── link.md
├── raw/          # immutable source responses and lawful full text
├── processed/    # versioned SQLite databases and normalized exports
└── result/       # screening, audit, and blueprint outputs
```

The repo stores code, schemas, manifests, source URLs, checksums, and small
aggregate summaries only. Downloads go directly to the payload root. Every
retrieved file must have a source, access status, byte size, format check, and
checksum. Raw inputs are append-only.

### 2.4 Retrieval and access

- Metadata enumeration may use NCBI PubMed E-utilities and must respect rate
  limits, retries, and source provenance.
- Full text starts only from a paper-level list reviewed after screening.
- Prefer legitimate open-access routes. Otherwise reuse only the user's
  authorized institutional browser session.
- Never bypass paywalls, CAPTCHAs, bot checks, DRM, SSO, or two-factor
  authentication. Never read or store credentials or browser session data.
- Work in batches of 5–10 papers (15–20 maximum) and preserve canonical access
  statuses in the full-text manifest.

### 2.5 Recall and decision semantics

The Master Universe is immutable with respect to screening: no classifier may
delete records. Deterministic rules can only set a candidate flag. The LLM must
emit the structured dimensions defined in the schema; it cannot be the final
inclusion authority. Human reviewers inspect every `YES`, every `MAYBE`, and a
seeded 10% sample of `NO`. A paper is finally included only after full-text or
figure triage confirms computational story centrality.

### 2.6 Documentation and reporting

Design and results are separate documents. Do not edit a design retroactively
to make it match real results. Report unresolved gaps and negative findings.
Track engineering progress separately from corpus/scientific readiness, and
always state the 100% endpoint before assigning a percentage.
