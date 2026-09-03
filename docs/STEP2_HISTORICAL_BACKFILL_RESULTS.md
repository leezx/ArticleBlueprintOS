# Step 2: Historical backfill and coverage validation — results

## Locked execution

The v1.1.0, 67-journal Master Universe was enumerated from PubMed for the
inclusive window `2023-01-01` through `2026-09-02`. The authoritative
backfill ID is `c65f9e44-a962-4627-95a4-3d8b9fd63999`.

Payloads are deliberately external to git:

```text
/Volumes/Stelligen_SSD/Stelligen/DATA/1.Databases/article_blueprint_os/
├── raw/pubmed/                  # immutable PubMed XML response batches
├── processed/metadata.sqlite3   # metadata, provenance, decisions, and audits
└── result/step2/coverage.json   # machine-readable aggregate coverage report
```

No article-level metadata, XML, abstract text, or database payload is
committed in this repository.

## Completion and reconciliation

| Check | Result |
|---|---:|
| Registry journals | 67 / 67 completed |
| Full-window PubMed count versus distinct PMID union | 67 / 67 match |
| Full-window discrepancies | 0 |
| Distinct articles in Master Universe | 195,706 |
| Immutable raw XML batches | 1,110 |
| Annual diagnostic checks | 268 |
| Annual diagnostic matches | 176 |
| Annual diagnostic discrepancies carried forward | 159 |

The annual diagnostic count exceeds the number of journal-year cells because
the report stores both full-window and annual checks. The 159 annual
discrepancies are non-blocking, retained provenance observations: PubMed date
matching may use multiple publication-date fields whereas the local parser
stores one canonical publication year. They do not indicate missing records:
every journal passed the authoritative full-window distinct-PMID union check.

Two transient transport failures (`Cell` and `Gastroenterology`) were recorded
as failed attempts and then retried through the same backfill ID. Both retry
runs passed their fetched-count, unique-PMID, and PubMed-reported-count gates;
the final backfill status is `complete` with zero failed journals.

`Nature` crossed PubMed's 10,000-result access boundary. The reviewed
partitioning amendments kept every fetch slice at or below 9,999 results and
accepted legitimate PMID overlap only after the distinct union matched the
full-window PubMed count. The initial runner revision is
`5b2daad0aa8531bdecaca3cecf30a09427452a43`; the execution used the reviewed
partition and overlap corrections merged in `8c0a91d` and `0845f47`.

## Deterministic screening

Rules version `v1.0.0` ran over all 195,706 Master-Universe records without
deleting any record.

| Deterministic outcome | Records |
|---|---:|
| Candidate-priority flag set | 14,603 |
| Not candidate-priority (retained, not excluded) | 181,103 |
| Screen records persisted | 195,706 |

The command also reported 40,227 obvious non-original publication-type
observations. These are retained in the Master Universe and are not final
exclusions; structured LLM screening and human audit remain required by the
charter.

## Validation and next gate

The repository test suite passes with 21 tests, and the reviewed Python 3.11
and 3.12 CI workflow remains the implementation validation. Step 2's data
acceptance gates were approved and merged in PR #5 at
`3b481b61696e7349836cbbd7673adb6ba9c8c37a`. The next step is LLM screening
calibration plus human audit, beginning with a separately reviewed design and
no full-text retrieval.
