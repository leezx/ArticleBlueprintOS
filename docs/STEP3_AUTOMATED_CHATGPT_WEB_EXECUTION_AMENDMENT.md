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

Each batch remains 1–50 records (20 by default). Only the allowlisted
`input.jsonl` and locked `web_prompt.txt` are uploaded. The operator records
the exact visible model label, execution mode (`automated_browser`), UTC
execution time, software revision, batch/attempt identity, input/output
checksums, fresh-chat confirmation, and raw response path. Raw output is
immutable; malformed output is retained as a failed attempt and retried only
with the next auditable attempt number.

The browser route does not mark calibration or human audit complete. Existing
schema, reference-standard, recall, stop-on-failure, and full-corpus gates
remain unchanged. This amendment authorizes implementation and testing of the
controlled route; real transmission begins only after its implementation PR
has been reviewed and explicitly approved.
