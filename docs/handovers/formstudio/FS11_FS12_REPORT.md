# FS-11 + FS-12 — fixed sections list their fields; the My Payobook page builder

Builder, tester, self-reviewer and deployer, 2026-11-20 (UTC). Handover `FS11_FS12_HANDOVER.md` (main
checkout, untracked). Branch `fs-11-12` from `origin/19.1` @ `9ac8b8fae`.

**Result: BUILT, TESTED, REHEARSED — HELD, NOT LIVE.** Another deployer's START ("Claude WORKFLOW-2
P6e", 11:04 UTC, its evidence folder unchanged since 11:16) stayed open through 240 minutes of retries
(13:42–17:32 UTC). The rule is never to go over another deployer's open START, so nothing was changed on
the server (no START of ours, no stop, no file copied into the addons folder). Everything is staged and a
single command resumes (§6). The code is on `origin/fs-11-12` only — NOT merged into `19.1`, so no other
deployer ships it by accident.

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

## 6. Go-live — held
* 13:42 the retry loop started (`fs12_tries.sh`, every 10 minutes, 24 tries). While any other START of the
  day is open it writes nothing and changes nothing (writing our START then would block the other
  deployer's own check). Each try: "waiting, open START of Claude WORKFLOW-2 P6e". 17:32 finished:
  WAITING-OTHER. Two NOTE lines in `/opt/deploy-notes.md` say so (15:44 ready/waiting, 17:32 held).
* Rize/payobook also had signed-in activity during the afternoon (30 requests in the 15 minutes before
  13:58), so the 15-quiet-minutes rule would have held it at those moments too.
* **To resume** (once the P6e START has its DONE, or the owner closes it):
  `sudo systemd-run --collect --unit=fs12-tries /bin/bash /tmp/fs12_tries.sh 20261120T124830Z 24` — then
  `bash /tmp/fs12_after.sh 20261120T124830Z` (verification ×5, payobook.com showcase page, pages opened
  for three demo employees), DONE line, merge `fs-11-12` into `19.1` (fast-forward is not possible if 19.1
  moved: merge, re-run the FS-11/12 tags), push, this report's §6 completed. The go-live script refuses by
  itself if the live trees moved since prep (re-run `fs12_prep.sh` then), takes fresh backups ×5 right
  before the stop, upgrades `-u pb_form_studio,pb_form_studio_people,pb_form_studio_contracts
  -i pb_form_studio_portal` in the order template, p0clone, sudima, rize, payobook (16–21 s each on the
  copies), purges the assets and bumps `web.assets.version`, switches back off any job an upgrade
  re-activates, and puts everything back if an upgrade fails.
* Staged on the server: `/tmp/deployFS12/addons` = `7edc89990` (hash-checked), evidence and backups
  `/tmp/fs12-20261120T124830Z/`, `/odoo/backups/fs12-20261120T124830Z/`.
* Not done because of the hold: the go-live itself, the payobook.com showcase page (DEMO section with
  "DEMO Shirt size" + two standard fields + a banner — `fs12_publish.py` with `PUBLISH_DEMO=1`), the
  checks on the five live sites. The browser cannot be used on payobook.com without typing a password
  into a production site, which is not allowed; the after-script opens the pages server-side instead.
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

## 9. Owner questions
1. The other go-live from this afternoon (the Workflow Studio language fix) has been "started" since 11:04
   and has not moved since 11:16, which blocks every other go-live. Should that one be finished or called
   off, so this release can go live?
2. With a page published, My details shows one link "Company details — see them on My Profile" instead
   of a second copy of the same fields. Keep it like that, or show the fields in both places?
3. The personal boxes today's My Profile offers (private phone, e-mail, address, emergency contact) are
   always changeable through today's change request (HR approves). Do you want a switch to make any of
   them look-only?
