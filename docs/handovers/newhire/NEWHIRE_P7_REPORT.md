# NEWHIRE P7 — Country of work first; bank details in each country's own format (report)

Engineer, 25 Nov 2026 (UTC). Handover `NEWHIRE_P7_HANDOVER.md`. Engineering receipt: real technical names on
purpose. No credentials, client names or client data in this file.

**Result: GO. Pushed to `19.1` (`a58a486b8`, the deployed commit) and LIVE on all five databases, 466 s of downtime
(12:43:16–12:51:02 UTC).** Every database exit 0, 0 ERROR, nothing restored. abm and `_test_sudima_policy_20261119`
untouched. Nothing created on rize, sudima, p0clone, the template or payobook.

## 1. What changed on screen

### 1.1 Step 2 — the Country of work leads
- Field order: **Country of work** (its own row, first) · Team · Job · Manager · Work site (+ More: nationality).
  Intro: "Pick the country of work first. The teams and jobs there come first in their lists, and the currency,
  trial period, contract letter and papers follow it. The team then decides who pays."
- Country list: "Where your company already works" (countries with people, active pay schemes or the company's own
  papers list) then "Other countries". The list is the five a contract can hold (VN, ID, IN, SG, MY — NH1); with five
  entries a native list replaces the "searchable" box of the handover.
- Starting country (teal "why" line under the box): the user's last pick in this browser session ("Your last
  choice") › the company's country when the company works in one ("Your company's country") › where most active
  people work ("Where most of your people work"). A team sent by the org chart / Hiring brings its own country
  ("Where this team works") and beats the last pick.
- Team list: "Teams in <country>", then "Other teams" (no signal — always offered), and "Teams in other countries"
  behind a link "Show teams from other countries (N)". No team of that country → calm line "No team has people
  working in <country> yet." above the same lists.
- Job list: "In <team>", then "Held by people in <country>", then "Other jobs", then "A new job title…".
- Manager picker: before typing, people working in that country come first.
- Changing the country with a team of another country chosen: the team (and the job when it is the team's own) is
  cleared with a one-line notice "Team and job cleared: Finance has no one in India." and **Undo** (restores both;
  the mismatch warning then names the fix). A team with no signal is never cleared.
- "What this decides" moves the instant the country changes (currency, trial period, letter, papers); the Pay scheme
  tile reads "Pick a team · The team decides who pays." until a team is chosen. Subtitle: "They follow the country of
  work, and the team names the pay scheme." Right panel follows (same answers).
- Rail line when incomplete: "Country, team and job needed" / "Country and team needed" / … (country first).

### 1.2 Step 5 — the bank row follows the account's country
- New first box **Bank account in** (default: the country of work; any of VN, ID, IN, SG, MY, TH, KH, AU, "Another
  country"), then that country's boxes, each with a one-line hint and the country's own words.
- Codes take their shape while typing (IFSC in capitals, BSB `062-000`, digits only); inline sentences on leaving a
  box (the server's own sentences); India: the bank is filled from the IFSC's first four letters ("From the IFSC
  code"); Singapore / Indonesia: the bank code is filled from the bank ("From the bank"); switching the country
  clears the previous country's codes (bank, number and name stay).
- The approver's card on the hire and on the bank change shows "Bank account in" and the codes; the Bank
  Verification screen (the side panel's "Open Bank Verification") shows the same boxes with a "Bank account in"
  list; its queue cards show "IFSC code HDFC0001234"; the backend Bank requests list has the country and code
  columns.
- **My Payobook** (`/my/details/bank/<id>`, the welcome link's bank page): "Bank account in" (changes the boxes at
  once; a Change button without JavaScript), the country's code boxes with hints and required marks, SWIFT where it
  belongs; the request page and the sent request show the codes.

## 2. The rules as built

### 2.1 Which teams belong to a country (`pb_new_hire/models/places.py`)
A team belongs to country C when **(a)** the pay scheme of the team's OWN map line or its division's is of C
(`pb.scheme.map.resolve_for_teams`, rungs department / division), or **(b)** at least one active person of the team
has Country of Work C. **(c)** an explicit country on the team: no such field exists on this build (checked).
"The company's only scheme" (rung `only`) is NOT counted — it says nothing about a team, and counting it would put
every team of a one-scheme company under that country (NH89). No signal → "Other teams". Signals that all point
elsewhere → behind the link. One call `places(country, team, job, first day, kind, clear)` returns team groups,
jobs held there, managers there, sites there, whether the team / job still fit, and "What this decides": three
grouped reads + one map read for all teams (new batch `resolve_for_teams`; `resolve_for_team` calls it).
Send still accepts any team with any country (C5).

### 2.2 Bank formats as built (ONE definition: `pb_bank_ocr/models/bank_formats.py`, model `pb.bank.format`)
| Country | Boxes beyond bank + account number + name | Account number | Stored code read by bank files (`res.partner.bank.clearing_number`) |
|---|---|---|---|
| India | **IFSC code** (required) `^[A-Z]{4}0[A-Z0-9]{6}$`; bank filled from the IFSC prefix when the directory knows it | 9–18 digits | the IFSC |
| Singapore | **Bank code** 4 digits (required; filled from the bank when known) + **Branch code** 3 digits (optional) | 7–14 digits | bank code + branch code (`7171081`; the shipped GIRO layout's own pattern `^[0-9]{4}([0-9]{3})?$`) |
| Malaysia | SWIFT / BIC (optional) | 7–17 digits | — (SWIFT → the bank record's BIC, as before) |
| Indonesia | Branch (optional text), **Bank code** 3 digits (optional; filled from the bank) | 8–16 digits | the bank code |
| Vietnam | Branch (optional text) — the existing bank list | 6–19 digits | — |
| Thailand | **Branch code** 4 digits (optional) | 10–12 digits | the branch code |
| Cambodia | SWIFT / BIC (optional) | 6–16 digits | — |
| Australia | **BSB** (required, shown NNN-NNN) | **5–9 digits** | the BSB `NNN-NNN` |
| Another country | Branch (optional text), SWIFT / BIC (optional); IBAN accepted in the account box | 5–34 letters and digits | — |

Differences from handover §2.2:
1. **Australia account 5–9 digits, not 6–10**: the ABA (Direct Entry) file holds at most 9 digits; some institutions
   issue shorter numbers.
2. **Singapore bank code is required** (filled from the bank for the six banks in the directory); the branch code
   is optional (the shipped GIRO layout accepts the bank code alone).
3. **Indonesia's bank code is optional** (filled from the bank for the nine banks in the directory; the Indonesian
   layout already falls back to the directory by bank name).
4. **Vietnam = the old rule exactly** (NH91): a Vietnamese request keeps the old checks and sentences. No country
   at all (every older request, every import from the Updates sheet / pay data files) = the old rule too.
5. A "Bank account in" choice was added (not in the handover): the studio's Country of work can only be VN/ID/IN/SG/
   MY, so an Australian (or any other) account needs it; it also lets an expat be paid at home. Same choice on My
   Payobook and on Bank Verification.

Single source of truth (§2.5): the bank files that read a code (`pb_pay_delivery` payment-list layouts) already read
the account's own `clearing_number` first; P7 writes there on approval and nowhere else. SWIFT keeps its path
(`x_swift` → `res.bank.bic` when the bank record is made). The Vietnamese bank file reads no code (unchanged).
Exporters per country: India / Singapore / Indonesia layouts read `clearing_number` → filled; Vietnam, Malaysia,
Thailand, Cambodia, Australia: no shipped layout reads a code today (the value is on the account for the day one is
added).

### 2.3 New stored fields (only what was missing)
`pb.bank.change.request`: `pb_bank_format` (Selection, country names from `res.country`), `x_bank_code`,
`x_branch_code` — frozen for the approvers like the other details (`_REVIEW_FIELDS`), stamped into the approval
revision only when set (so no existing approval's stamp changes), carried to the account on approval. `pb_bank_ocr`
19.0.1.6.1 → 19.0.1.7.0. Payroll-ready: unchanged code — a NEW request in a country's format cannot be sent or
approved without its required code, so "bank on record" from a new request always has it; people already on record
are untouched (B4: identical counts on the copies and live, §5).

### 2.4 Files touched outside `pb_new_hire`
| Module | What | Version |
|---|---|---|
| `pb_bank_ocr` | the format definition, 3 fields, gates, mirror to the account, approval card, OCR schema, cockpit boxes, queue card line, list/form columns, portal view/update/set-format | 19.0.1.7.0 (-u) |
| `pb_me_details` | bank page boxes + "Bank account in" + route `/my/details/bank/<id>/country`, shaping script, styles | 19.0.1.0.3 (-u) |
| `pb_people_advanced` | the old window's bank path carries `bank_format` + codes when a caller sends them (`BANK_EXTRA_KEYS`); old callers unchanged | none (Python) |
| `pb_scheme_map` | `resolve_for_teams` batch; `resolve_for_team` calls it | none (Python) |
| `pb_learn` (+ `docs/tutorial_poc/author/data.js`) | Add employee lesson step 3 and the replica follow the new order; anchor `nh-country` | none (static files) |

## 3. Tests (numbers per handover §3)

### 3.1 New tests — 18 / 18 pass (`/pb_new_hire:TestP7Places,TestP7Bank`, `/pb_bank_ocr:TestP7BankFormats`, plus the new hiring test)
| # | Test | Result |
|---|---|---|
| C1 | rule a (Singapore scheme), b (people), other countries, no signal; jobs held there; managers there; every team in one list | pass |
| C1b | a company with one scheme and nobody's country set (rize-shaped): nothing hidden, every team "Other teams" | pass |
| C2 | country change: team + job don't fit, sentence, decides without the team; Undo case keeps the team with the mismatch; fitting / no-signal team never cleared | pass |
| C3 | default: most people (tie broken by test data), company's country when it works in one; load() answers | pass |
| C4 | prefilled team brings its country (people majority, scheme); team_defaults | pass |
| C5 | Vietnam-paid team + India accepted and applied; old bank payload keeps the old check; new payload names the IFSC | pass |
| C6 | `places()` on 32 teams + 320 people: median < 300 ms (and on the rize copy 37–176 ms per country, payobook copy 24–473 ms, §5) | pass |
| B1 | each country good / bad samples, stored shapes, directory fills, words and hints, old rule | pass |
| B2 | request → account: India IFSC, Singapore 7171081, Australia 062-000; send refused without the IFSC; approval card rows | pass |
| B3 | the same definition serves the studio row (every country's boxes), My Payobook view, Bank Verification boxes; studio send refuses a missing / bad IFSC, carries country + code into the proposal rows and the bank change | pass |
| B4 | older / Vietnamese changes: old checks and sentences; imports keep no country; revision stamp of an older change unchanged; an Indian on record without an IFSC is still on record | pass |
| B5 | the payment list's bank identity returns the IFSC from the account | pass |
| B6 | the reader's schema has the codes; a read IFSC is stored in shape and checks pass | pass |
| P1 | My Payobook: view = spec, update shapes the IFSC, change of country, nonsense refused, cockpit boxes | pass |
| H-P7 | Hiring bank paper read without the Singapore bank code: not sent, the leg says which code is missing | pass |
| static | no vendor word, icons exist, `_t` form (`TestNewHireStatic`) | pass |

### 3.2 Suites before / after (same-before/after rule)
Two copies of the walk world (`nh6_base`), `-u` of `pb_new_hire, pb_bank_ocr, pb_me_details, pb_me_portal, pb_me_tax,
pb_me_team, pb_me_privacy, pb_me_expense, pb_me_trip, pb_me_project_time, pb_me_portal_comm, pb_me_portal_website,
pb_learn, pb_people_advanced, pb_scheme_map, pb_employee_bank_panel` with the same tags; "before" = the six changed
modules from `origin/19.1` placed first in the addons path.
- before: **974 tests, 57 failed + 19 errors**; after: **991 tests (+17 new), 57 failed + 7 errors**.
- 62 not-ok are the same on both sides (web-page tests answering through this laptop's setup, Learn node suites,
  Bank OCR web flows …).
- Only before (14): static / icon / Learn / scheme-map static contract tests that read sibling modules the slim
  "before" folder hides (NH73) — environment.
- Only after (2): `test_hiring` f3 and h3 — real: a Singapore hire's Hiring bank paper now needs the bank code
  before it is sent, and the leg said "could not be read". Fixed (`490d7e4f6` "Hiring bank paper says which
  country code is missing"): the leg says what is missing; the tests' reader returns the code; new test H-P7.
  Re-run of `TestFromHiring`, the P7 classes and the static gates: **38 / 38**.
- Learn authoring: `gen_learn_data.py --check` clean (vi_VN.po untouched), `test_scenario_rules.py` 20 refusals +
  1 acceptance, `check_contract.py` the same 3 pre-existing govreports lines.

## 4. Browser walks (Claude-in-Chrome; local `nh11_p7` = copy of the P4 walk world upgraded; console read)
| # | Walk | Result |
|---|---|---|
| W1 | Indonesia (starting country "Where most of your people work"): Teams in Indonesia (2) / Other teams (3), link "(3)", tiles IDR / 3 months / Indonesian letter / KTP; team + job picked, scheme tile "Indonesia monthly staff"; switched to Singapore → "Team and job cleared: Indonesia Operation has no one in Singapore. Undo", tiles SGD + "Pick a team"; Undo → team and job back, the other-countries group opens, amber mismatch with "Use Indonesia"; pressed → country back, warning gone | pass |
| W2 | company with no links (rize-shaped) | test C1b + rize copy (§5): Malaysia → "No team has people working in Malaysia yet.", Other teams (15), link (17); India → Teams in India (6), Held by people in India (25) | pass |
| W3 | bank: Indonesia boxes (bank code filled "014" from BCA, "From the bank"); India (IFSC typed `hdfc 0001234` → `HDFC0001234`, bank "HDFC" "From the IFSC code", account 4 digits → "9 to 18 digits. This one has 4.", `HDFC1234` → the 11-character sentence); Singapore (OCBC; account 2 digits → sentence); Australia (`062000` → `062-000`, 10 digits → "5 to 9 digits. This one has 10."); Malaysia (SWIFT `mbbe my kl` → `MBBEMYKL`); Vietnam (5 digits → "6 to 19 digits") | pass, after one fix: an Indonesian bank code stayed under Singapore when the country was switched (NH90) — cleared now |
| W4 | India hire sent from the studio (State Bank of India from the IFSC `SBIN0000300`): proposal rows "Bank account in India", "IFSC code SBIN0000300"; approved → bank change BCR waiting, "All format checks passed.", card rows; approved by the second person → account `clearing_number = SBIN0000300`, bank on record, the bank file layout reads it | pass (the local letter leg fails as always — no PDF tool on the laptop, NH20) |
| W5 | employee's own bank page (Indonesian user language): upload → "Rekening bank di: India", "Kode IFSC *" with hint, "9 sampai 18 digit."; Australia → BSB box; send without IFSC → "Ketik kode IFSC…"; with it → "Dikirim untuk persetujuan"; sent page shows "Kode IFSC: HDFC0001234"; at 390 px (real phone frame) scrollWidth 390, every box full width | pass, after two fixes (country row laid out in a column, NH85; lazily loaded script, NH84) |
| W6 | org chart door with the team "Product & Technology" while the last pick was Singapore → India ("Where this team works"), scheme "India monthly staff" | pass |
| W7 | studio at 340 px (NH45 method): `scrollWidth` 340, nothing wider | pass |
| W8 | Vietnamese and Indonesian: step 2 intro, groups, link, tiles, the cleared notice + Undo ("Urungkan"), step 5 bank boxes ("Mã IFSC", "Từ 9 đến 18 chữ số"), My Payobook (Indonesian) | pass |
| W9 | console: clean on every walk except OWL patch errors right after a language switch while Chrome's own page translation was rewriting the page (NH88, environment); clean after a reload with translation off | pass |

## 5. Release (risky tier, P6's ritual; scripts `p7/`)

### 5.1 Timeline (UTC, 25 Nov 2026)
| Time | Step |
|---|---|
| 10:47 | deploy notes read: DOCSTUDIO PDFFIX-2 START open → built meanwhile; then Codex Attendance Rules (11:30–11:40) and WFSETUP P10c (11:50–12:17) shipped; waited for each DONE |
| ~11:59 | merged `origin/19.1` (no overlap with the six modules), pushed `d1c4dbf5c..a58a486b8` (fast-forward) |
| 12:00–12:05 | prep (`nh7_prep.sh`): staged = commit; server trees of all six = 19.1 before P7 (`d1c4dbf5c`), nothing newer; PO gate (0 vendor word); pb_new_hire's 128-module closure installed ×5; vi + id active ×5; dumps ×5 read back; file folders linked; counts, job snapshots; payroll-ready probe ×5 |
| 12:07–12:16 | rehearsal on hidden rize copy (first try: my probe read a column the copy did not have yet → probe fixed to plain SQL, rehearsal re-run, §5.2) |
| 12:18–12:25 | browser walk on the rize copy (tunnel, two throwaway logins made on the copy, dropped with it) |
| 12:16–12:30 | rehearsal on hidden payobook copy — passed, copy dropped |
| 12:30 | START line; try 1 refused itself (signed-in activity on payobook until 12:23) |
| 12:40 | try 2: quiet since 12:25 on rize/payobook/sudima; go-live dumps ×5; notes re-read; lock taken |
| 12:43:16 | service stopped; per-module scoped rsync; addons = staged |
| 12:43–12:50 | `-u pb_bank_ocr,pb_me_details,pb_new_hire` one database at a time (§5.3) |
| 12:51:02 | service up; five sites 200; DONE line; lock removed |
| 12:51–12:54 | verification (§5.4); NOTE line 12:54 |

Backups `/odoo/backups/newhire-p7-20261125T1200Z/` (prep dumps, go-live dumps, file-folder hard links,
`previous-trees.tgz`). Evidence `/tmp/newhire-p7-20261125T1200Z/` on the server.

### 5.2 Rehearsals (hidden template copies; jobs, mail servers, incoming mail off first; staged code first)
| Copy | Command | Result |
|---|---|---|
| `nh7_rh_rize` (313 people) | `-u pb_bank_ocr,pb_me_details,pb_new_hire` | exit 0, **104 s**, 0 ERROR, 0 Traceback; versions ok; payroll-ready (231 people, 194 bank on record, 167 payroll-ready) **identical** before/after; data identical except +4 technical change notes (2 jobs, 2 server actions — as P5b/P6); 18 jobs re-activated by the cascade on the copy (all off there; live keeps its own state) |
| `nh7_rh_payobook` (4,583 people) | same | exit 0, **83 s**, 0 ERROR; payroll-ready (4,582 / 4,500 / 4,500) identical; counts identical; copy dropped |
Look on the copies (`nh7_look.py`): rize starts on Indonesia ("most"); Malaysia → 0 teams of Malaysia, 17 of other
countries, 15 with no signal; India → 6 teams, 25 jobs held there; `places()` 30–176 ms per country (rize), 24–473 ms
(payobook, first call warm-up 473). Bank boxes per country as §2.2.

Browser on the rize copy (Claude-in-Chrome through a tunnel; console clean; nothing sent): start Indonesia "Where
most of your people work"; Malaysia → "No team has people working in Malaysia yet.", Other teams (15), "Show teams
from other countries (17)", tiles MYR / 2 months / general letter / MyKad; India → Teams in India (6), Held by people
in India (25), INR; step 5 bank India → IFSC code; switched to Malaysia → SWIFT / BIC.

### 5.3 Go-live (order payobook_template → p0clone → sudima → rize → payobook)
| Database | Exit / time / ERROR | Jobs active before → after |
|---|---|---|
| payobook_template | 0 / 72 s / 0 | 40 → 40 |
| p0clone | 0 / 67 s / 0 | 49 → 49 |
| sudima | 0 / 68 s / 0 | 91 → 91 |
| rize | 0 / 72 s / 0 | 92 → 92 |
| payobook | 0 / 80 s / 0 | 59 → 59 |
Asset purge + `orm_signaling_assets` + `web.assets.version` per database. No job re-activated, no new job row.
**Downtime 466 s.**

### 5.4 Verification (live, read-only)
| Check | Result |
|---|---|
| Trees | all 6 = commit `a58a486b8` |
| Versions | manifest = installed ×5 (pb_bank_ocr 19.0.1.7.0, pb_me_details 19.0.1.0.3, pb_new_hire 19.0.1.6.0; the three files-only modules unchanged) |
| Jobs vs prep snapshot | identical ×5 (59/40/49/92/91); payobook job 156 off |
| Data right before the stop vs after | identical on payobook, payobook_template, p0clone, sudima; rize +4 technical change notes (as rehearsed); only expected lines moved (3 new columns, module versions) |
| **B4 payroll-ready** | identical before/after ×5 — payobook 4,582 / 4,500 / 4,500, rize 231 / 194 / 167, sudima 678 / 642 / 0, template 1/0/0, p0clone 12/0/0 (people / bank on record / payroll-ready) |
| Compiled code | ×5: country-first step 2, bank row by country, Bank Verification country list, My Payobook shaping script, Learn replica; old window still registered |
| Live look (`nh7_look.py`, rolled back) | rize as on the copy (Malaysia 0/17/15, India 6 teams); sudima: Vietnam 40 teams, default "company"; payobook: Vietnam 41 teams (company 5), default "company"; template / p0clone: no people with a country → default none, every team "no signal" (offered) |
| Server log since the stop | 0 ERROR / CRITICAL, 0 Traceback, 0 asset errors; one service process |
| Sites | five × 200 |
| Rehearsal copies | both dropped, file folders gone, rehearsal service stopped, throwaway logins gone with them |
Live browser look on the five sites was not done (NH76: never as the owner's admin; walks ran locally and on the
rize copy). **Ask the owner for a two-minute look** on rize: People › Employees › Add employee → Country of work India,
then step 5 bank.

### 5.5 Rollback plan (written before the stop; not needed)
As P6: a failing database inside the window → the six previous trees from `previous-trees.tgz`, the failed and
already-upgraded databases restored from the go-live dumps, FAILED line. After go-live → report first; files from the
tar; data only if it changed and the owner agrees. The three new columns are additive (empty on every existing row).

### 5.6 Left behind
- Live: nothing created anywhere. payobook_template and p0clone have nobody with a Country of Work and a company
  country outside the five, so their step 2 starts on "Choose a country" (every team offered once one is picked).
- Server: backups and evidence folders above. Local: worktree `gitlocal-worktrees/nh-p7`; local test databases
  (`nh11_*`) dropped.

## 6. Design bar (ledger rule 4)
- **Hero moment — 9/10**: pick India and the screen re-sorts itself — India's teams and jobs on top, ₹, the trial,
  the letter and the papers move at once; switch to Singapore and the Indian team steps aside with one honest line and
  an Undo.
- **Zero dead-ends — 9/10**: every team and job stays reachable; a country with no team says so; the bank row works
  for any country (Another country, IBAN); a paper that lacks a code says which.
- **Plain language — 9/10**: the country's own words (IFSC code, BSB, Bank code, Branch code) with a hint each.
- **Motion — 8/10**: tiles re-land on change (existing), the notice rises; no new decorative motion.
- **Keyboard — 8/10**: native selects (type-ahead), codes shaped while typing, Undo is a button in the tab order.

## 7. Open questions
1. Owner: is "Where your company already works" the right label for the first country group (the handover said
   "Where you already have people"; the group also holds countries with a pay scheme or papers list but no people)?
2. Owner: Singapore bank code required (auto-filled for the six banks we know) — right, or optional like Indonesia?
3. Australia (and Thailand, Cambodia, Malaysia) have no bank file layout yet; the codes are stored on the account
   for when one is added.
4. Rize: no team is linked to a pay scheme (P6 §3.1), so "Teams in <country>" is built from where people work. Linking
   teams to schemes in Mapping would make the lists exact.
