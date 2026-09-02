# Step 2 amendment: allow overlap between PubMed date slices

## Trigger

The first run after PR #3 correctly partitioned Nature below PubMed's 10,000
accessible-result limit, but stopped before fetching because the two slice
counts summed to 15,569 while the full-window query reported 15,540.

This demonstrates that PubMed's `Date - Publication` matching is not a
single-valued partition key: a PMID can satisfy adjacent date slices through
different indexed publication-date fields. Closed, non-overlapping calendar
ranges therefore prevent date gaps, but their result sets are not guaranteed
to be disjoint.

## Corrected completeness contract

Slice-count additivity is removed as an acceptance gate. It is valid for:

```text
sum(slice counts) > full-window count
```

because the same PMID may occur in multiple slices. Each slice must still:

- stay at or below 9,999 reported records;
- independently satisfy its reported count, fetched count, and unique-PMID
  equality; and
- retain its own enumeration run and raw XML checksums.

The authoritative cross-slice gate remains:

```text
COUNT(DISTINCT PMID across completed slices) == full-window PubMed count
```

This allows legitimate overlap but detects any missing or extra PMID in the
final journal universe. Annual comparisons remain diagnostic because the
parser chooses one canonical publication year while PubMed may index multiple
publication-date fields.

## Resume behavior

Stored slice boundaries, rather than stored counts, define the resume plan.
Counts may change as PubMed metadata is updated, but completed slice runs keep
their original reported counts. A resume rejects changed boundaries, retries
non-complete slices, and re-evaluates the final distinct-union gate against the
current full-window count.
