# NEWHIRE P8 — owner decisions of 2026-11-26

Owner rulings (verbatim intent, binding):
A. "For pay schemes, select the pay scheme by default, the one associated with the country of work. E.g. India →
   the pay scheme for India. If more than one, give that option during adding the employee. There, by default the
   scheme the team is mapped to should be selected."
B. "Update the RIZE database so that the teams are mapped to the pay scheme based on their country of work."
C. Hide one of the two "Add your tax number" reminders on the employee's home.
D. Access gets a "print a new sign-in slip" button.
E. HR managers see the New joiners board by default.
F. An equipment request ticks the checklist's laptop step by itself.
G. The joining checklist follows Country of work (not nationality).
H. "Enable Portal My home → Edit page for the HR Manager role" (the My Payobook page builder: add fields to My
   home / profile etc.).

Read first: `NEWHIRE_LEDGER.md` (D2/D3 "team decides the scheme, no per-person picker" are AMENDED by A),
`NEWHIRE_P7_REPORT.md`, `NEWHIRE_FACTS_CORE.md` (scheme map, `resolve_for_team`, how a payslip finds its scheme),
`NEWHIRE_FACTS_ONBOARD.md` §A6 (home to-do rows), §F (checklist, template choice, laptop step, New joiners board row
rights), §G (sign-ins, slips — Access desk), §H (equipment), §J (Form Studio; FS-16 page builder in
`docs/handovers/formstudio/`), §M; `NEWHIRE_P6_REPORT.md` + `NEWHIRE_P5B_DEPLOY_HANDOVER.md` (release rails/scripts).
Fresh worktree from `origin/19.1`.

Rails: design mandate verbatim "extreme WOW, intuitive, out-of-this-world experience, best in class"; Lucide, no emoji;
plain screen words; never "Odoo" in a user-visible string; vi_VN + id_ID for every new string (PO + LOOK rules);
lessons follow screen changes; public repo — no client names/data/credentials; backend needs a screen twin.

## A. Pay scheme follows the country, with a choice when there are several
A.1 FIRST establish (report, file:line) how a person's pay scheme is determined at pay-run time today: team map only,
    or is there a per-person / per-contract assignment the pay run honours (scheme-map row for an employee, a field on
    the contract, pay-run membership)? The studio may only offer a per-person choice through a mechanism the PAY RUN
    ALREADY HONOURS. If none exists: build A.2's default + display, make the multi-scheme choice set the TEAM (A.3), and
    report the gap as an owner question — do not invent a new assignment path in the pay engine.
A.2 Step 2 "Pay scheme" tile becomes live: schemes for Country of work C (active schemes whose country is C, company
    scoped). Exactly one → shown as chosen ("Indonesia Monthly · the only pay scheme for Indonesia"). None → today's calm
    "No pay scheme for <country> yet" + Mapping link. Several → a compact chooser in the tile (radio cards: name,
    currency, pay frequency, how many people it pays), default = the scheme the chosen team is mapped to; when the team
    has no mapping, default = the scheme that pays most people of that team, else most people in C. Changing the team
    re-defaults unless the user picked by hand (then keep + small "differs from the team's usual scheme" note).
A.3 Team default from the scheme side: with a country chosen and no team yet, teams mapped to a scheme of C are the
    "belongs" group (already P7 rule a); when the user picks a scheme first (several case), the Team list puts that
    scheme's teams first.
A.4 On apply: the person is paid by the chosen scheme through the A.1 mechanism. If the team is UNMAPPED and the
    company has exactly one scheme for C, nothing extra is written (the studio must not silently map a team); the Check
    step says plainly who will pay them and how to make it permanent ("Set who pays <team> in Mapping").
A.5 Payslip example, usual answers, components and currency all use the CHOSEN scheme (they key on the resolved scheme
    today — route them through one resolver `pb.new.hire._scheme_for(draft)`).
A.6 Server accepts old payloads without a scheme key (resolver falls back to today's behaviour). Tests: one / none /
    several; team mapped / unmapped; hand pick kept; apply honoured by a real pay run on a fixture (the person lands in
    the chosen scheme's run); example matches.

## B. rize: map teams to pay schemes (DATA CHANGE on a client database — owner-ordered)
B.1 Build a reusable, screen-reachable action — Mapping (or the studio's amber "No pay scheme pays <team>" line) gets
    "Suggest who pays each team": lists every unmapped team with the suggested scheme and why, tick boxes, Apply. Rule:
    team's country = country of work of the majority of its active people (ties / empty team → no suggestion);
    suggestion = the only active scheme for that country; several schemes for the country → the one that paid the
    majority of that team's people in their latest pay run; still ambiguous → no suggestion, listed as "needs your
    choice". Applies through the product's own mapping write (same as doing it by hand in Mapping), never raw SQL.
    Already-mapped teams are never changed.
B.2 On rize: dry-run first on the hidden copy; put the full proposal table (team → scheme, reason, people count,
    left-unmapped list) in a file under `outputs/` (NEVER committed — client data) and in the server-side undo table
    (`/odoo/backups/newhire-p8-<ts>/rize_team_map_undo.csv`: every row created, with id). Apply on live rize via the
    B.1 action as a real HR/manager-capable path (shell calling the same method is acceptable; say so). After: confirm
    no existing payslip, pay run or contract changed (counts + write_dates), the scheme-map stale flags are in the
    expected state, and the studio on rize now shows a scheme + payslip example for one team per country. Do not map
    on any other database.
B.3 If more than ~20 % of rize's teams end "needs your choice", still apply the unambiguous ones and return the list.

## C. One tax reminder
When the studio's welcome/asked-items home row is showing and includes the tax number, the tax area's own "Add your
tax number" row is hidden; when the studio's row is gone (nothing asked / all done) the tax area's row behaves as
before. Implement from `pb_new_hire` (inherit the to-do provider) — no edit in `pb_me_tax` unless unavoidable. Test both.

## D. "Print a new sign-in slip" in Access
In the Access desk's person actions (where tenant admins set passwords / print worker slips today — clone that slip
and its rights exactly), an action that issues a fresh sign-in slip for one person (and as a bulk action for selected
people): same content and security behaviour as the existing first slip (find how the first slip handles the
password: if it sets a temporary one, this does the same and says the old one stops working — confirm dialog in plain
words). Audit-logged like the other Access actions. Off where the Access desk is off (payobook demo). PDF must print
correctly with the NEW PDF engine (wkhtmltopdf 0.12.6.1 patched Qt: no flex/grid in printed templates, pages draw ~15 %
larger unless `data-report-dpi` is set) — open the PDF and look. Also link it from the studio's success screen for
people added without an email ("Print their sign-in slip").

## E. HR managers see the New joiners board by default
Find why they do not today (P2/P3b reports: Lifecycle role). Grant by implication from the HR manager role the
minimum Lifecycle right that shows the board and its rows (read + the board's own actions), on install/upgrade for
existing users too (group implication, not per-user writes). Must respect biz_access role gates / Access previews
(memory: Access preview reads palette gates) and record rules (own company). Test: HR manager sees it; HR officer and
employee unchanged.

## F. Equipment request ticks the laptop step
When an equipment request for the person reaches the state that means "handed over" (establish which state; if the
owner's intent is ambiguous between "requested" and "handed over", use handed over and show "Requested" as the step's
sub-line meanwhile), the joining checklist's laptop/equipment step for that person is ticked by the system (author =
system, note "Ticked when the laptop was handed over"), idempotent, never un-ticked automatically. Works for requests
made by the studio, by Hiring hand-over and by hand.

## G. Checklist follows Country of work
Template choice for the joining checklist uses the person's Country of work (`payroll_country`), falling back to
today's rule only when it is empty. Existing open cases are not re-templated. Studio step 6 preview uses the same
function. Test both countries + fallback.

## H. My home → Edit page for HR managers
Find the gate of the My Payobook page builder (FS-16: Form Studio portal). Extend it to the HR manager role — the
same role as E (name it in the report with its xmlid) — on all five databases: menu/button visibility, server-side
access checks, record rules, and any controller guard; an HR manager can add/hide/reorder fields on My home and
profile exactly as a tenant administrator can today, limited to their own company; they must NOT gain anything else the
administrator gate carried (enumerate what that gate guards and split it if it guards more than the page builder).
Employees and HR officers unchanged. Tests for allow/deny on each endpoint; walk as an HR manager.

## Tests / walks / release
Numbered tests per section (A1–A8, B1–B5, C1–C2, D1–D4, E1–E3, F1–F3, G1–G3, H1–H5), full suites of every touched
module before/after (same-failures rule). Walks local in en + vi: every section on screen, 340 px for the studio,
console clean.
Release — risky tier exactly as P6/P7: merge, push 19.1; `-u` every touched module on ALL FIVE (payobook_template →
p0clone → sudima → rize → payobook); deploy notes (wait on open START/HOLD), flock, quiet check, job counts, backups
×5 twice, rehearsals on hidden copies of rize AND payobook incl. the B dry-run, rollback plan before the stop. Then
B.2 on live rize. Never `abm`, never `_test_sudima_policy_20261119`. Apart from B.2, create nothing on client sites.
Do not act as the owner's signed-in admin on live sites.

## Report back — `NEWHIRE_P8_REPORT.md` (+ ledger amendments D2/D3, closeout), committed + pushed on 19.1
Final message: short plain summary per section A–H — what changed on screen, tests/walks counts, live or not per
site, downtime, rize mapping result (counts only: mapped / left for the owner, per country — no client names in the
repo; the full list path under `outputs/`), anything failed or left behind, open questions.
