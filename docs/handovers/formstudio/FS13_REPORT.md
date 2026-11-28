# FS-13 — My Payobook page builder and Form builder: six fixes from the browser check

Builder, tester and deployer, 2026-11-20 (UTC). Branch `fs-13` from `origin/19.1` @ `d7dca75d8`.
Code commit `3188d5a2d`, scripts `152da5fee` (staged trees = this commit).

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm untouched)
at `152da5fee`, **190 s down** (19:57:23–20:00:33 UTC). Deploy notes: START 19:55, DONE 20:00 (written by
the tries script), NOTE after the checks. Scripts: `docs/handovers/formstudio/fs13/` (clones of `fs1112/`).

## 1. What was fixed (one line each, then how)

| # | Finding | Fix | Test |
|---|---|---|---|
| 1 | Preview left out a field newly placed in the unpublished draft | Preview draws the draft exactly as Publish would make it | `test_21`, `test_22`; rehearsal "draft preview" ×5 copies; browser |
| 2 | Photo broken inside Preview | Preview's own photo address, administrator only | `test_23`; rehearsal; browser |
| 3 | Phone width: status text cut to "N." | Short pill "3 to publish" at phone width, nothing when there are no changes | browser at 390 px |
| 4 | "Work permit number" twice | Two real fields with one label; a "Field code" sub-line tells them apart (page builder list, Standard fields tab, fixed lines) | probe on all five sites; JS helper checked in the browser |
| 5 | "Page for" offered switched-off companies | Only active companies the administrator works in (company switcher ∩ their companies); a page kept for a company not offered survives the next Publish | `test_24` |
| 6 | Administrator with no employee record | `/my/profile` shows a short note with "Edit this page"; "Preview as" lists every employee they may see (logins first) | `test_25`; browser |

### 1. Preview = the draft as it would publish
`pb_form_studio_portal/models/page_builder.py`: `portal_page_render(employee, spec, company, preview=None)`.
With `preview` (a dict of the draft's field settings, possibly empty) the specs come from the new
`_pbfp_preview_fields(rec, spec, updates)`: every field the spec places that the page may show
(`_pbfp_eligible` = the engine's R14 rules: hidden pay figures, can_show), Country of Work honoured
exactly like `_pbfs_portal_fields` (custom fields limited to countries), the draft's own labels
(`labels` for own fields, `std_labels` for standard ones) and change settings, values read with the
engine's `_pbfs_raw` / `_pbfs_display`. Fields the draft does not place are NOT drawn (the old
"ticked but not placed → end of the first section" rule is for the live page only; Publish unticks
them). `preview` is administrator-only (`_pbfs_check_admin`). Nothing is written: no tick, no label,
no history line — the "Show on My Payobook" fact still changes only at Publish (test 21 asserts the
tick, the label and the audit count). The preview of the standard page before any Publish now shows
today's seven fields too (before, it showed none of them because none is ticked).
Controller `/my/profile/preview`: draft → `preview=payload['updates']`; no draft and no page →
`_pbfp_default_spec()` with `preview={}`; live published page → the normal path (exactly what employees get).
No engine model change.

### 2. Preview photo
The person card used `/my/photo/<id>/avatar_256`, which serves only a person's own face or a
colleague's (`pb.me.home._pbme_photo_allowed`) — an administrator previewing someone else got a 404.
New route `/my/profile/preview/photo/<employee_id>`: administrator only, for an employee they may
read (`_pbfp_preview_employee`: the engine's `_pbfs_portal_record` read check with all the
administrator's companies, not only the website's), streams `avatar_256`. The preview sets
`profile['avatar_url']` to it. Employees' own pages keep `/my/photo` (test 23).

### 3. Phone-width status
`page_builder.xml`: the sentence stays (`pbpb-chg-long`), plus a pill `pbpb-chg-short` ("%s to publish",
full sentence on hover) shown only at ≤ 760 px; the spacer is switched back on there so the buttons stay
right. With no changes nothing is shown (Publish is greyed anyway). Browser at 390 px: "1 to publish",
no word cut; the bar wraps Publish and close to a second line as before.

### 4. Same label, two fields
Finding: on all five sites the page builder list itself has **no** repeated label (probe: 0). The
"Work permit number" pair is in the **employee Form builder**, fixed section Personal › ID papers:
two real fields, `permit_no` (the standard work permit) and `vietnam_work_permit_number` (the
Vietnamese payroll details), both labelled "Work permit number" by the side panel's own table
(`pb_employee_vault` `_SPEC`, not ours to edit). The same check found more pairs (all real, different
fields):

| List | Same label | Fields |
|---|---|---|
| Employee › Standard fields tab | Phone | `private_phone`, `emergency_phone` |
| Employee › Standard fields tab | Expires on | `passport_expiration_date`, `visa_expire`, `work_permit_expiration_date` |
| Employee › Standard fields tab | Account holder (en) | `pb_other_name_holder`, `vietnam_bank_account_name` |
| Employee › fixed Personal | Work permit number | `permit_no`, `vietnam_work_permit_number` |
| Employee › fixed Pay & tax | Tax regime | `pb_in_tax_regime`, `vn_tax_regime` |
| Employee › fixed Pay & tax (vi) | Cư trú thuế | `pb_sg_tax_residency`, `pb_vn_tax_resident` |
| Contract (both lists), page builder | none | |

Fix (generic, so a future pair is covered too): `fs_words.js` `sameLabels(items, labelOf)` → the
folded labels two or more DIFFERENT fields share; the line of each such field gets a sub-line
"Field code: <code>" (the Field library's existing wording) — page builder list (`rowSub`), Standard
fields tab (`stdState`), fixed section lines (`fixedCode`, per section). One field listed twice:
`vietnam_tax_code` and `vietnam_social_insurance_number` appear in Pay & tax under both "Vietnam payroll"
(people paid in Vietnam) and "Vietnam (recorded boxes)" (anyone else with Vietnamese details) — the panel
draws one OR the other depending on the person, with different labels; kept as a truthful listing.

### 5. "Page for" = active companies the administrator works in
`_pbfp_companies()`: `env.companies & env.user.company_ids`, active only. On payobook.com nothing about
the list was wrong in the data (4 active companies offered, the archived "SG Company" was never offered);
the two companies the check saw as switched off were the ones switched off in the administrator's
company switcher — they are no longer offered. `page_publish` carries over, untouched, any company page
stored for a company not offered (archived since, or switched off), and keeps its fields shown (test 24).

### 6. Administrator without an employee record
* `/my/profile` (route override in our controller subclass, same path and options; everybody else goes
  to the unchanged parent): an administrator with no employee gets template
  `my_profile_no_employee` — "Your login has no employee record", two plain lines, button "Edit this
  page" to the builder. Employees and portal users without an employee: exactly as before (test 25 +
  rehearsal byte check).
* The Settings › System › Form builder › "My Payobook page" card opens the builder (browser);
  "Preview as" now lists every employee the administrator may see, logins first, "no login yet" marked —
  a site where nobody has a login yet (p0clone) can be previewed.

**`pb_me_portal` lines touched: none.** (`/my/profile` is overridden from our controller subclass.)

## 2. Tests (local, `--test-tags`; base `fs13_base` = `wf2p6_base` + the Form builder stack)

| Run | Result |
|---|---|
| `/pb_form_studio_portal` (9 FS-12 + 5 FS-13) | 14 / 0 failed — twice (before and after the last template change) |
| `/pb_me_portal,/pb_me_details,/pb_form_studio_reach,/pb_form_studio` | 83 / 0 failed |
| `/pb_form_studio_people` | 40 / 2 failed, both environment: `test_13` (no hourly-cost module, recorded in FS-12) and `test_l3_tax_source_binding` (`pb_me_tax` not installed on this base) |

PO gate (platform reader, locally and on the server): engine 498/498 vi/id, page builder 230/230 vi/id,
0 empty, 0 vendor word. New words: 9 (page builder) + 1 (engine). Grep of every added line: the vendor
word only in PO markers.

Browser (local, desktop + 390 px): administrator without an employee → the note and the button; builder
opened from the Settings card; a field placed in the draft → Preview shows it ("Birthday", empty value
"—") with the photo loaded from the preview's address; phone bar "1 to publish"; console clean.

## 3. Rehearsal (hidden copies of all five with the LIVE installed module set, jobs + mail off, dropped after — 0 left)
Prep `fs13_prep.sh`: staged trees = commit, live trees = `origin/19.1` (nothing newer on the server),
previous trees saved, PO gate passed, dumps ×5 read back (`/odoo/backups/fs13-20261120T191651Z/`),
job snapshots, read-only probes as the administrator.

| Copy | Upgrade (`-u pb_form_studio,pb_form_studio_portal`) | Data restored vs upgraded | Employee pages old vs new | Draft preview check |
|---|---|---|---|---|
| rize | 32 s, 0 ERROR | identical | 3 people byte-identical (My Payobook, My Profile, My details, My Leave) | new field drawn, photo 200 image, tick still off, employee page does not show it, draft removed |
| p0clone | 20 s, 0 ERROR | identical | no employee login on this site | administrator is sent to the Vietnamese address (`/vi/…`, language redirect the probe does not follow); same check passes on the other four |
| sudima | 17 s, 0 ERROR | identical | 1 person byte-identical | passes; the administrator without an employee record now gets the note + "Edit this page" (before: sent back to /my) |
| payobook | 21 s, 0 ERROR | identical | 3 people byte-identical (with the showcase page published) | passes; showcase page row unchanged (`409e6b37ba`) |
| payobook_template | 18 s, 0 ERROR | identical | no employee login | passes |

**rize payslips: 211 payslips / 6,914 lines old vs new, 0 differing** (31 computed, 180 refused identically).

## 4. Go-live and checks
* 19:55 START (no other open START; lock taken); no signed-in activity on rize/payobook since 19:40;
  fresh backups ×5 (template 31 MB, p0clone 32, sudima 36, rize 45, payobook 84); notes re-read right
  before the stop: no HOLD, no open START.
* 19:57:23 stop → 2 trees rsynced (= staged) → upgrades template 20 s, p0clone 19, sudima 18, rize 19,
  payobook 21 — all exit 0, 0 ERROR → asset purge + `web.assets.version` per database → 20:00:33 port
  listening; five sites 200.

| Check (after) | Result |
|---|---|
| Trees | both = commit |
| Versions | manifest = installed on all 10 rows (engine 19.0.1.5.1, page builder 19.0.1.0.1) |
| Jobs | = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); none re-activated; payobook job 156 off |
| Data before the stop vs after | identical ×5 (ticks: payobook 10 shown, others 0; page: payobook 1, others 0) |
| Showcase page "DEMO About me" (payobook) | page row unchanged (`409e6b37ba` before and after) |
| Server log since the stop | 4,464 lines, 0 ERROR, 0 Traceback, 0 asset errors; one service process |
| Probes as the administrator ×5 | page builder, Form builder fixed lists (126–131 lines), contract builder 21, side panel open; "Preview as" lists 1–20 people (p0clone 6 → 12: people without a login now included); sudima administrator (no employee record): `/my/profile` 200 with the note and the builder button |
| Same-label lists ×5 | as in §1.4; every pair now carries its field code on screen |

**payobook.com in the browser (QA login, already signed in; undone):** page builder opened; "Visa No"
placed in the draft → Preview drew it with the person's photo (loaded from the preview's address), 20
people offered; at 390 px the bar read "1 to publish"; Discard → no draft left, ticks unchanged (10).
Employee Form builder on a demo employee: fixed section ID papers shows "Work permit number — Field code:
permit_no" and "Work permit number — Field code: vietnam_work_permit_number" (and the Tax regime pair);
the Standard fields tab shows the code under Phone, Expires on and Account holder. Console clean.
Customer sites: server-side open-the-screen checks only (no sign-in).

## Not done / notes
* The two companies seen as "switched off" on payobook.com are active companies switched off in the
  company switcher, not archived ones (payobook has 1 archived company, which was never offered). With
  this fix "Page for" follows the switcher. If the owner meant something else, say which two.
* The page builder's own list had no repeated label on any site; the reported pair was in the employee
  Form builder (now told apart there).

## 5. Gotchas (ledger rows)
* FS13-1 A website page rendered with `request.render` takes the template's `name` as the browser tab
  title (the website layout reads it): name a page template with the screen words ("My Profile").
* FS13-2 `/my/photo` serves only one's own or a colleague's face: any page that shows SOMEONE ELSE to an
  administrator (a preview) needs its own guarded image route.
* FS13-3 A preview that must show "what Publish would do" cannot use `fields_for(…, 'portal')` (it is
  decided from the stored ticks): build the specs from the draft and the eligibility rules instead, and
  never write the tick.
* FS13-4 `env.companies` (the company switcher) is what an administrator "works in"; offering only those
  means a Publish must carry over the stored pages of every company it does not offer.
