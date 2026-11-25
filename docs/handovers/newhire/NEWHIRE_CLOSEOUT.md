# NEWHIRE — closeout (2026-11-25)

## 1. State
- Built in phases P1–P5a (reports alongside this file), released in P5b (`NEWHIRE_P5B_REPORT.md`).
- LIVE: `pb_new_hire` 19.0.1.5.0 installed on **payobook only**; shared-module changes (`pb_scheme_map`, `pb_probation`,
  `pb_hr_payroll_formula`, `pb_people`, `pb_learn`, …) upgraded on all five (payobook, payobook_template, p0clone,
  rize, sudima). On the four without `pb_new_hire` the old `pb_onboard_wizard` window is untouched.
- Architect live look after release: `/bizapp/add-employee` on payobook.com opens the seven-step studio, console clean.
- Demo record left on payobook on purpose: "DEMO NH P5b Live Check".
- `docs/deploy/PENDING.md` carries the row "pb_new_hire pending on the other four — waiting for the owner".

## 2. Open items
Owner decisions
1. Install `pb_new_hire` on rize, sudima, p0clone, payobook_template (risky-tier install each; rehearsal recipe in the
   P5b report is reusable).
2. payobook demo world has no Indonesian team and no approval route for new hires → the Indonesian path and the
   "second person approves" step cannot be demoed there.
3. Joining-checklist step names and equipment names have no vi/id translations (owned by `pb_onboarding` /
   `pb_lifecycle` / `pb_assets`).
4. Learn has no Indonesian lessons (en + vi only).
5. Tax module's own "Add your tax number" home row shows next to the studio's asked-items row.
6. Earlier parked: print a new sign-in slip from Access; HR managers on the New joiners board by default; equipment
   requests ticking the laptop step; checklist by country of work vs nationality.
Architect rulings made during the build (reversible): HR's step-6 buddy beats Hiring's; no document reader → bank from
Hiring defaults to "Ask the person" (reader configured on payobook only); optional "Valid until" for the Hiring ID
card; older welcome links stay valid after "Send again" until expiry; first payslip example 1–1.5 s accepted.
Not verified live
- L6 Hiring › "Confirm they joined" → studio (no signed offer on payobook; proven locally, P4 walks G4).
- Approval path on live (payobook demo company has no route; proven locally P1–P3).
- Contract letter PDF after the other session's PDF change (re-check one letter).

## 3. Cleanup
Worktrees `gitlocal-worktrees/newhire` and `gitlocal-worktrees/nh-release` can be removed once item 1 is done.
