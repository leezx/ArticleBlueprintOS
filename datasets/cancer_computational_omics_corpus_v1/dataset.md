# Cancer Computational Omics Blueprint Corpus v1

- **Type**: one-time historical backfill followed by prospective updates.
- **Canonical workspace path**:
  `${BIOWORKSPACE_ROOT}/DATA/1.Databases/article_blueprint_os/`
- **Metadata source**: NCBI PubMed E-utilities.
- **Time range**: 2023-01-01 through an explicit run cutoff.
- **Journal universe**: `config/journals.json`.
- **License/access**: PubMed metadata under NCBI terms; full text only through
  legitimate open-access sources or the user's authorized institutional route.
- **Current status**: design/implementation; no historical payload acquired.
- **Expected payloads**: immutable PubMed XML responses, versioned SQLite
  metadata database, screening/audit exports, legally retrieved full text,
  extracted text, and blueprint outputs.
- **Repository boundary**: this manifest is committed; payloads are not.

## Verification requirements

Every acquisition run records source URLs, query, date range, timestamps,
counts, software commit, and completion status. Full-text assets additionally
record access status, byte size, MIME/format validation, SHA-256, and whether
supporting information was available but not downloaded.
