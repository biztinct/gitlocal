# WORKFLOW-2 · Phase 5b handover — Vietnamese and Indonesian, tidy-up, closeout

Designer: Claude (Fable), 12 November 2026. Implementer: Opus agent, same session. **Last phase of the programme.**
Read first: `WF2_LEDGER.md` (R1–R9, D1–D34, conventions §3, gotchas G1–G79 — binding); `WF2_P5C_REPORT.md` **§4 (deploy as last done), §10, §13 (the string inventory this phase works from), §14**; then this file. Baseline: `pb_lifecycle` 19.0.1.18.0, 149 Studio tests, live ×5. Target **19.0.1.19.0**.

White-label (binding): "Odoo"/"OdooBot" never in anything a person can see or receive — in any language. Plain words (R8) in every language: translate the meaning a person on the screen needs, never the code word. Use the vocabulary the product already uses in each language (find the existing msgstr for "pay run", "approval", "time off", "task", "stage", "workflow" in the shipped `.po` files and reuse it exactly; list the glossary you used in the report).

## 1. Scope

### 1.1 Translations — what people other than the builder see (must ship)
Vietnamese (`vi_VN`) and Indonesian (`id_ID`) for every WORKFLOW-2 string a person **outside the Studio editor** can see or receive:
- task page, employee home pages (`/my/todo…`), public link pages (`/workflow/t/…`), record strip (OWL and QWeb twin), dock line, Approvals inbox additions (Tasks group, line words, "Do all in turn"), in-app notices and announcements, "sent back" and link emails (mail templates: make them language-aware the way the area's existing approved/refused templates are), late/passed-up/reminder outbox messages, status wordings (D22), errors a participant can hit.
- the module contracts' words that appear on those surfaces (stage names, effect sentences, line labels "receipt 2 of 3", reminder timetable sentences) in `pb_hiring`, `pb_timeoff`, `pb_me_expense`, `pb_payruns`, `biz_approval_workflow`, `pb_contract_lifecycle`, `pb_probation`, `pb_employee_vault`.
- the new right's and ability's name and description (data records: translate through the `.po` `model_terms`/record entries AND confirm the stored value per language on each database — a translation fix is two fixes: the `.po` and the stored value).

### 1.2 Translations — server strings shown inside the Studio (ship)
The remaining server `_()` strings in `pb_lifecycle/models/workflow_*.py` listed in `WF2_P5C_REPORT.md` §13 (validation messages, Review warnings, "already happens", time report). Wrap `workflow_schedule.py`'s ~25 plain constants in `_()` first (lazy where module-level: `LazyTranslate`/`_lt` pattern used elsewhere in this build — find the precedent, do not invent).

### 1.3 The Studio editor's own screen text (`static/workflow/*.js`, ~466 phrases) — NOT in scope
The workbench has never had a translation mechanism (true before WORKFLOW-2). Do not build one in this phase. Record it in the closeout as an open item with a sized recommendation (mechanism + phrase count + which files).

### 1.4 Rules for every `.po` entry (ledger + memory, binding)
Each entry needs all three or it crashes the upgrade or stays English in silence: `#. module: <name>`; `#. odoo-python` or `#. odoo-javascript`; `#: code:addons/<module>/<path>:0`. Markers go **after** the module line. Where a `<module>.pot` exists, add the msgid there too (a `.pot` filters its `.po`). `pb_lifecycle` has no `id_ID.po`: create it. Never regenerate a whole `.po` with an export (it wipes hand-kept entries) — append/merge only, and diff entry counts before/after per file (no entry lost). `%s`/`%(name)s` placeholders identical in every msgstr (script-check). Run the `PoFileReader` parse gate over every `.po` and `.pot` touched locally **and** on the server after rsync, before any `-u`.

Proof that it loads (local suites prove nothing — a test DB has no second language): on p0clone after the upgrade, as a `vi_VN` user and an `id_ID` user, call the people surfaces and assert translated output for a sample of at least 30 strings per language spread across every file in §13; plus browser screenshots (local, both languages) of: task page, `/my/todo`, link page, record strip, inbox Tasks group with line tasks, one email preview. Report remaining-English counts per file per language (target 0 for §1.1; any left in §1.2 listed with reason).

### 1.5 Consolidation (small, safe only)
From `WF2_P5C_REPORT.md` §13 "Consolidation candidates": make the screen read the server's sentence instead of building it twice where the server already returns it (`workflow_schedule.words`/`schedWords`; `_repeat_words`/`repWords`; inbox card and "My tasks" line words) — only where the output is byte-identical in English for the shipped fixtures (prove with tests). Anything that would change a pixel or a sentence: leave it and list it. R1: nothing shipped moves or restyles.

### 1.6 Closeout report — `WF2_CLOSEOUT.md` (written for engineers; §0 for the owner in plain words)
- §0 plain words: what the programme delivered, phase by phase, in screen vocabulary; what the owner should try first.
- What is live: versions per module ×5, test counts, the undo switch (`biz_approval.single_notice`), job state (sudima Studio job off by owner choice; Approvals message job off on payobook/template).
- Every owner decision D1–D34 in one table (decision, where it lives).
- **Open items**, each with a sized recommendation: Studio editor translation (1.3); repeat for more areas (pay run payslips first, then time off days, trip legs, asset handover items, joiner equipment); trips and equipment "sent back" emails; remaining areas' reminder timetables; `execution_user_id` column drop; time off "sent back" is a refusal underneath; line details read once at start; lines start 25 per click; never tested on a real phone or touchscreen; no outgoing mail on rize/sudima/p0clone by owner choice (D29 — state only, do not recommend changing); ~18 leftover filestore folders (owner not asked to delete).
- Known failing baseline tests per module, by name (from P5c report §13 and G60), each marked "not caused by this programme".
- Gotcha ledger index, where each handover/report is, how to roll back the last phase.
- Access change made by the main loop on rize, 12 Nov: role "See everyone's approvals" (id 462) given to `debalina@rize.farm`; undo = remove the role from her on the Access screen.

## 2. Binding non-goals and rails
- No new behaviour, no new step type, no new job, no schema change beyond what translations need (none expected).
- English output byte-identical before/after for every shipped surface (tests t11-style fixtures from P5c still pass; add one that renders each people surface in `en_US` against a stored baseline).
- Do not touch `pb_approval_config`/`biz_approval_workflow` code (another session works there; G29, G76). Their `.po` files: add entries only if a WORKFLOW-2 string lives in that module (`biz_approval_workflow/models/workflow_contract.py`, 8 strings) — coordinate through the notes file, re-read the file immediately before editing and before rsync, and hash the server tree against the repo before overwriting (stop if it differs).
- Other sessions' uncommitted files (`pb_records`, `pb_updates`, `outputs/`, `docs/design/`, `docs/handovers/updates/`) are not yours.
- Live: never create, enable, start, approve, move, grant or send anything. Never `abm`. No mail server talk (D29).

## 3. Deploy and verify
As P5c (`WF2_P5C_REPORT.md` §4): notes file START/DONE "Claude WORKFLOW-2" (re-read immediately before START — the UPDATES session deploys `pb_updates` repeatedly today; wait for its DONE and confirm exactly one service process before stopping the service), flock, clean staging, scoped rsync with before-tarballs, parse gate on the server, `-u` each module whose `.po`/data changed (versions bumped only where needed; G29: mind dependents), order payobook, payobook_template, p0clone (suites + the language proofs), rize, sudima last; job id lists and mail/outbox/to-do counts identical before/after ×5 (note: rize now has role 462 and one more approval request/outbox row than P5c's snapshot — take a fresh "before"); sudima Studio job off; asset purge ×5; restart; one process; warm; hashes + `latest_version` ×5; 0 ERROR; no `no translation for language` line for the modules touched. Cache keys `wf2-p5b` only if a workbench file changed.

Commit per feature, explicit paths, no credentials. Do not push.

## 4. Report back (`WF2_P5B_REPORT.md`, short) + `WF2_CLOSEOUT.md`
Commits, versions; per-file per-language counts before/after; glossary; the loaded-proof results and screenshots; consolidation done / left; deploy evidence; deviations; gotchas G80+; anything in §1.1 still English and why.
