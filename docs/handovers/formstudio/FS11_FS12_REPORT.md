# FS-11 + FS-12 — fixed sections list their fields; the My Payobook page builder

Builder, tester, self-reviewer and deployer, 2026-11-20 (UTC). Handover `FS11_FS12_HANDOVER.md` (main
checkout, untracked). Branch `fs-11-12` from `origin/19.1` @ `9ac8b8fae`.

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm untouched) at
`e23380c24` (`origin/fs-11-12` → fast-forwarded into `19.1`), **192 s down** (17:39:37–17:42:49 UTC).
The first attempt was held 13:42–17:32 UTC behind the open START of "Claude WORKFLOW-2 P6e" (11:04); the
coordinator called that START off at 17:34 (nothing of it had been deployed) and its change — **`pb_lifecycle`
files only, commit `9ac8b8fae`, Workflow Studio words follow a language change without a hard refresh** —
**shipped inside this go-live** (scoped rsync, no `-u`, version 19.0.1.21.0 unchanged, covered by the asset
purge, the `web.assets.version` bump and the restart). Deploy notes START 17:37, DONE after the checks.

## 1. What was built

### FS-11 (R29) — "Drawn by the screen" sections show their fields
* Every fixed section of the Form builder canvas lists the fields that part of the screen really shows,
  in on-screen order, under the screen's own sub-headings, with a kind icon and chips: Hidden /
  Hidden for <countries> / Renamed / On My Payobook / Locked (full reason on hover and in the settings
  column) / Only <country> (Country of Work) / Worked out by the screen.
* Clicking a field line opens the same settings column as the Standard fields tab (hide, rename per
  language, Country of Work, My Payobook ticks). Lines the screen works out itself (the Profile summary,
  the Vietnamese pay-scheme settings, the bank block) are listed for truth and open nothing.
* Chip text "Fixed layout — fields can be hidden or renamed" (with the count, folds open/closed; open on a
  desktop, folded on a phone); legend line updated.
* Opened from Full details / the full contract form, the canvas shows THAT page's tabs as fixed sections,
  read from the combined form (helpers, pictures and status widgets left out, as the Standard fields tab
  does), followed by the open sections.
* "Find a field on this screen" above the canvas: highlights every match (open tiles and fixed lines),
  unfolds the section, scrolls to it; Enter = next, Shift+Enter = previous, Esc clears. Sticky.

Seams: engine `_pbfs_fixed_items(host_key, surface)` (hook), `_pbfs_full_sections`,
`_pbfs_surface_sections`, `_pbfs_fixed_lists`; `get_studio` returns `fixed` and reads the surface from
the context key `pbfs_surface` (no signature change: `pb_form_studio_explorer` overrides
`get_studio(self, host_key)`). Maps beside the screen code, in the bridges:
`pb_form_studio_people/models/fixed_sections.py` (the vault's `_SPEC` read at run time + the Vietnam
pay group + the FS-9 bank block + the Profile summary) and `pb_form_studio_contracts/models/fixed_sections.py`
(`_TERMS`).

### FS-12 (R30) — the My Payobook page builder ("My Profile")
New module `pb_form_studio_portal` 19.0.1.0.0 (depends engine, people host, reach, `pb_me_portal`,
`pb_me_details`).
* **Where:** "Edit this page" in the header of My Profile (tenant administrators only) and a second card
  "My Payobook page" in Settings › System › Form builder. Both open the page builder in the app.
* **Builder:** studio bar (changes, Build / Preview, Discard, Publish, close); left: Fields (search, chips
  All / Own / Standard / On the page / Not on the page / Employee can change, Country of Work filter) and
  Page (page per company where there is more than one company, history with Restore, Undo the last
  publish, Reset to the standard page); centre: the page — header (tint, banner, heading, sub-line), the
  person card (fixed, always first), the sections (title per language, one/two columns, move up/down,
  remove when empty), field tiles (drag between/within sections, keyboard, take off), "Add a section",
  "Request a change" (automatic), side blocks "My requests" and the My details door (fixed, order can
  swap); right: settings of the header / section / field (label per language — the field's own label,
  the same stored fact as the Form builder; width half/full; section; "Employee can change it" and
  "HR approves" / "Saves at once" with the engine's refusals and reasons).
* **Preview:** the real My Profile page, rendered by the server for a chosen employee (desktop or phone
  width), from the administrator's draft, look-only (banner "Preview as …", form fieldset disabled,
  links inert).
* **One truth:** placed on the page = "Show on My Payobook". A field ticked in the employee Form
  builder appears on the page (end of the first section until moved); unticked there, it leaves.
* **Rendering:** with a published page, My Profile is drawn from it through `portal_page_render(employee)`
  (built only from `fields_for(…,'portal')` + `portal_values`); without one, My Profile is today's page,
  byte for byte. "Request a change" lists exactly the changeable fields on the page in page order:
  fields the administrator made changeable go through `portal_check` → `portal_apply` (saves at once,
  history line) or ONE `pb.me.detail.request` HR approves (the My details path of R14); the personal
  boxes today's page offers (private phone/e-mail/address, emergency contact/phone) go through today's
  profile change request (draft → review → submit, HR approves).
* **My details:** with a page published, the "Company details" card on My details becomes one door to
  My Profile (no second copy of the same fields).
* **Banner:** JPG/PNG/WebP told apart by their first bytes (never the name), ≤ 2 MB, no SVG, stored as
  a private attachment, served by `/my/profile/banner/<id>` only to signed-in people whose page shows it
  (and to administrators).
* **Reset:** removes the page (history kept) and puts every field's My Payobook tick back as it was before
  the page was first published.

**Exact `pb_me_portal` lines changed: none.** The render seam is a template inheritance from this module
(`pb_form_studio_portal.portal_my_profile_page`: `t-if` on the page's `div.pbme`, one `t-call` before it,
one `t-set hero_actions` inside the hero call) plus a controller subclass (`_profile_card`). Without a
published page the employee's My Profile is byte-identical (test 6).

**Fixed blocks:** the person card is always first (cannot move or be removed); "My requests" and the
"Family, ID papers, photo and bank account" door stay in the side column, their order can swap; the
"Request a change" card follows the sections automatically.

**Spike decision — builder in the app with a live preview, not on the portal page.** The overlay's look
(tokens, buttons, icons) comes with the app bundle; carrying it into the website page would put a
second copy of those styles against the website theme and make every employee's page ready to load
builder code. In the app, the page is shown exactly as an employee gets it — rendered by the server, as
a chosen employee — which the page itself never could (it is always the viewer's own page). Employees
download one small stylesheet and no builder code.

## 2. Tests (local, `--test-tags`; base `fs1112_base` = `wf2p6_base` + the Form builder stack, TIDY-E,
FS-9 bank panel, My details, tax, native look, leave set-up installed with the 19.1 code)

| Run | Tests | Failed + errors |
|---|---|---|
| FS-11 + FS-12 tags | 17 (people 5, contracts 3, page builder 9) | 0 |
| Suites: engine 41, people 50, contracts 36, lists 13, reach 62, page builder 11, My details 34, My Payobook 125 | 290 (+ re-run lists/page builder 20) | 6 + 2 — all pre-existing |

The pre-existing set is the one FS-10 / Batch 2 recorded on this kind of base: My Payobook home cards
(test_05 grid, test_06 font), home source (test_01, test_12), profile change flow (test_01, access on the
approval request), portal-only door (t1_7), people `test_13` (no hourly-cost module here). The lists
performance test failed once (7 queries > 6) — a real regression from this branch (the page host read its
layout on every host lookup); fixed by caching (`_pbfp_host_sections`, cleared on publish/reset; every
worker follows), re-run green.

## 3. Results per numbered test

| # | Test | Evidence | Result |
|---|---|---|---|
| 1 | every fixed section lists its real fields (map = screen) | `test_fs11_fixed` people 01/01b/01c: the side panel drawn for three filled-in people (paid in VN / ID / SG) — every line it draws is in the map AND every field the map names is drawn; Full details: the listed boxes = the visible boxes of the combined form; contracts 01/01b: `_cd_terms` = map, full contract form = form | PASS |
| 2 | chips correct | people 02: hidden / hidden for India / renamed / On My Payobook / locked (birthday) facts on the lines; browser: chips drawn (Locked with reason on hover, Only Vietnam/India/Singapore, Worked out by the screen) | PASS |
| 3 | click → settings → hide → Publish → gone | people 03 (Place of birth leaves the panel), contracts 03 (Location leaves the contract panel); browser: clicking Work Phone in "Top of the page" opens its settings column | PASS |
| 4 | "Find a field" | browser: "tuesday" → highlighted, section unfolded, scrolled into view; count "1 match"; sticky | PASS |
| 5 | phone width | the canvas uses the overlay's one-column rules; fixed sections folded on a phone; search sticks under the studio bar | PASS (walk at 500 px, the browser window could not go narrower) |
| 6 | no page → byte-identical | test 06: My Profile HTML with this module vs with its template switched off, tokens removed: identical; no layout made by opening it. Rehearsal: employee pages before vs after the install on the copies (§5) | PASS |
| 7 | section, 3 fields (own, standard, country-limited), order, widths | test 07 (+ browser: section added, renamed, field added, published, My Profile shows it) | PASS |
| 8 | on the page ⇄ tick, both ways | test 08 | PASS |
| 9 | Request a change | test 09: boxes = exactly the changeable fields in page order; HR approves → request in the approver's inbox, value unchanged until approved; saves at once → saved + history line; blood type refuses "Saves at once"; personal box → today's change request | PASS |
| 10 | locked field never changeable | test 10: page publish and direct call refused, forged POST refused, nothing written; wage never offered | PASS |
| 11 | access matrix | test 11: employee and HR manager refused on every builder call; another person's values by id refused; no button for employees; no employee link → back to /my; administrator gets "Edit this page" | PASS |
| 12 | banner ok / too big / wrong kind; tint; words | test 12: PNG ok, > 2 MB refused, SVG refused, GIF named .png refused; signed-out visitor never gets the picture; a gradient "tint" refused; heading in vi; id falls back to English | PASS |
| 13 | preview look-only | test 13 + browser (banner "Preview as …", fieldset disabled); employee and HR manager get 404 | PASS |
| 14 | history, undo, reset | test 14: two publishes in history, an older version read back, reset = standard page + ticks back | PASS |
| 15 | two workers | nothing about the page is kept in a worker except the section list of the host (cleared through the registry on publish/reset, which every worker follows); the page itself is read from the database on every request | PASS (by design) |
| 16 | payslips; upgrade keeps the page | rehearsal §5 | see §5 |
| 17 | words, forbidden word, console, 390 px | §4 | PASS |

## 4. Words, white-label
PO gate (platform reader, locally and on the server): engine vi/id 497 each, people 137, contracts 47,
page builder 220 — all parse, 0 empty, 0 vendor word in any msgstr; the JS words carry the JS marker.
New words: FS-11 10 (engine) + 39 (people map labels), FS-12 211. Grep of every added line: the vendor word
appears only in code identifiers and a test's assertion. Browser: console clean on My Profile, the page
builder, the Form builder (Full details); the page at 388 px has no sideways scroll.

## 5. Rehearsal
## 5. Rehearsal (hidden copies of all five, jobs + mail off, `dropdb --force` after — 0 copies left)
Scripts `docs/handovers/formstudio/fs1112/` (cloned from the WF2 P6 set; on the server `/tmp/fs12_*`).
Backups first: `/odoo/backups/fs12-20261120T124830Z/` (payobook 84 MB, template 31, p0clone 32, rize 46,
sudima 35; read back; file folders linked; previous trees saved). Server PO gate passed (§4). Live trees
before = `origin/19.1` (hash). The copies have the LIVE installed module set (restored from the live dumps).

| Copy | Upgrade (`-u` engine, people, contracts `-i` page builder) | Data restored vs upgraded | Notes |
|---|---|---|---|
| rize | 18 s, 0 ERROR, 0 Traceback | identical | **211 payslips / 6,914 lines, 0 differing** (31 computed, 180 refused identically); with a page published on the copy: My Profile, My details, My Leave, My Payobook home 200 for 3 employees and the administrator |
| p0clone | 16 s, 0 ERROR | identical | no employee login on this site; pages and screens open |
| sudima | 17 s, 0 ERROR | identical | |
| payobook | 21 s, 0 ERROR | identical | with a page published on the copy: all pages 200 |
| payobook_template | 16 s, 0 ERROR | identical | employee pages byte-identical |

After the upgrade on every copy: the employee builder lists 126–131 fixed lines, Full details 14–15 tabs,
the contract builder 21 lines and its form 4–5 tabs, the Field library 3 screens, the page builder 81–82
fields with 0 ticks and no page (silent install), side panel and employee page open.

Test 6 on real data: the rehearsal's first page comparison counted the bundle addresses and the
registry stamp in the page (both change with ANY install) and so said "different" on rize, sudima and
payobook; the probe now leaves those out (locally proven: the only differences were those two plus the
administrator's own "Edit this page"). The byte check was re-run on fresh copies of rize, payobook and
sudima with the final commit (`fs12_bytecheck.sh`, final stage `7edc89990`):

| Copy | People opened | My Profile, My details, My Leave (and My Payobook home) before vs after |
|---|---|---|
| rize | 3 employee logins | **byte-identical** (the home too) |
| payobook | 3 employee logins | **byte-identical** |
| sudima | its only login on an employee is the platform's internal user | page bodies identical; the only line that differs is the session script an internal user's page carries (it differs between two runs of the SAME code too) |

The administrator's own My Profile differs as designed: "Edit this page" in the header.

## 6. Go-live
* Held first: 13:42–17:32 UTC the retry loop waited behind the open START of WORKFLOW-2 P6e (24 tries,
  nothing written). 17:34 the coordinator closed it ("CALLED OFF"); the scripts were taught that a
  "CALLED OFF" line closes a START, and to judge a line by WHO wrote it (the called-off line mentions this
  go-live by name, which the inherited check had read as our own line — and the inherited HOLD check would
  have ignored a HOLD that named us; both fixed and tested on a copy of the notes).
* P6e added (`fs12_reprep.sh`): staging = 5 trees = commit; live `pb_lifecycle` = `bf2dba174` (hash);
  previous trees saved again; its PO file parses (2,122 entries); live version 19.0.1.21.0 = shipped (no
  roll-back).
* 17:37 START; no signed-in activity on rize/payobook since 17:22; fresh backups ×5 (template 31 MB,
  p0clone 32, sudima 36, rize 46, payobook 84 MB, read back); notes re-read right before the stop: no HOLD,
  no open START; lock taken.
* 17:39:37 stop → 5 trees rsynced (= staged) → `-u pb_form_studio,pb_form_studio_people,
  pb_form_studio_contracts -i pb_form_studio_portal`: template 20 s, p0clone 18, sudima 19, rize 18,
  payobook 21 — all exit 0, 0 ERROR → asset purge + `web.assets.version` per database → 17:42:49 port
  listening; five sites 200.

| Check (after) | Result |
|---|---|
| Trees | all 5 = commit |
| Versions | manifest = installed version on all 25 rows (engine 1.5.0, people 1.5.0, contracts 1.4.0, page builder 1.0.0, lifecycle 1.21.0) |
| Jobs | = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); none re-activated; payobook job 156 off |
| Data before the stop vs after | identical ×5 |
| Silent install | no page on any site; no tick added (payobook's 1 existing tick unchanged) |
| Server log since the stop | 3,986 lines, 0 ERROR, 0 Traceback, 0 asset errors; one service process |
| Screens as the administrator ×5 | My Payobook home and My Profile open (p0clone/sudima: the administrator has no employee there → back to /my, as before); employee builder fixed lists 126–131 lines; Full details 14–15 tabs; contract builder 21 lines, contract form 4–5 tabs; Field library 3 screens; page builder 81–82 fields; side panel and employee page open |
| WF2 P6e ×5 | Workflow Studio opens (its start-up call answers); its words at the new address 200 with `private, no-cache` and an ETag; the Studio's page asks for the new address |
| My Leave + employee home ×5 | opened server side for the newest employees with a login (5/1/5/5/1): 0 failed |
| Time off ×5 | its list and form open; rows read |

**payobook.com (demo):** the showcase page is published and KEPT: today's fields, the existing company
details, and a section "DEMO About me" (Vietnamese/Indonesian names too) with **DEMO Shirt size**, Work
mobile and Date of birth, a banner picture (purple) and a purple header. With it in place, My Payobook home,
My Profile, My details and My Leave open (200) for three demo employees and the administrator.
**Language follows (P6e):** the QA login switched en → vi → en; after each switch a fresh page load got the
words of the new language at once (the reply says `"lang": "vi_VN"` with Vietnamese words, then English
again), with a new ETag each time and `Cache-Control: private, no-cache` THROUGH the web server (no
two-day cache any more); the language was put back to what it was. Not done: a click-through in the
browser on payobook.com — signing in there would mean typing a password into a live site, which this
agent may not do; every page above was opened over the real web stack instead.

**The `KeyError: 'active'` of 10:47:55 UTC on payobook:** not a screen. It is a hand-made data call —
`hr.leave` `search_read` asking for the field `active` (time off has no "active" field in this version),
sent by the QA login seconds after the P6c check cancelled its demo time off, in the same burst as
`res.users.write`, `hr.employee.write` and the deletion of its timesheet lines: the WORKFLOW-2 P6 checker's
own clean-up (archiving the throwaway DEMO employee). It does not come from the time off "Sent back" work
and no person met it; nothing to fix.

## 7. Candidates for the next pages
My details (family, ID papers, photo, bank — its own flows, so only arrangement, not new fields), the
My Payobook home tiles (order, which tiles show), My Leave (the request form's optional boxes), Payslips
(the card's figures), My requests. Each would be a new host with its own fixed blocks; the engine and the
builder are ready to take them.

## 8. Gotchas (ledger rows)
* FS11-1 A component getter named like a template loop variable (`lang` vs `t-as="lang"`) wins: OWL's
  loop scope is created from the component, an assignment onto a getter is silently dropped — every
  language box showed English. Never name a getter after a loop variable.
* FS11-2 The engine's `_pbfs_hosts()` is asked on every screen (People list included): a host whose
  definition reads the database adds a query to every page — caught by the lists performance cap. Cache
  such parts with `ormcache` and clear them where they change (registry → every worker).
* FS11-3 `get_studio` is overridden by `pb_form_studio_explorer` with a fixed signature: pass new
  options through the context (`pbfs_surface`), not as a new argument.
* FS11-4 Website pages pick their language from the website (URL / cookie), not from the user's
  language: test translated page words through the render helper with a language context.
* FS11-5 Locally `--dev=xml` breaks a view whose file path cannot be resolved (`None + str` in
  `get_view_arch_from_file`); walk without it.
* FS11-6 The open-the-pages probe (`fs1112/fs12_probe.py`) opens real pages over the in-process web stack
  with a server-made session (no password); the web stack lists no template database, so a hidden
  rehearsal copy is made visible only while its probe runs (jobs and mail are off on it).
* FS11-7 `odoo-bin i18n export` lists tuple items next to translated calls as words (`VNSIJOIN`,
  `ssnid` …) — FS7-6 again; take only real sentences into the .po.

* FS11-8 The deploy-notes check must read WHO wrote a line (the second column), not whether a line
  mentions us: a closing line naming our go-live was taken for our own line (the other START looked open
  for ever), and a HOLD naming us would have been ignored. A START may also be closed by "CALLED OFF".
* FS11-9 Page comparisons before/after an install must leave out the bundle addresses and the
  `registry_hash` of the page's session script (both change with any install); an internal user's page
  carries more session data that differs between two runs of the same code — compare employee logins.

## 9. Owner questions and answers
* Answered by the architect (owner's standing approval): the link from My details to My Profile stays once
  a page is published; a look-only switch for private phone / e-mail / address / emergency contact is NOT
  built — today those boxes go through the profile change request, which has no per-box switch; adding one
  needs a stored setting, the builder's toggle and a change to which boxes the request form offers. Left for
  a follow-up.
* No new owner question.
