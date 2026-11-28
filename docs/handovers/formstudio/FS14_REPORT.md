# FS-14 — My Profile: "Employee can change it" for the page's own personal boxes (+ three browser findings)

Builder, tester, self-reviewer and deployer, 2026-11-21 (UTC). Handover `FS14_HANDOVER.md` (main checkout,
untracked) + the coordinator's addition (Preview as list/preview disagree, search as you type, 7 missing
app icons on the employee page). Branch `fs-14` from `origin/19.1` @ `ce098597a`.

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm untouched) at
`4565cd2f7` (code `67bb872a0`), **171 s down** (01:49:30–01:52:21 UTC). Deploy notes: START 01:02, DONE 01:52
(the tries script), NOTE after the checks. Four tries waited for 15 quiet minutes (rize and sudima were in
use 01:02–01:32 UTC). No other deployer's START was open; the INBOX-BULK-BANK builder had not started.

## 1. Verified facts (do not re-derive)
* The five boxes (private phone, private e-mail, address = `private_street`, emergency contact, emergency
  phone) are changed ONLY through pb_me_portal's profile change request (`pb.profile.change.request`):
  draft → review page → submit → HR approves (approval engine, `pb_profile_change_approval.py`). The
  engine locks them for its own path (`pb_form_studio_people/models/form_studio.py:82-83,246-247`
  "Already on My details"). So TODAY = changeable, **HR approves** — not "saves at once" as the handover
  assumed.
* pb_me_portal already has a per-box whitelist: config parameter `pb_me_portal.editable_fields`
  (`pb_profile_change_request.py:36-37,110-116`, data record `pb_me_portal_data.xml:15-17`, noupdate),
  enforced by that model at create/write (strip), `_has_change`, `_diff` and `_apply_to_master` (skip), and
  by the stock page's inputs (`portal_templates.xml:713-721`). It had no screen. All five sites: the full
  list (all five on).
* The platform lets every signed-in person write their OWN user record's "safe" fields as super-user
  (`base/models/res_users.py:605-615`); the HR addon adds the five boxes (and work e-mail/phone, mobile,
  the rest of the home address …) to that list (`hr/models/res_users.py:27-50,125`). That is a direct
  call around My Profile's "Request a change" — open today for every employee login.
* Work e-mail and work phone: look-only for the employee today ("A pay formula can read it, so only HR
  changes it" — the engine's lock); FS-14 does not change them.

## 2. What was built (`pb_form_studio_portal` 19.0.1.0.1 → 19.0.1.1.0; one module)
* **Switch:** in the page builder's right-hand column, each of the five boxes now has "Employee can change
  it" (on/off). On (default): "Offered in "Request a change" on the page." + the existing note "HR approves
  every change". Off: "Look only: the employee sees it; only HR changes it." The canvas pencil, the
  "Employee can change" filter chip, the left-list sub-line and the "Request a change" count follow it.
  "Saves at once" is NOT offered for these five: their only write path is the HR-approved change request;
  a "saves at once" would be a new write path (handover: ship on/off only and say so).
* **One stored fact:** the switch writes pb_me_portal's own whitelist at Publish (no second store), one
  history line per box. Draft → Preview (draws the draft's switch) → Publish → history as the rest of the
  builder. "Reset to the standard page" puts the whitelist back exactly as before the builder first
  changed it (`page.profile_before`). Like every other field's "Employee can change it", the switch is
  one per site, not per company page.
* **Look-only on the server** (off = refused, value unchanged):
  1. the page's "Request a change" (forged box) → "Some of these details can only be changed by HR.
     Nothing was sent.";
  2. today's `/my/profile/request` route → the same refusal page instead of pb_me_portal's silent strip
     (which left an empty draft) — route override in our controller subclass;
  3. the engine's path (`pbfr__private_phone`) → refused by the engine's lock (unchanged);
  4. the platform's own-user write (`res.users.write` on oneself) of a CHANGED value of a look-only box →
     refused (`models/res_users.py`, new). HR users and administrators are never stopped; an unchanged
     value passes; while a box is on nothing changes (exactly today).
  HR editing the employee record is unchanged.
* **Preview as (coordinator item 1, 2):** "Find a person" searches as you type (250 ms pause) and at once on
  Enter; an older answer arriving late is ignored; when the person being previewed is not in the new list,
  the first person found is previewed — so the list and the preview never disagree (a one-result search
  previews that person at once).
* **pb_me_portal lines changed: none.** Never touched: `pb_lifecycle/`, `pb_pack_*`, standard addons.
* Words: 5 new (vi/id). Lucide icons, existing tokens; no emoji, no gradient.

Files: `pb_form_studio_portal/models/page_builder.py` (PROFILE_PARAM/PROFILE_BOXES,
`_pbfp_profile_editable`, `_pbfp_set_profile_editable`, publish/reset/render), `models/res_users.py` (new),
`controllers/portal.py` (form rows, send refusal, `/my/profile/request` override),
`static/src/js/page_builder.js`, `static/src/xml/page_builder.xml`, `tests/test_page.py` (31–36), i18n.

## 3. Tests
Local base `fs14_base` = `wf2p6_base` + the Form builder stack (engine, people, reach, page builder, My
details, bank panel) with this branch's code; `--test-tags`.

| Run | Result |
|---|---|
| `/pb_form_studio_portal` (14 FS-12/13 + 6 FS-14) | **20 / 0 failed** |
| `/pb_me_portal,/pb_me_details,/pb_form_studio_reach,/pb_form_studio,/pb_form_studio_people` | 242 run, 7 failed + 3 errors — all pre-existing: the same 8 pb_me_portal ones on `origin/19.1`'s page builder (baseline run, 93 tests: home cards test_05/06/page, home source test_01/12, profile flow test_01 = approval-request access, portal-only t1_7/t1_8) + people `test_13` and `test_l3_tax_source_binding` (environment, recorded in FS-12/FS-13) |

Numbered tests (handover 1–9, coordinator A–C):

| # | Test | Evidence | Result |
|---|---|---|---|
| 1 | switch visible for the five, absent/locked for locked fields | `test_31` (five carry it, on by default; work e-mail locked); browser: the switch in the settings column of Private Phone; work e-mail/phone keep the engine's lock | PASS |
| 2 | off → Publish → value shown, no box, direct POST refused, value unchanged | `test_32`: whitelist minus `x_phone`, history line, value shown, form boxes = the other four; refused: page form (forged), `/my/profile/request` (no request made), engine path, own-user write; unchanged value passes; HR edit works. Browser: Publish sheet "Private Phone: look only"; the employee's My Profile shows the phone, no box. Rehearsal on real copies (§5): box gone, own-user write refused, back on | PASS |
| 3 | on again → as before | `test_33`, `test_35` (stock route answers as today with all on) | PASS |
| 4 | "HR approves" lands in the approver's inbox, value unchanged until approved | `test_33`: request → submit → approval request exists, phone unchanged → approved → changed. (On = HR approves is today's only mode; "Saves at once" not offered, §2) | PASS |
| 5 | silent upgrade on copies ×5: My Profile byte-identical, showcase unchanged | §5 | see §5 |
| 6 | Preview shows the draft | `test_34` + browser (draft off → preview has no phone box; live page unchanged) | PASS |
| 7 | access matrix | `test_36`: HR manager (not administrator) cannot publish nor write the setting; HR writing their own record not stopped; an employee cannot reach another person's user record; FS-12 `test_11` still green | PASS |
| 8 | three payslips identical | §5: rize 211 payslips old vs new | see §5 |
| 9 | vi/id PO gate, forbidden word, console, 390 px, no builder code for employees | PO gate locally and on the server: 235/235 vi and id, 0 empty, 0 vendor word; added lines: the vendor word only in PO markers; employee My Profile: no builder script, no sideways scroll (browser window cannot go below 500 px; the page uses the one-column rules), console: only local-environment 500s (missing local file folder: site logo, favicon, worker bundle) | PASS |
| A | Preview as: one search result → that person previewed | browser: typed "Walk Binh" (no Enter) → list = 1 person, preview frame = that person ("Preview as DEMO Walk Binh") | PASS |
| B | search as you type; Enter still works | browser: as above without Enter (250 ms); "Walk Chi" + Enter → list and preview = that person | PASS |
| C | 7 missing app icons | §4 — cause found outside our modules; reported | REPORTED |

## 4. The 7 missing app icons on the employee page (coordinator item 3) — NOT ours; reported, not fixed
* The seven 404s on payobook.com (web server log, referrer `/bizapp/employees/<id>`): `/ai`, `/documents`,
  `/hr_appraisal`, `/hr_payroll`, `/hr_referral`, `/planning`, `/sign` `…/static/description/icon.png` —
  12 times each, all from employee record pages.
* Source: the standard HR addon's Employees action (`hr.open_view_employee_list_my`, path `employees`) has
  an empty-list advert in its `help` with 15 app icons (`hr/views/hr_employee_views.xml:672`, pictures at 705–765); 7 of
  those apps are not part of this build (checked locally: exactly those seven). The web client inserts that
  help into the live page to test whether it is empty (`web/static/src/core/utils/html.js:189-191`, called
  from `webclient/actions/action_service.js:431-433`), so the browser fetches every picture in it on every
  open of an employee record from that action, although nothing is shown. Live on payobook, rize and sudima
  the stored help is the standard one (21,496 characters, contains the icons).
* None of our modules adds or renders it (searched: no module of ours refers to that action or draws an
  action's help). So, per the instruction, not fixed. A fix from our side would be ONE data line in one of
  our modules (e.g. the People module or the debranding module) that replaces the Employees action's help
  with our own empty-list words without pictures — harmless and reversible; it also removes an advert for
  apps the product does not have. Say if it should be done.

## 5. Rehearsal
Scripts `docs/handovers/formstudio/fs14/` (clones of `fs13/`; on the server `/tmp/fs14_*`). Prep
(`fs14_prep.sh`): staging = the pushed commit `4565cd2f7` (hash), live tree = `origin/19.1` (hash, nothing
newer on the server), previous tree saved, server PO gate 235/235 vi and id, dumps ×5 read back
(`/odoo/backups/fs14-20261121T001609Z/`: payobook 84 MB, template 31, p0clone 32, rize 46, sudima 37),
file folders linked, job snapshots, read-only probes as the administrator. Hidden copies of all five with the
LIVE installed module set (restored from those dumps), jobs + mail off, dropped after (0 left).

| Copy | Upgrade (`-u pb_form_studio_portal`) | Data restored vs upgraded | Employee pages old vs new (My Payobook, My Profile, My details, My Leave) | Look-only switch on the copy |
|---|---|---|---|---|
| rize (has a published page) | 23 s, 0 ERROR | identical | 3 people **byte-identical** | off → whitelist minus the phone, box gone from the employee's page, own-user write refused; on → whitelist back |
| p0clone | 35 s, 0 ERROR | identical | no employee login | same (administrator path); preview answers the language redirect as in FS-13 |
| sudima | 23 s, 0 ERROR | identical | 1 person byte-identical | off/on ok (no employee login to open the page) |
| payobook (showcase page) | 18 s, 0 ERROR | identical | 3 people **byte-identical** | as rize; showcase page row unchanged (`409e6b37ba`) |
| payobook_template | 21 s, 0 ERROR | identical | no employee login | off/on ok |

**rize payslips: 211 payslips / 6,914 lines old vs new, 0 differing** (31 computed, 180 refused identically).
The FS-13 draft-preview check still passes on every copy (p0clone: language redirect, as before).

## 6. Go-live
* `origin/19.1` re-fetched right before: unchanged (`ce098597a`); live tree = `origin/19.1` (hash).
* 01:02 START (`fs14_tries.sh`; lock taken; notes re-read for HOLD / open START before every try and right
  before the stop). Tries 1–4 (01:07–01:37) refused to stop: signed-in activity on rize and sudima. Try 5:
  quiet since 01:32 on rize, payobook and sudima → fresh backups ×5 (template 32 MB, p0clone 33, sudima 37,
  rize 46, payobook 84) → 01:49:30 stop → 1 tree rsynced (= staged) → `-u pb_form_studio_portal`:
  template 21 s, p0clone 17, sudima 15, rize 16, payobook 16 — all exit 0, 0 ERROR → asset purge +
  `web.assets.version` per database → 01:52:21 port listening; five sites 200.
* Another deployer ("ChatGPT Calendar settings", `pb_hiring`) wrote START+DONE with a short restart at 01:18,
  while our START was open and before our stop; nothing of ours was running then (we were between tries).

| Check (after, `fs14_verify.sh`) | Result |
|---|---|
| Tree | = commit |
| Versions | manifest = installed `19.0.1.1.0` ×5 |
| Jobs | = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); none re-activated; payobook job 156 off |
| Data before the stop vs after | identical ×5 |
| Silent upgrade | whitelist unchanged ×5 (all five boxes changeable); pages unchanged (payobook showcase `409e6b37ba`, rize `32fb198c68`); ticks unchanged (payobook 10, rize 7, others 0); 0 changeable |
| Page builder ×5 (administrator) | opens; 5 personal boxes, all "employee can change" (before the upgrade the builder had no switch: 0) |
| My Profile as the administrator ×5 | unchanged hash ×5 |
| Employee pages after (My Payobook, My Profile, My details, My Leave) | payobook 3 people, rize 3, sudima 1: all 200, 0 failed (template, p0clone: no employee login) |
| Server log since the stop | 4,030 lines; 1 ERROR = a chat-presence write on rize refused at the moment of the stop (concurrent update), not a screen; 0 asset errors; one service process |

The administrator's My Payobook home hash moved on payobook, template and rize between the prep (00:19)
and the check; My Profile did not. The home is not touched by this module; the calendar deploy of 01:18
(`pb_hiring`) and the new `web.assets.version` fall in between. Employee pages were proven byte-identical on
the rehearsal copies (§5).

**payobook.com in the browser (QA login, already signed in; nothing changed):** page builder → Private
Phone → "Employee can change it" switch shown, on, with "Offered in "Request a change" on the page." and the
HR-approves note; "No changes yet"; console clean. Customer sites: server-side checks only.

## 7. Gotchas (ledger rows)
* FS14-1 A user writing their OWN `res.users` with "safe" fields is done as super-user
  (`base/models/res_users.py:605-615`), and the HR addon lists the employee's private boxes among them: any
  employee login can change its private phone/e-mail/address/emergency contact (and work e-mail, work phone,
  mobile, the rest of the home address) by a direct call, bypassing every approval. FS-14 closes it only
  for a look-only personal box.
* FS14-2 pb_me_portal's whitelist strips a non-whitelisted box silently at create: a forged post still
  makes an empty draft request. Refuse at the route before calling it.
* FS14-3 The web client inserts an action's `help` into the live page to test whether it is empty
  (`web/core/utils/html.js:189-191` → `createElementWithContent` = `document.createElement` + innerHTML):
  every `<img>` in an action's help is requested even when nothing shows it.
* FS14-4 Worktree-isolated agents: a shell command that mentions the checkout path together with `cd`,
  pipes or several steps is refused by the worktree guard; put such steps in a script file.

## 8. Owner questions
* **Employees can change some of their own details without HR, by a direct call (already true before
  FS-14).** A signed-in employee can change their work e-mail, work phone, work mobile and the rest of their
  home address (city, zip, state, country, second street line) directly, without "Request a change" and
  without HR seeing a request — the same way they could change the five personal details while those are
  changeable. Nobody can do it from a screen; it needs a hand-made call. FS-14 closes it only for a
  personal detail switched to look-only. Question for the owner: should every detail HR has to approve be
  closed to direct changes too? (Costs a small change; nothing changes on any screen; staff who edit their
  own details from the app's own profile window, if any, would be refused for those details.)
* **The seven broken pictures on the employee page** (§4): replace the standard Employees empty-list
  advert with our own words, no pictures? (One small change; the console stops showing the seven errors;
  nothing else on the screen changes.)
* "Saves at once" for the five personal details was not built: these details only change through HR
  approval today. If the owner wants some of them (say, private phone) to save at once, that is a new way
  of writing them and needs his yes.
  **Answered by the architect (FS-14b): all three — see §9.**

---

## 9. FS-14b — architect decisions on §8 (built, tested, deployed under the same rules)

Decisions: (1) "Saves at once" for the five personal details: not offered, left as is. (2) Close the
direct-change gap. (3) Stop the seven picture requests from our side.

### 9.1 What was built
* **No direct change of one's own details** (`pb_form_studio_portal` 19.0.1.1.0 → **19.0.1.2.0**,
  `models/res_users.py` rewritten, `controllers/portal.py` +1 method):
  * own-user write (`res.users.write` on oneself) by an employee (no HR role, not an administrator): EVERY
    field of the user record that writes the employee record (the HR addon's related fields — private
    phone/e-mail, every home-address part: street, street2, city, zip, state, country; emergency contact
    and phone; work e-mail, work phone, work mobile; and the rest of that list) is refused when the value
    really changes — whatever the My Profile switches say. Plain message: "Your details change only through
    "Request a change" on My Profile, where HR approves them. Nothing was saved." (vi/id). The address parts
    are therefore refused in both switch positions; with the address switch on, the address changes
    through "Request a change" (HR approves), exactly as the visible address does — the other parts are on
    no screen (the engine keeps them HR's: government forms).
  * the work contact: an employee's work e-mail and work phone ARE the e-mail and phone of their own work
    contact (`hr/models/hr_employee.py:122-124,824-842`; for a person with a login that is their own
    partner). A write of that partner's e-mail or phone asked by the employee is refused — also under the
    portal's super-user forms (judged by WHO asks). The standard portal address form (`/my/address/submit`,
    `/my/account`) answers in its own error area before anything is written (controller override of
    `_create_or_update_address`); the model refuses as a backstop (own-user write of `email` / `phone`).
  * Not stopped: HR users, administrators, the system (cron, sign-up), approved requests (applied as the
    approver), the Form builder's declared My Payobook boxes ("Saves at once" / "HR approves" through the
    engine, which writes the employee record, not the user record), "Request a change".
  * **pb_me_portal lines changed: none** (no edit was needed).
* **No broken app pictures** (`pb_employee_form_tidy` 19.0.1.3.0 → **19.0.1.3.1**, new
  `models/action_help.py`): when an action is handed to the browser (`ir.actions.act_window.
  _get_action_dict`, used by `/web/action/load` and `_for_xml_id`), an `<img>` of `/<app>/static/...` is left
  out when that app is not on the server. Nothing stored changes, an upgrade of the HR addon cannot bring
  the 404s back, pictures of apps that exist stay (8 of the 15 in the Employees advert). Upgrading this
  module also refreshes `pb_employee_bank_panel` (its only dependent; no file of it shipped).

### 9.2 Tests (local base = `wf2p6_base` + the Form builder stack + `pb_employee_form_tidy`)
| Run | Result |
|---|---|
| `/pb_form_studio_portal,/pb_employee_form_tidy` | **59 / 0 failed** (page builder 23 incl. 41–43; tidy incl. c1, c2) |
| `/pb_me_portal,/pb_me_details,/pb_form_studio_reach,/pb_form_studio_people,/pb_employee_bank_panel,/pb_form_studio` | 261 run, 7 failed + 3 errors = exactly the pre-existing set of §3 (none new) |

| # | Test | Evidence | Result |
|---|---|---|---|
| b1 | direct change of each field as an employee is refused, value unchanged | `test_41`: work e-mail, work phone, work mobile, street2, city, zip, state, country + the five personal details, address switch on AND off; a staff (internal) employee too; values unchanged; a non-employee setting (language) still saves. `test_42`: own-user write of e-mail / phone refused; portal address form refused with the plain words; work e-mail unchanged. Rehearsal on real copies (§9.3) | PASS |
| b2 | the normal "Request a change" flow still works | `test_43` (Form builder "Saves at once" box saves; personal box → today's change request), `test_33` (HR approves → value changes only then) | PASS |
| b3 | another employee's record unreachable | `test_36` (another person's user record), `test_42` (another person's contact through the portal form: refused by the standard portal rule, value unchanged) | PASS |
| b4 | HR still edits | `test_32` (private phone), `test_42` (work e-mail) by an HR user | PASS |
| b5 | silent upgrade: My Profile markup identical for 3 employees per site | §9.3 rehearsal byte check | see §9.3 |
| c1 | the Employees action sends no picture of a missing app | `test_c1` (15 stored, the missing ones left out, the others kept, stored help unchanged), `test_c2` | PASS |
| c2 | console clean on the employee record page | browser (local, administrator, `/bizapp/employees/<id>`): the page asks for 8 app pictures (all present), none of the 7 missing; no 404 in the console or in the server log (the only console lines: local-environment 500s of the missing local file folder and the worker bundle, as in §3) | PASS |

PO gate: 236/236 vi and id, 0 empty, 0 vendor word.

### 9.3 Rehearsal (after INBOX-BULK-BANK's go-live, so on the live module set incl. its changes)
INBOX-BULK-BANK wrote START 02:00 (it upgrades `pb_employee_bank_panel`, the dependent of
`pb_employee_form_tidy`); we waited for its DONE (02:31) before taking the dumps. Prep `20261121T021322Z`:
staging = commit (2 trees), live = `origin/19.1` (hash), server PO gate (page builder 236/236, tidy 48/48 vi
and id), dumps ×5 read back (`/odoo/backups/fs14-20261121T021322Z/`). Hidden copies of all five, jobs + mail
off, `-u pb_form_studio_portal,pb_employee_form_tidy` (refreshes `pb_employee_bank_panel` 19.0.1.1.0),
dropped after (0 left).

| Copy | Upgrade | Data restored vs upgraded | Employee pages old vs new | Direct changes on the copy | Employees action pictures sent |
|---|---|---|---|---|---|
| rize | 17 s, 0 ERROR | identical | 3 people **byte-identical** | work phone, city, work mobile, private phone: refused | 15 → 8 |
| p0clone | 17 s, 0 ERROR | identical | no employee login | refused | 15 → 8 |
| sudima | 16 s, 0 ERROR | identical | 1 person: differs — see below | no employee login with a portal account | 15 → 8 |
| payobook | 19 s, 0 ERROR | identical | 3 people **byte-identical** | refused; showcase page unchanged | 15 → 8 |
| payobook_template | 16 s, 0 ERROR | identical | no employee login | — | 15 → 8 |

**rize payslips: 211 / 6,914 lines old vs new, 0 differing.** Sudima: its only employee with a login is an
internal (staff) user; its pages carry session data that changes between two runs of the SAME code (proven
on live sudima: two read-only runs, all four page hashes differ — gotcha FS11-9). In the FS-14 rehearsal an
hour earlier the same comparison was identical; nothing in FS-14b touches page markup.

### 9.4 Go-live
* `origin/19.1` had moved to `17e48af44` (INBOX-BULK-BANK merged with FS-14): merged into `fs-14` (no force
  push) → `0f348ac4c`; the two module trees are byte-identical to the rehearsed ones (hash).
* 03:07 START (tag "Claude FORMSTUDIO FS-14b"; no other open START; lock). Try 1: quiet on rize, payobook,
  sudima since 02:52 → fresh backups ×5 → 03:09:47 stop → 2 trees rsynced (= staged) → upgrades template
  23 s, p0clone 17, sudima 17, rize 18, payobook 19 — all exit 0, 0 ERROR → asset purge +
  `web.assets.version` → 03:12:50 port listening. **183 s down.** DONE 03:13.

| Check (after) | Result |
|---|---|
| Trees / versions | 2 trees = commit; manifest = installed ×5 (page builder 19.0.1.2.0, tidy 19.0.1.3.1) |
| Jobs | = snapshot ×5; payobook job 156 off |
| Data before the stop vs after | identical ×5 |
| Silent upgrade | personal-box switches all on ×5 (unchanged), pages and ticks unchanged |
| Employees action | pictures sent 15 → 8 on all five sites |
| Employee pages after (My Payobook, My Profile, My details, My Leave) | payobook 3, rize 3, sudima 1: all 200, 0 failed |
| Server log since the stop | 2 ERROR lines = one chat-presence write on rize refused at the moment of the stop (as in FS-14); 0 asset errors; one process; sites 200 |
| payobook.com in the browser (QA login) | People list and an employee record (`/bizapp/employees/<id>`): only the 8 existing app pictures asked for, **console clean**; 0 picture 404s in the server log since the restart |

### 9.5 Gotchas (ledger rows)
* FS14-5 An employee's work e-mail and work phone are not stored on the employee: they are the e-mail and
  phone of the work contact, which for a person with a login is THEIR OWN partner — so the standard portal
  address form and an own-user write of `email` / `phone` change them. Guard by WHO asks (the portal writes
  the partner as super-user).
* FS14-6 `-u pb_employee_form_tidy` also refreshes `pb_employee_bank_panel`: wait for any deployer of that
  module and rehearse on dumps taken after its go-live.
* FS14-7 A probe that compares an INTERNAL user's pages before/after will differ between two runs of the same
  code (sudima has only such a login); judge byte-identity on portal employees.

### 9.6 Not done / left
* The login's own name, photo and time zone still copy to the employee record when the person changes them
  on their own user record (the platform's sync). Not in the decision's list; the time zone is read by pay
  formulas (working time). Say if they should be closed the same way.
* "Saves at once" for the five personal details: not offered (decision 1).
