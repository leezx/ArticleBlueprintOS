# Agent instructions

Read `docs/PROJECT_CHARTER.md` and the active step design in full before making
changes.

- Work on one branch per reviewed step and open a PR against `main`.
- Never merge a PR without explicit user approval for that specific PR.
- Keep data payloads out of git. SQLite databases, PubMed XML, exports, PDFs,
  HTML full text, and extracted text belong under `ARTICLE_BLUEPRINT_DATA`.
- Preserve the full journal-first universe. Screening may prioritize records,
  but only a human-reviewed decision can exclude a paper from the final corpus.
- Store provenance for every fetch, model decision, audit sample, and full-text
  retrieval.
- Do not bypass paywalls, CAPTCHAs, bot checks, institutional login, or DRM.
- Use open-access or user-authorized institutional routes for full text, in
  small batches from a reviewed paper list.
- Update `docs/PROJECT_SUMMARY.md` at milestones and append `Worklog.md` only
  after a PR is merged.


<claude-mem-context>
# Memory Context

# [ArticleBlueprintOS] recent context, 2026-09-02 4:02pm EDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 4 obs (1,318t read) | 67,748t work | 98% savings

### Sep 2, 2026
9 3:43p ⚖️ ArticleBlueprintOS: Bioinformatics Literature DB Scope Locked to 9 Journals, 2023–2026
10 " ⚖️ Three-Tier Funnel Architecture for Article Enumeration and Filtering
11 " 🔵 GitHub CLI Token Expired for `leezx` Account — Blocking Repo Creation
12 " 🔵 ArticleBlueprintOS Local Workspace Structure and Governance Templates Confirmed

Access 68k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>