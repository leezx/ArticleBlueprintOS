# Step 2 amendment: partition PubMed queries below 10,000 records

## Trigger

The first reviewed Step 2 execution on 2026-09-02 queried `Nature` for the
locked full window. PubMed reported 15,540 records, but retrieval stopped at
the 10,000-result boundary with HTTP 400. The journal run was recorded as
failed; no partial run was marked complete.

NCBI documents that PubMed ESearch can access only the first 10,000 records of
a query and recommends adding date limits to segment larger result sets into
batches below that limit:

- https://www.ncbi.nlm.nih.gov/books/NBK25499/#chapter4.ESearch

This operational constraint was not captured in the original Step 2 design.
This amendment supersedes only its one-query-per-journal orchestration; the
locked journal universe, date window, provenance, and acceptance gates remain
unchanged.

## Revised orchestration

1. Obtain the authoritative count for the full journal/date query.
2. Recursively bisect the date range until every planned slice contains at
   most 9,999 PubMed records.
3. Persist every slice, its planned count, attempts, enumeration run, error,
   and completion state.
4. Resume at slice granularity: completed slices are skipped; failed or
   interrupted slices are retried without deleting earlier enumeration runs or
   raw XML.
5. Count the distinct PMID union across all completed slices and require it to
   equal the authoritative full-window count. A mismatch fails the journal.
6. Retain annual comparisons as parser/date-boundary diagnostics; they do not
   replace the full-window union gate.

The partition plan itself is fail-closed. Its slice counts must sum to the
full-window count, and a single-day slice that still exceeds 9,999 records is
rejected rather than truncated.

## Recovery of the interrupted run

The existing backfill ID and its failed/running journal states remain the
authoritative provenance record. After this amendment is reviewed and merged,
the same backfill is resumed. The obsolete failed full-window Nature
enumeration and interrupted Science attempt remain stored; new slice runs are
linked separately.
