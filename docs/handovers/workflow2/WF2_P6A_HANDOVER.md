# WORKFLOW-2 · Phase 6a handover — the closeout's remaining area items

Designer: Claude (Fable), 14 November 2026. Implementer: Opus agent, same session.
Owner instruction (14 Nov): **"finish off all the remaining items"** of `WF2_CLOSEOUT.md` §3. This phase does items 2, 3, 4, 5, 6, 7 and 12. Phase 6b (separate handover) does item 1 (Studio editor translation). Items 8, 9, 10, 13 are statements, not work; item 11 is done (main loop deleted 19 folders, 14 Nov).

Read first: `WF2_LEDGER.md` (R1–R9, D1–D35, conventions §3, gotchas G1–G83 — binding); `WF2_CLOSEOUT.md` §3–§6; `WF2_P5C_REPORT.md` (how expense receipts became lines; the three timetables; deploy §4); `WF2_P5A_REPORT.md` (D28 sent-back emails as built); `WF2_P5B_REPORT.md` §8 and its translation method; then this file. Baseline: `pb_lifecycle` 19.0.1.19.0, 152 Studio tests, live ×5. Target **19.0.1.20.0**.

Design bar (owner, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji. White-label (binding): "Odoo"/"OdooBot" never in anything a person can see or receive, in any language. Plain words (R8). **Every new people-facing string ships with Vietnamese and Indonesian in the same commit** (P5b's `.po` rules: three markers, `.pot` too, parse gate, never regenerate a `.po`).

Reuse rule (owner, standing): Workflow Studio is the central point and **reuses** what areas already have. Each item below goes through the owning area's own door, add-only. If you find an existing feature that already does one of these, do not duplicate it: use it, and list it under "Overlaps found".

Order of work — ship each item only whole and proven; an item that cannot be finished safely is left entirely out and reported.

## 1. Repeat for each line — more areas (closeout item 2)
Clone exactly how `pb_me_expense/models/workflow_lines.py` declares receipts (contract `lines` + `_workflow_lines`), one file per area, add-only, restart-loaded:
1. Pay run → payslips (cap respected: over the cap the repeat refuses with the shipped sentence; label "payslip 3 of 120 · <employee>"; the line may name a person = the employee, so "The person on the line" works).
2. Time off → each day of the request.
3. Business trips → each leg (and name the model you found; if trips have no leg lines, say so and skip).
4. Asset handover → each item.
5. Joiner checklist → each equipment line.
For each: find the real model/field first; read only through the area's own records with the reader's rights as the shipped receipts do; no writes. R2: still no approval and no status write inside a repeat. Tests per area: declared, counted, labelled, capped, a person on the line resolves, an area without lines is skipped cleanly.

## 2. "Sent back" emails for trips and equipment (item 3, D28)
Same shape as `pb_timeoff`'s `_pb_tell_sent_back` and P5a's expense one: the employee is emailed the reason when their request is sent back, in their own language (P5b pattern), with the `biz_approval.single_notice` guard so nobody is told twice. These areas have no approved/refused email to sit beside: create the one template each, in the area's module, styled like the sibling areas' templates. Tests like P5a's.

## 3. Remaining reminder timetables (item 4, D31)
Declare (read-only, from each area's real settings, never hard-coded where a setting exists): time off balance reminders, pay review cycle, learning due dates, asset returns. Same contract method and Review warning as P5c's three. The reminders themselves do not change; job id lists identical. If an area has no such reminder, say so and skip it.

## 4. Drop `execution_user_id` (item 5)
G7 first: remove the record-rule terms that mention it, then the fields, with one migration script that drops the columns (pre-migration; guard for absent). Prove no code, view, rule, test or stored filter still names it (grep + `ir_rule`, `ir_filters`, `ir_ui_view` arch search on all five databases before the deploy). This is the one schema change of the phase: take a dump of each database before the upgrade (tiered deploy rule: risky tier).

## 5. Time off "sent back" (item 6, D33) — only if it can be done add-only
Today the employee sees "sent back" but the request is refused underneath. Find whether a safe, add-only improvement exists **without adding a value to Time off's status field and without changing balances logic**: e.g. a marker on the request that makes every people-facing surface (employee home, Time off lists, history, counts labelled "refused") say "Sent back" consistently and lets the employee correct and send again from the same request. If the only honest way is a new status value, do **not** build it: report the options with what each costs.

## 6. Line details read once (item 7)
Re-read a line's details when a line step opens (cheap, through the same area door) so a receipt edited after the repeat started shows its current amount on the task; keep the value captured at start in the activity history ("was … at the start"). A line that no longer exists: the line's open steps close with a plain note, the repeat's count updates, nothing fails. Tests for both.

## 7. Translation leftovers (item 12)
- Hiring's own stage names/descriptions: vi + id (stored values: `.po` AND the stored value per database — "a translation fix is two fixes").
- "Other request" status labels (`biz_approval_workflow` selection) and the approval-route sentence that shows "validation_type" on a screen: fix the wording to plain words and translate. `biz_approval_workflow`/`pb_approval_config` are shared with another session: re-read `/opt/deploy-notes.md` and `git status` for those paths immediately before editing; if another session has uncommitted edits in the same file, do it by `_inherit` from `pb_lifecycle` (G76) or leave it and report. Do not bump those modules (G29) unless a data file must change; a `.po`-only change loads by restart for code strings.
- Indonesian for the rest of the employee expense claim page (`pb_me_expense`).
- Activity history written earlier stays as written (stored text) — no work.

## 8. Binding non-goals and rails
- R1: nothing shipped moves or restyles; English output byte-identical for shipped surfaces except the one plain-words fix in §7 (list it in the R1 audit).
- No new scheduled job. Job id lists and mail/outbox/to-do counts identical before/after ×5. Sudima's Studio job stays off. No mail-server work (D29).
- Live: never create, enable, start, approve, move, grant or send anything. Never `abm`. On rize `debalina@rize.farm` holds role 462; G80 applies.
- Other sessions' uncommitted files (`pb_updates`, `pb_records`, `pb_clock`, `outputs/`, `docs/design/`, `docs/handovers/updates/`) are not yours. Explicit paths in every commit.
- Approval suites and each touched area's own suite: same result before and after (known baseline failures in closeout §4).

## 9. Deploy and verify
As P5b (`WF2_P5B_REPORT.md` deploy section): notes file START/DONE "Claude WORKFLOW-2" (re-read immediately before START; other sessions deploy daily — wait for their DONE and confirm with `ps` that exactly one service process runs before stopping it), flock, clean staging, five dumps first (schema change), scoped rsync with before-tarballs, parse gate on the server, `-u` the modules whose data/schema changed (mind dependents, G29), payobook, payobook_template, p0clone (suites + language proofs), rize, sudima last; asset purge ×5; restart; one process; warm; hashes + `latest_version` ×5; 0 ERROR. Cache keys `wf2-p6a` if a workbench file changed.

Commit per feature, explicit paths, no credentials. Do not push.

## 10. Report back (`WF2_P6A_REPORT.md`)
Per item: built / skipped and why; tests; browser proofs (local) for one new repeat area, one sent-back email in vi and id, the time off result; deploy evidence; R1 audit; Overlaps found; gotchas G84+; what phase 6b must know (any workbench file you touched); owner decisions needed. Update `WF2_CLOSEOUT.md` §3 in place: mark each item done / not done with one line.
