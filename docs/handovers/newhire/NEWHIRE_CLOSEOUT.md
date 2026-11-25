# NEWHIRE — closeout (2026-11-25)

## 1. State
- Built in phases P1–P5a (reports alongside this file), released in P5b (`NEWHIRE_P5B_REPORT.md`) and P6
  (`NEWHIRE_P6_REPORT.md`).
- LIVE ON ALL FIVE (P6, 2026-11-25, commit `b763d7d49`, 354 s down): `pb_new_hire` 19.0.1.5.0 installed on payobook,
  payobook_template, p0clone, rize and sudima — People › Employees › Add employee is the seven-step studio everywhere.
- P6 also: the joining checklist (name, 11 step names + descriptions) and the 10 equipment names read in Vietnamese and
  Indonesian on all five (`pb_lifecycle` 19.0.1.22.0, `pb_onboarding` 19.0.1.5.0, `pb_assets` 19.0.1.4.0,
  `pb_training` 19.0.1.15.0, `pb_goals` 19.0.1.6.0; `biz_debrand` files only). Running checklists show the steps in
  the reader's language.
- P7 (owner request 2026-11-25, `NEWHIRE_P7_REPORT.md`): step 2 starts with the Country of work (that country's
  teams and jobs first, "What this decides" follows it, a team of another country is cleared with Undo); step 5's
  bank row, the employee's own My Payobook bank page and Bank Verification all show the account country's own
  boxes (IFSC, BSB, bank / branch code, SWIFT) from ONE definition (`pb_bank_ocr` `pb.bank.format`). Release
  status: see the P7 report §5.
- Architect live look after P5b: `/bizapp/add-employee` on payobook.com opens the seven-step studio, console clean.
- Demo record left on payobook on purpose: "DEMO NH P5b Live Check". Nothing created on the four other sites.
- `docs/deploy/PENDING.md`: the "pending on the other four" row is removed.

## 2. Open items
Owner decisions / setup
1. ~~Install `pb_new_hire` on the other four~~ — done in P6.
2. **rize and sudima cannot show "Paid by" or the first-payslip example yet**: rize has 4 active pay schemes but none
   of its 32 teams is linked to one in Mapping; sudima has no active pay scheme (its clock-pay scheme is a draft). The
   screen explains it and still adds the person. Link teams to schemes in Mapping (tenant setup) to light it up.
3. payobook demo world has no Indonesian team and no approval route for new hires → the Indonesian path and the
   "second person approves" step cannot be demoed there.
4. ~~Joining-checklist step names and equipment names in vi/id~~ — done in P6. Still English for Indonesian users:
   the New joiners board and equipment screens' own labels (almost no Indonesian screen translations in those
   modules; a few Vietnamese labels missing too), the "Tell us about you" questions, reminder email step names.
5. Learn has no Indonesian lessons (en + vi only).
6. Tax module's own "Add your tax number" home row shows next to the studio's asked-items row.
7. Earlier parked: print a new sign-in slip from Access; HR managers on the New joiners board by default; equipment
   requests ticking the laptop step; checklist by country of work vs nationality.
8. Contract letter with the new PDF tool is 2 pages (signatures alone on page 2; was 1 page) — for the document /
   PDF session (P6 report §2.7).
9. Architect call: a shipped step a company renamed in English would still get our translations from the upgrade's
   own loader (ledger NH78); P6 gated on "none renamed". Decide whether to pin a renamed row's missing languages.
Architect rulings made during the build (reversible): HR's step-6 buddy beats Hiring's; no document reader → bank from
Hiring defaults to "Ask the person" (reader configured on payobook only); optional "Valid until" for the Hiring ID
card; older welcome links stay valid after "Send again" until expiry; first payslip example 1–1.5 s accepted.
P7 owner questions (report §7): label of the first country group; Singapore bank code required or optional; no
bank file layout yet for Australia / Thailand / Cambodia / Malaysia; rize teams not linked to pay schemes (lists
built from where people work).
Not verified live
- L6 Hiring › "Confirm they joined" → studio (no signed offer waiting on any site; proven locally, P4 walks G4).
- Approval path on live (the walks added people straight away, no approval step for those logins; proven locally P1–P3).
- Owner's own two-minute look on rize and sudima (P6 checked on a hidden rize copy + server checks only).
- ~~Contract letter PDF after the other session's PDF change~~ — produced and opened in P6 (see item 8).

## 3. Cleanup
Worktrees `gitlocal-worktrees/newhire`, `gitlocal-worktrees/nh-release`, `gitlocal-worktrees/nh-p6` and `gitlocal-worktrees/nh-p7` can be removed.
