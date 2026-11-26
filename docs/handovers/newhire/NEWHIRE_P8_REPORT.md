# NEWHIRE P8 — owner decisions of 2026-11-26 (report)

Engineer, 26 Nov 2026 (UTC). Handover `NEWHIRE_P8_HANDOVER.md`; coordinator rulings during the phase (§0).
Engineering receipt: real technical names on purpose. No credentials, client names or client data in this file.

**Result: GO for A, C, D, E, F, G, H and the B tool. Pushed to `19.1` (`3d038fcc9`, the deployed commit) and
LIVE on all five databases, 195 s of downtime (02:09:43–02:12:57 UTC).** Every database exit 0, 0 ERROR, nothing
restored. **B's live rize mapping was NOT applied** (owner hold, §0.2): the tool is live everywhere, the dry run
ran on the hidden rize copy only, no map line was written on any live database (rize map lines 25 = before).
abm and `_test_sudima_policy_20261119` untouched. Nothing created on any client site.

## 0. Rulings received during the phase (binding, recorded)
1. Per-person scheme: keep as built — the studio never writes a map line; a plain sentence when the pay run
   will not use the pick. No pay-engine change in this phase.
2. Section B: the live rize mapping is ON HOLD (owner is designing person-level scheme assignment in another
   stream). The tool ships; the dry run ran on the hidden rize copy; the client workbook lists the teams that
   could be linked cleanly as PROPOSED, not applied. Nothing was mapped on any live database.
3. Section E: a NEW narrow right for the New joiners board, implied by the HR manager role — never the
   Lifecycle Manager role.
4. Section A must answer "which pay scheme will pay this person" through ONE resolver that follows the pay
   run's full chain (team line, then the per-country rule, then the pay run's fallbacks) — checked and tested
   (A9, A10), verified on the hidden rize copy (§6.3).
5. Owner: the coming person-level design assigns the scheme by COUNTRY OF WORK, never by work site (§2.4).

## 1. What changed on screen
### A. Pay scheme follows the country of work
- Step 2 "Pay scheme" tile follows the Country of work at once (before any team): one scheme → shown as chosen
  ("The only pay scheme for Indonesia."); none → "No pay scheme for Malaysia yet" + "Suggest who pays each team"
  (opens Mapping with that drawer open); several → radio cards in the tile (name, currency · kind of run ·
  "pays N people", a "Usual" tag), Enter / Space / arrow keys.
- Default when several: the pay run's own answer for this person (team line, division, a rule on the map, the
  only scheme) when it is of the chosen country → the team's; else the scheme paying most of the team; else
  most of the country. Changing the team re-defaults unless picked by hand; a hand pick stays with "This differs
  from the team's usual scheme, X. Use the usual one".
- The team list puts "Teams <scheme> pays" first when the country has several schemes (A.3).
- Honest pay-run line (amber, step 2 / step 3 / record panel / Check): "<team> is paid by X, and the pay run
  follows the team." + how to pay them by the pick; "No pay scheme pays <team> yet." only when the pay run itself
  would find nothing; a rule-paid team shows on Check "<scheme> pays them through a rule on the map. Set who pays
  <team> in Mapping to make it the team's own." The approver's card gets "Who pays them" when it differs.
- Payslip example, usual answers, components and currency use the chosen scheme (`decides(..., scheme_id)` →
  `_scheme_for`).

### B. Mapping › "Suggest who pays each team"
- Mapping's "Who is paid by what" board gets "Suggest who pays each team" (also opened from the studio's
  scheme tile / amber line). A drawer lists every team no line of its own or of its division pays:
  "Can be set now" (tick boxes, ticked when nobody's paying scheme would change; unticked with "Moves N" and
  "N of them are paid by another pay scheme today and would move to X" otherwise), "Needs your choice" (the
  reason in plain words), and teams with nobody in them. "Set N teams" writes through the board's own path (a
  proposal; carried out at once where no second person approves, otherwise "Sent for approval" and the button
  goes away). Already-mapped teams are never touched; a line written later is never replaced (`keep_existing`).
- Rule as built: the team's country = the Country of work of MORE than half of its active people (ties,
  nobody with a country, empty team: no suggestion); the suggestion = the country's only active scheme (never a
  mid-month advance); several → the one that paid more than half of the team in their latest pay run; else
  "needs your choice". Two rails added (NH92, NH95): a team where someone would change scheme is offered
  unticked; a team with an older line for the same kind of run (even one naming an archived scheme) says
  "An older line on the map still names X for this team. Take it off on the map first, then ask again."

### C. One tax reminder
While the joining-details row on My Payobook is showing and still asks for the tax number, the tax area's own
"Add your tax number" row is hidden; it comes back by itself once the joining row is gone or the tax number is
no longer among the open asks. Done from `pb_new_hire` (a filtering `put` around `super()`); `pb_me_tax` untouched.

### D. Access › "Print a new sign-in slip"
- Person card (desk): "Print a new sign-in slip" → confirm in plain words ("Their old password stops working and
  they are signed out everywhere. They choose their own password the next time they sign in.") → the slip result
  → "Print the slips".
- Bulk: Logins for workers gets a second mode "New sign-in slips" (people who already sign in; tick, press twice:
  the second press after the warning).
- Same slip as the first one (one shared printer `printSignInSlips`), same password shape, same path as "Set a
  new password" (`set_user_password`: same refusals, signed out everywhere, must change at next sign-in), shown
  once, never stored or logged; a log line like the other desk actions. Add employee's done screen: "Print their
  sign-in slip" for people signing in with their employee number, shown to people who manage access.
- Finding: the slip is a page the browser prints (a table; no PDF engine involved), so the wkhtmltopdf rail does
  not apply. No switch turns the Access desk off; the buttons appear only where the desk card does (NH96).

### E. HR managers see the New joiners board
New right "New joiners board" (`pb_new_hire.group_joiners_board`), implied by `hr.group_hr_manager`
(HR manager role). People › Joiners tab and its ⌘K row show for it; the board, its rows, the joiner drawer
and the board's own actions (choose / cover a buddy, run a step now) work, inside the reader's own companies and
live joining checklists only; Welcome sessions, HR partner rules and Run today's steps stay the Lifecycle team's
(hidden; refused by the server). No Lifecycle access rule changed; HR managers do NOT get Lifecycle Manager.

### F. Equipment handed over ticks the laptop step
When a request that counts for "Laptop and equipment" is handed over (Progress: delivered or confirmed), the step
is ticked by the system user with the note "Ticked when the laptop was handed over"; never un-ticked; idempotent.
Counts: requests linked to the step (studio, Hiring's checklist) and a laptop requested by hand since the
checklist opened. Meanwhile the step shows "Requested" (Journeys and the New joiners drawer; display only).

### G. Checklist follows Country of work
The joining checklist template is picked by the Country of work for every opener (studio, Hiring, connected
system: `pb.zoho.pipeline._open_case` → `pick_for` reads it); nationality only when the Country of work is empty.
A running checklist is never re-templated. Step 6 previews the same function.

### H. My home → Edit page for HR managers
New role "My Payobook page builder" (`pb_form_studio_portal.group_page_builder`), implied by
`hr.group_hr_manager` (the same role as E). Edit this page, the page builder, preview and banners open for it.
A page builder who is not the administrator changes the page of the company they work in: add / hide / order
fields, sections, columns, header, colour, banner; a note says so. What the old gate also guarded and stays the
administrator's (enumerated): every other Form builder screen and method (`get_studio`, `create_field`,
`update_field`, `delete_field`, `update_portal`, `update_standard`, library, reach switch, premium sections,
save/discard/publish of other screens), field settings that apply to every company (labels, "Employee can
change it", HR approves / saves at once, the personal-boxes switch), the page for every company and other
companies' pages, history restore and "Reset to the standard page". Finding: the gate was `base.group_system`,
not the Tenant administrator (NH97).

## 2. Section A gate and the seam (A.1)
### 2.1 How a person's pay scheme is decided at pay-run time (today)
- The pay run's population: `pb_payrun_wizard/models/pb_payrun_wizard.py` `_scheme_population` (≈ :322) →
  `pb.scheme.map.resolve_many` (`pb_scheme_map/models/pb_scheme_map.py`).
- A payslip's scheme: `pb_hr_payroll_formula/models/hr_payslip_formula.py` (≈ :440–500): the run's own scheme →
  the import batch's → the scheme map (`resolve`) → a sibling payslip → the structure.
- The map's ladder (`RUNGS`): 1 a confirmed work segment naming a scheme (cross-company days) · 2 the team's own
  line (deepest team first) · 3 the team's division · 4 advanced rules (an employee domain, in sequence) · 5 the
  company's only active scheme · 6 nobody.
- Per-person mechanisms the pay run honours: rung 1 (stretches of days in another company — not a scheme
  choice) and rung 4 (a rule), which ranks BELOW a team's own line. No per-contract field. So a per-person pick
  that differs from a team line cannot be honoured; the studio writes nothing and says so (ruling 1).

### 2.2 The one resolver
`pb.new.hire._scheme_for(draft)` (`pb_new_hire/models/studio.py`) — inputs: team (`department_id`), Country
of work (`payroll_country`), job, and the hand pick (`scheme_id`). It asks the pay run's chain for a person who
does not exist yet (`pb.scheme.map.resolve_for_draft`: rungs 2, 3, 4 judged on an in-memory employee, 5), then
the country's schemes. Every reader goes through it: step 2 tile and chooser, team defaults, step 3, the record
panel, Check, the payslip example, the usual answers, the values sent for approval.

### 2.3 Tests that the studio and the pay run agree
A9: for a real person with the same team, country and company, `Map.resolve(employee)` equals the studio's
answer in every branch (team line, division, rule, only scheme, none). A7: a hire sent through a rule-paid team
lands in that scheme's pay run (`_scheme_population`), and a team-line hire in the team's. A10: rize's shape (no
team line, a rule per country) → the rule's scheme shows, no amber line, the payslip example works.

### 2.4 Country of work, never work site (owner clarification)
Nothing in `_scheme_for`, the chooser, the defaults (`_most_paid`: team and `payroll_country`) or "Suggest who
pays each team" (people's `payroll_country`, their latest payslips) reads the work site / work location to
decide a scheme. The work site is read only to suggest the site box itself (`team_defaults`). The rules the pay
run already holds on rize read: India, Singapore, Indonesia — `payroll_country` (+ the company); Vietnam — a
list of employee codes (`barcode in [...]`), one of them limited to August 2026 — NOT the country of work, so a
new Vietnamese joiner is reached by no rule until a team line, a rule or the coming person-level assignment
covers them (the studio says "No pay scheme pays <team> yet" for that case, truthfully).
Note: the draft person carries only the country and the job; a rule that read other fields (none on the five
databases) would be judged without them.

### 2.5 Seam note for the person-level design
- ONE resolver: `pb.new.hire._scheme_for(draft)` for every screen of Add employee; underneath it
  `pb.scheme.map.resolve_for_draft` (a person who does not exist yet) mirrors `resolve_many` (a real person),
  which the pay run, the payslip, "Paid by" and Mapping's coverage all use.
- Order today: segment → team line → division → rule → only scheme → nobody.
- A person-level assignment by Country of work slots in as a rung in `resolve_many` (and the same rung in
  `resolve_for_draft`, judged on the draft's `payroll_country`) — at the position the owner chooses (above the team
  line if it must beat it). `_scheme_for` then needs no change beyond honouring a pick through that rung instead of
  only reporting it; the studio's chooser already sends `scheme_id`.

## 3. Section B — "Suggest who pays each team" and the rize dry run
### 3.1 Dry run on the hidden rize copy (rehearsal, `p8/nh8_map.py`, `NH8_MODE=dry`, rolled back)
Applied through the board's own write (fast lane on rize: no second approver for scheme moves), then every
active person's paying scheme compared before / after, then rolled back. Run twice (both rehearsals), same result.
| | Teams |
|---|---|
| Active teams | 32 (none mapped today; rize pays everybody through per-country rules, NH92) |
| Could be linked cleanly (nobody's paying scheme changes) | **14** — Indonesia 5, Vietnam 4, India 4, Singapore 1 |
| Mixed countries — majority link would move people | 2 teams, 8 people would change scheme (offered unticked) |
| Mixed countries — no country for more than half | 3 teams |
| An older line in the way (an archived scheme, NH95) | 1 (India) |
| Nobody with a country of work | 1 |
| Empty | 11 |
People checked 231; people whose paying scheme would change with the 14: **0**. Payslips, pay runs, payslip lines,
contracts: counts and newest change identical before / after. "Paid by" stale flags: all 313 people marked to be
worked out again by the map write (the nightly refresh then finds the same scheme) — on the copy only.
The coordinator's ruling counted 15 clean teams from my first live read; the map's one-line-per-kind-of-run
check makes one of them (7 people, India) an "older line in the way" team, so 14.

### 3.2 Live
Not applied (owner hold). Undo file therefore not needed; the apply script (`p8/nh8_map.py`, `NH8_MODE=apply`)
writes `/odoo/backups/newhire-p8-<ts>/rize_team_map_undo.csv` with every row created, when the owner releases it.

### 3.3 Client workbook (never committed)
`outputs/rize-team-pay-schemes-2026-11-26/rize-team-pay-schemes-2026-11-26.xlsx` (main checkout): sheet 1 the 5
mixed-country teams, one row per person (43 rows: team, person, country of work, scheme paying them today, the
scheme a majority link would give, would change yes/no); sheet 2 the 13 other unlinked teams with the reason;
sheet 3 the 14 teams that could be linked cleanly (proposed, not applied). Built from the copy's dry run
(`team-detail-from-copy.json` beside it).

## 4. Tests
### 4.1 New tests — 35 / 35 pass (+ the FS-12 page suite 23 / 23 with its updated refusals)
| # | Where | Result |
|---|---|---|
| A1–A10 | `pb_new_hire/tests/test_p8.py` `TestP8Scheme` (one / none / several, team mapped / unmapped, hand pick kept, old payloads, a real hire lands in the chosen scheme's pay run, example + usual answers follow the pick, studio = pay run in every branch, rize's rule-paid shape) | 10 / 10 |
| B1–B5 | `test_p8.py` `TestP8Suggest` (the rule incl. latest pay run, moves offered unticked, old line blocks, apply writes only ticked unmapped and changes nobody else / no payslip, gates + a late approval never replaces a line) | 6 / 6 |
| C1–C2, D1–D3, E1–E3, F1–F3, G1–G3 | `pb_new_hire/tests/test_p8_more.py` `TestP8More` | 14 / 14 |
| H1–H5 | `pb_form_studio_portal/tests/test_page.py` `TestP8PageBuilderRole` (role implied, own company only, builder tools, everything else refused incl. a forged context key, officer + employee unchanged) | 5 / 5 |
| FS-12 page suite | `TestFs12Page` with the HR-manager refusals moved to an HR officer, test 36 also proves an HR manager's publish keeps every company's switches | 23 / 23 |

### 4.2 Suites before / after (same-before/after rule)
`/pb_new_hire,/pb_scheme_map,/biz_access,/pb_form_studio_portal,/pb_onboarding,/pb_lifecycle,/pb_assets,
/pb_me_tax,/pb_zoho_bridge` on two copies of the P8 walk base (`nh12_base`); "before" = the four changed modules
of `origin/19.1` first in the addons path.
- before: 729 tests, 1 failed + 9 errors; after: 762 tests (+33), 2 failed + 1 error.
- Same on both sides: 1 (pre-existing).
- Only before (9): static / icon / dependants tests that read sibling modules the slim "before" folder hides
  (NH73) — environment.
- Only after (2), both real, fixed and re-run (32 / 32 with the P8 scheme tests): `test_p4_errors` (with A the
  country's only scheme now gives an example where the team has no line — the test now asks for no example only
  when neither has a scheme, and the example carries the pay-run sentence as a note) and the scheme-map static
  contract (an unprefixed class in the new drawer).

## 5. Browser walks (local `nh12_w`, Claude-in-Chrome, console read)
| # | Walk | Result |
|---|---|---|
| W-A | Studio step 2 (en): Indonesia → two radio cards, "Usual" on the default, "Teams Indonesia large scheme pays" first in the team list; a team with its own line re-ticks its scheme ("Because Indonesia Operation is paid by this scheme."); picking the other card → "You chose this pay scheme." + differs line + amber pay-run sentence with "Suggest who pays each team"; Malaysia → "No pay scheme for Malaysia yet" + link; Vietnam → "The only pay scheme for Vietnam." | pass (one fix: a space before "Use the usual one") |
| W-B | The studio link opens Mapping with the drawer: 1 can be set (2 of 2 in Singapore), 1 needs a choice (1 no country, 1 Indonesia), 2 empty; Set → the walk database has a second-person route → "Sent for approval" | pass (fixes: one-team wording, Set hidden while waiting) |
| W-D | Access: Logins for workers → New sign-in slips → tick → warning → press again → result → Print the slips: the slip (captured page) = the first slip's layout with a new first password; person card → Print a new sign-in slip → confirm → result | pass |
| W-E | HR manager login (no Lifecycle role): People › Joiners tab shown, 8 joiners, drawer opens with its steps; Lifecycle-team buttons hidden | pass (fix: buttons hidden) |
| W-F | Joiner drawer: "Laptop and equipment … Requested" | pass (fix: notes shown in the drawer) |
| W-H | HR manager → My Payobook page builder: "You are changing the page for DEMO Farms…", no history / reset, field settings read-only with the reason; took Work Phone off and published → stored as company 1's page by the HR manager, the page for every company unchanged | pass |
| W-vi | Vietnamese: step 2 intro, chooser ("Chọn chương trình lương cho người này", "Thường dùng", "trả lương cho 0 người"), tiles; `font` nodes 0 (NH61) | pass |
| W-340 | Studio at 340 px (NH45 method): scheme cards stack full width, `scrollWidth` 325 | pass |
| Console | errors only, every walk | clean |
C was walked by its tests as the person (the home's rows are a server list); no browser walk of /my in P8.

## 6. Release
### 6.1 Timeline (UTC, 26 Nov 2026)
| Time | Step |
|---|---|
| 00:38 | deploy notes read (no open START); my P8 lookup leftovers removed |
| 01:23–01:27 | prep (`nh8_prep.sh`): staged = commit, server trees = 19.1 base (nothing newer), PO gate (0 vendor word), dependencies x5, vi + id active x5, dumps x5 read back, file folders linked, counts, jobs, payroll-ready |
| 01:34–01:46 | rehearsals on hidden rize + payobook copies — passed; re-run 01:52–02:03 on the final commit after two suite fixes — passed |
| 01:47 | pushed `3a7686e7e..3d038fcc9` to `19.1` (fast-forward; nothing else of ours on 19.1 since) |
| 02:07 | START line; `nh8_tries.sh` in a systemd unit; quiet 15 min on rize/payobook/sudima, no HOLD, lock taken, go-live dumps x5 |
| 02:09:43 | service stopped; per-module scoped rsync of the four trees |
| 02:09–02:12 | `-u pb_new_hire,pb_form_studio_portal` one database at a time |
| 02:12:57 | service up; DONE line; lock released |
| 02:13–02:16 | verification; NOTE line |

### 6.2 Rehearsals
| Copy | Result |
|---|---|
| `nh8_rh_rize` (313 people) | exit 0 in 16–18 s, 0 ERROR, 0 Traceback; versions ok; payroll-ready identical (231 / 194 / 167); counts identical; B dry run as §3.1; look §6.4 |
| `nh8_rh_payobook` (4,583 people) | exit 0 in 19 s, 0 ERROR; payroll-ready identical (4,582 / 4,500 / 4,500); counts identical |
Both copies dropped (0 left), rehearsal service inactive.

### 6.3 Go-live
| Database | Exit / time / ERROR | Jobs active before → after |
|---|---|---|
| payobook_template | 0 / 21 s / 0 | 40 → 40 |
| p0clone | 0 / 17 s / 0 | 49 → 49 |
| sudima | 0 / 18 s / 0 | 91 → 91 |
| rize | 0 / 18 s / 0 | 92 → 92 |
| payobook | 0 / 18 s / 0 | 59 → 59 |
**Downtime 195 s.** Asset purge + `web.assets.version` per database. No job re-activated, no new job.

### 6.4 Verification (live, read-only)
| Check | Result |
|---|---|
| Trees | all 4 = `3d038fcc9` |
| Versions | manifest = installed x5 (pb_new_hire 19.0.1.7.0, pb_form_studio_portal 19.0.1.3.0; pb_scheme_map, biz_access files only) |
| Jobs | identical x5 (59/40/49/92/91 active) |
| Data right before the stop vs after | identical x5 (no technical notes this time) |
| Payroll-ready | identical x5 |
| New roles | implied by HR manager x5; internal users holding them: payobook 7, rize 1, sudima / template / p0clone per the role list |
| Server log since the stop | 0 ERROR / CRITICAL, 0 Traceback, 0 asset errors; one service process |
| Sites | five x 200 |
| rize map lines | 25 = before (nothing mapped) |
**What a new person gets on live rize (one team per country, read-only, rolled back):**
| Country | Scheme shown | How the pay run reaches them | Amber line | Payslip example |
|---|---|---|---|---|
| Indonesia | the Indonesia scheme | rule on the map (country of work) | none | renders, 6 lines |
| India | the India scheme | rule (country of work) | none | renders; values come from the pay data file, so no amount lines (said in its notes) |
| Singapore | the Singapore scheme | rule (country of work) | none | renders, as India |
| Vietnam | the Vietnam scheme (the only one) | NONE — the Vietnam rule is a list of employee codes, a new person is on no list | "No pay scheme pays <team> yet." + fix | renders, as India, with the sentence as a note |
payobook: company 5 Vietnam has 7 schemes → chooser, team line honoured, example 12 lines; companies 1–2 as before.
Live browser look was not done (NH76: never as the owner's admin). **Ask the owner for a two-minute look** on rize:
Add employee → Country of work India / Vietnam; People › Joiners as an HR manager; My Profile → Edit this page.

### 6.5 Left behind
- Live: nothing created anywhere. Backups `/odoo/backups/newhire-p8-20261126T0130Z/` (prep + go-live dumps x5,
  file-folder links, `previous-trees.tgz`, rollback plan); evidence `/tmp/newhire-p8-20261126T0130Z/` (incl. the
  copy's dry-run files `rh-map/`, names only there).
- Local: worktree `gitlocal-worktrees/nh-p8`; walk / test databases dropped (`nh12_base` kept as the next base).

## 7. Design bar (ledger rule 4)
- Hero moment — 9/10: pick Indonesia and the pay scheme tile turns into two cards with the usual one ticked;
  pick a team and it re-ticks itself; pick the other card and the screen says, in one line, why the pay run will
  not follow and how to make it.
- Zero dead-ends — 9/10: no scheme for a country → one press to the Mapping drawer that suggests it; an HR
  manager never meets a button the server refuses (board settings hidden, page builder controls that apply to
  every company read-only with the reason).
- Plain language — 9/10; Motion — 8/10 (cards, a rising done line); Keyboard — 8/10 (radio keys, Esc closes the
  drawer).

## 8. Open questions
1. **rize mapping (on hold)**: when released, 14 teams can be linked with nobody changing scheme; 5 mixed teams
   and 13 others are in the workbook for the client. The coming person-level assignment (by country of work)
   would make the mixed teams moot (§2.5).
2. **rize Vietnam**: the per-country rule for Vietnam is a list of employee codes, not the country of work, so a
   new Vietnamese joiner is paid by no scheme until a team line, a rule or the person-level assignment covers
   them. The screen says so; the owner may want the Vietnam rule to read the country of work like the others.
3. **E**: HR managers got the narrow board right; Welcome sessions, HR partner rules and the daily run stay with
   the Lifecycle team — confirm that split.
4. **H**: an HR manager builds the page of the company they work in; labels and "employee can change it" stay
   the administrator's (they apply to every company) — confirm.
5. **D**: "off where the Access desk is off" had nothing to hook onto (no switch exists); the button shows only
   where the desk card shows.
6. rize has 8 scheme-map proposals waiting from before this phase (not ours) — worth a look in Approvals.

## 9. Gotchas
NH92–NH99 in the ledger.
