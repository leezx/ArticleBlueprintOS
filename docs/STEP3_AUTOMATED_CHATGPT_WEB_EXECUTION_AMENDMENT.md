# Step 3 amendment: controlled ChatGPT Web browser execution

This amendment supersedes the manual-copy execution boundary in
`STEP3_MANUAL_CHATGPT_WEB_EXECUTION_AMENDMENT.md` for the user-authorized
calibration only. It permits the Codex operator to use the already
authenticated Chrome UI to upload one locally generated packet, submit it in a
fresh ChatGPT conversation, read the response, and save it verbatim outside
the repository.

The route remains Web UI only: no model API, direct HTTP request, credential
access, session-cookie access, CAPTCHA/paywall bypass, or hidden model control
is permitted. Automation must stop immediately on login prompts, bot checks,
unexpected navigation, upload failure, or a non-fresh conversation.

The browser integration is visible-UI-only. It must not read or export Chrome
profiles, cookies, localStorage, sessionStorage, IndexedDB, authentication
headers, DevTools/network traffic, or any other authentication/session
material. A logged-in page may be used only through its rendered UI.

Each batch remains 1–50 records (20 by default). Only the allowlisted
`input.jsonl` and locked `web_prompt.txt` are uploaded. The operator records
the exact visible model label, execution mode (`automated_browser`), UTC
execution time, software revision, batch/attempt identity, input/output
checksums, fresh-chat confirmation, and raw response path. Raw output is
immutable; malformed output is retained as a failed attempt and retried only
with the next auditable attempt number.

The implementation must evolve provenance additively: the database supports
both `manual` and `automated_browser` execution modes, preserves existing
manual/prepared rows, and shares one strictly consecutive attempt history per
batch across both modes. Switching modes never resets an attempt to 1;
first-attempt validity, retry rate, and final completion retain the same
definitions. A migration must never silently rewrite existing provenance.

Automation saves only one confirmed-final assistant response after generation
completion. Streaming partial text, interrupted or regenerated responses,
multiple assistant responses, page refreshes, and indeterminate UI state fail
closed and remain auditable failed attempts.

The browser route does not mark calibration or human audit complete. Existing
schema, reference-standard, recall, stop-on-failure, and full-corpus gates
remain unchanged. This amendment authorizes implementation and testing of the
controlled route; real transmission begins only after its implementation PR
has been reviewed and explicitly approved.
