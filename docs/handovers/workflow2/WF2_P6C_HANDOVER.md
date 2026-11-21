# WORKFLOW-2 · Phase 6c handover — time off "Sent back": the label and "Ask again"

Designer: Claude (Fable), 17 November 2026. Implementer: Opus agent, same session, after phase 6b in the same worktree.
Owner decision D36 (16 Nov): **"Label + Ask again"** = options B and C of `WF2_P6A_REPORT.md` §7 together. Owner also decided: **no workflows on pay runs for now** (do nothing there).

Read first: `WF2_P6A_REPORT.md` §2.6 and §7 (the facts: `HrLeaveApproval._approval_return` refuses the request; the label comes from five places) — do not re-derive; `WF2_LEDGER.md` rules. The time off area changed on the shared branch since P6a (WDGAP QF3: half days and hours, withdraw, cancel, documents, "balance after" on My Payobook; balance board changes) — read the current `pb_timeoff` and `pb_me_portal` leave code before designing, and **reuse** what QF3 added (its request form, its withdraw/cancel buttons' pattern); never add a second way to ask for leave.

## Build
1. **A mark, not a status.** One new stored boolean on the time-off request in `pb_timeoff` (set when the approval is sent back, with the reason kept where it already is; cleared never). **Time off's status field and every balance rule stay exactly as they are**: the request is still refused underneath, so no day is held.
2. **"Sent back" wherever our own screens name the status**: employee home requests list and the leave pages on My Payobook, the staff Time off cockpit cards, and the cockpit's saved view/filter (a "Sent back" view beside "Refused"; "Refused" then shows only real refusals on our screens). Colour and chip follow the existing "sent back" look used for expenses. Show the reason under the chip where the screen has room. The standard form, list and board keep "Refused" (owner accepted this) — but add a plain one-line note on the standard form: "Sent back to the employee, not refused: <reason>".
3. **"Ask again"** on a sent-back request (employee's own pages; staff acting for an employee where QF3 already allows it): opens the existing request form filled in from the old request (kind, dates, half day/hours, note; documents are not copied — say so), the employee changes what they need and sends it; the new request names the old one ("Asked again after …") and the old one shows "Asked again on …" with a link, and its button disappears. One "ask again" per sent-back request. All normal rules run on the new request (balance, overlap, notice) — nothing is bypassed.
4. Counts and reports on our own screens that say "refused" must not count sent-back requests as refusals; list every count you changed.
5. Vietnamese and Indonesian for every new string in the same commit. Never "Odoo" in a visible string. Design bar (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience, best in class." Lucide icons, never emoji.

## Rails
- No backfill guesswork: existing refused requests get the mark only where the approval request provably was sent back (it has a `return_note` / returned decision); report the count per database before writing, and do it in the upgrade's post-migration, idempotent.
- Schema change (one column): dumps of all five databases before the upgrade.
- pb_timeoff's own suite: same known failures before and after (6 `TestLeaveRules`). New tests: mark set on send back and not on refuse; labels on each surface; ask again pre-fills, links both ways, once only, runs the normal rules (a request over balance is refused by the normal rule); counts.
- Browser proof (local): employee page with a sent-back request, Ask again through to the new request waiting for approval, staff card, in en/vi/id; 390 px for the employee pages; console clean.
- Live: never create, approve, move, grant or send anything. Never `abm`.

Deploy with phase 6b in one go if both are ready (one outage), else separately; same procedure as the 6b handover §4, `-u pb_lifecycle,pb_timeoff` (+ `pb_me_portal` only if its data changed; mind dependents, G29). Report in `WF2_P6C_REPORT.md`; update `WF2_CLOSEOUT.md` §3 item 6 and the ledger (D36, phase row, gotchas).
