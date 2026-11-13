# UPDATES programme — closeout (2026-11-13)

People › Updates: a standalone bulk sheet door for employee details, contract and pay
items, one-off pay items, new joiners, leave opening balances and year-to-date figures —
usable any time, separate from the pay run. Built 2026-11-11 → 2026-11-13 in phases
P1–P6 (+ P4b, P5b, P5c, P5d). Everything below is LIVE on `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima` and pushed to `origin 19.1`.

Source of truth for decisions (D1–D32), facts (U…) and gotchas (G1–G97):
`UPDATES_LEDGER.md`. Per-phase evidence: `UPDATES_P*_REPORT.md`.

## 1. What shipped

| Phase | What | Report |
|---|---|---|
| P1 | Front door: download sheet, upload own file, remembered column matching, review grid, named batches, history, undo | P1 |
| P2a | Safe name look-ups, full-roster speed, Sudima added | P2A |
| P2b | Pay items by pay scheme, greyed off-scheme cells, CLEAR | P2B |
| P2c | Start dates, scheduled changes (hourly job), Start now, real Cancel, manager by code/email | P2C |
| P2d | One-off pay items for a pay month, paid once, clash = stop and ask | P2D |
| P3a | Three approval lanes; bank details need a second person; pay data file month-only; old employee import retired | P3A |
| P3b | New employees from a sheet, drafts, "Since the last pay run" | P3B |
| P3c | Bank approvers: support/demo logins never seated; rize route names its own people; new tenants' admin holds Finance | P3C |
| P6 | Tenant administrators manage approvals for their own company | P6 |
| P4 / P4b | Leave opening balances sheet; attendance tile; HR officers may send leave sheets | P4, P4B |
| P5 | Year-to-date figures before Payobook: sheet, store, view, tax summary row, guarded mapping, "Download for the pay run" | P5 |
| P5b | Engine `history.ytd`: blank joining date = "not known"; new demo runs keep results | P5B |
| P5c | "Paid in Payobook" counted honestly (complete sums only, engine signs, advances once), popover | P5C |
| P5d | Employee tax summary counts each month once; mid-year joiners paid in Payobook alone | P5D |

Final versions: `pb_updates` 19.0.1.7.3, `pb_records` 19.0.1.10.1 (see each report for the
other modules touched).

## 2. Open items

### Owner / client decisions and actions
1. **Tax summary, advance whose month-end slip is not finished** (P5D): not counted
   ("waits for month end"), so a person whose only tax sits on such an advance shows 0.
   Owner asked 2026-11-13 whether to count it until month end.
2. **Rize Indonesia December**: Rize to confirm "Total income" = monthly taxable pay and
   whether severance was paid; December steps and exact mapping in `UPDATES_P5_REPORT.md`
   (re-read with P5C/P5D: incomplete figures are refused, joiners rule D31).
3. **Rize's two August test runs** (same Indonesia scheme, same 122 people): delete or
   never finish — both DONE would double every year-to-date figure (warning shown).
4. **Rize joining dates**: 132 of 241 active people have none → year-to-date "not known"
   for them; 38 joined in 2026 and qualify under D31 once payslips are finished.
5. **Nobody at Rize holds Tenant administrator** — nobody there can use P6's approvals
   set-up until one is named.
6. **Sudima**: HR login can change approvals (P6); bank approvals are owner ↔ HR login
   (D21, accepted for now). Two waiting changes on sudima were left untouched.
7. `p0clone` and `payobook_template` have no bank approver (bank lane waits, by design).

### Product gaps (not built)
8. **Application-data pay runs do not read Updates one-offs** (only rize uses that mode);
   the screen says so. Year-to-date reaches them only via "Download for the pay run".
9. "Since the last pay run" exists only on Review pay data.
10. Tax year is the calendar year everywhere (India April–March not modelled).
11. Leave sheet refuses half days where the leave type does not allow them (owner: keep).
12. Old demo payslips carry no taxable pay (owner: leave); demo schemes have no own pay
    items, so greyed off-scheme cells rarely show on the demo.

### Engineering debt
13. "Review pay data" is slow (~90 s for 902 people) and errors when opened twice.
14. Five older approvals-suite test failures predate this programme.
15. Engine wording "carried out" for scheduled changes.
16. Prototype `docs/design/updates-desk-prototype.html` not updated since v2.
17. `outputs/updates-p6/` — nine screenshots were committed (1222eb576); harmless, left.
18. **Shared working tree hazard (G94+)**: on 2026-11-12 another session's deploy shipped
    P5c's uncommitted code. Build in a git worktree and deploy from a commit.

## 3. Undo references
- rize bank route (workflow 17504 revision 2): undo SQL in `UPDATES_P3C_REPORT.md` R0.
- Backups (`pg_dump` ×5) taken before every Tier 3 deploy; paths in each report.
