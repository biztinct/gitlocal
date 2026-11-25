# NEWHIRE P4 — report (payslip example, From Hiring, Many at once, "Confirm they joined")

Built on worktree `gitlocal-worktrees/newhire` (branch `newhire`), 2026-11-25. Not pushed, nothing deployed, no server access.
Local walk DB `nh6_base` = copy of `nh4_base` (P3b walk world) + `-u pb_new_hire` + scratch `walk_seed_p4.py` (real formulas on
the four walk schemes, a 300-rule "Indonesia large scheme" paying team "Large intake", a team "Unpaid team" no scheme
pays) + `seed_hiring_p4.py` / `seed_hiring_p4b.py` (three signed offers) + `walk_p4_roles.py` (the two walk HR users got
Hiring's recruiter role so they may read offers). **The approval route was switched back ON for the walk** (scratch
`route.py`, `NH_ROUTE=route`): new hires on `nh6_base` now wait for Dewi Lestari.

## 1. What was built

`pb_new_hire` 19.0.1.3.0 → **19.0.1.4.0**. New dependencies `pb_hiring`, `pb_updates` (both installed on all five live
databases, FACTS_ONBOARD §M3 — the facts doc names pb_hiring as safe to depend on).

| Part | Files |
|---|---|
| B — the example (commit 1) | `models/payslip_example.py` (new): `payslip_example`, refusals, try-lock, seat check, the savepoint, in-memory lines, notes, the LRU cache; `models/create_ext.py` (`PREVIEW_CTX`: no leg runs for a preview); `record_panel.js` (the dark box, four states, panel scroll-into-view); `new_hire_studio.js` (`exampleReady`, `refreshExample`, `runExample`); xml, scss (`.pbnh-pvo*`, `.pbnh-pvno`, shimmer, the panel scrolls on its own); `tests/test_payslip_example.py` (P1–P6, 8 tests) |
| A — From Hiring etc. (commit 2) | `models/hiring.py` (new): tile probe, `hiring_offers`, `offer_draft`, received-in-Hiring marks on step 5, `_validate`/`_values` (offer re-check, `pb_nh_offer_id`), `many_at_once`, legs `hiring` and `hiring_close`, the `pb.hiring.offer` overrides; `welcome_legs.py` (LEG_ORDER + an "amber but kept" leg answer); `studio.py` (`offer_id` draft key); `step_who.js` + xml + scss (three tiles, the offer list); `step_docs.js` / `studio_util.js` (choices for received rows, the `hiring` bank choice); `record_panel.js` (bank line); `new_hire_studio.js` (source, offers, bring across, the Hiring door, Many at once); `static/src/js/hiring_patch.js` + `static/src/xml/hiring_patch.xml` (Hiring and Updates patches); `tests/test_hiring.py` (H1–H9 + H5b, 9 tests) |

**Files touched outside `pb_new_hire`: none.** Hiring and Updates are extended by inheritance, a JS `patch()` and
template inheritance only.

### 1.1 The payslip example as built (FACTS_CORE §F followed)
`payslip_example(draft)` → `{ok, month_label, month, lines:[{name, amount, band}], gross, deductions, net, employer_cost,
currency:{symbol, name, position, decimals}, scheme, scheme_id, notes, cached, took_ms}` or `{ok: False, reason, fix, step
[, busy]}`.

1. Refusals first (name, first day, team, country, wage or pay-scale amount, fixed-term end), each with the step to go to.
2. Scheme from `decides()` (D3). None → "No pay scheme pays this team yet." (step `role`).
3. Cache lookup (below). On a miss: seat check (`hr.employee._pb_check_seats(1)`, NH7), then `pg_try_advisory_xact_lock`
   on (company, company calendar) — taken → `{busy: True}` (NH54).
4. `_values(draft)` — the studio's own builder — minus the welcome / bank / documents / org-chart / **manager** keys (NH51).
5. Inside `with cr.savepoint(): … raise _Rollback()` as superuser with `tracking_disable, mail_notrack, mail_create_nolog,
   mail_create_nosubscribe, pb_nh_preview, NEWHIRE_WRITE`: `pb.people.onboard.wizard.create_employee(vals)` (the whole
   P1/P2 create chain incl. pay scales, the org chart hook, the fill-in, the person's changed usual answers, trial end;
   `create_ext` returns before the legs in preview); `onchange_employee_id` for the month; one draft `hr.payslip` (full
   calendar month of the first day, `formula_config_id`, `calculation_method='formula'`);
   `_get_formula_input_values(config, provenance=…)`; `hr.formula.sample.data.new(...)._evaluate_rules_with_dependencies(
   inputs, readonly=True, errors=…)`; one `hr.payslip.line.new()` per rule `_create_payslip_lines_from_formulas` would make
   (same filter: appears on payslip + `wants_number`; same fields incl. `pay_role`, `component_detail`); totals from
   `pb_pay_totals()`. Plain values copied out, then rollback and `invalidate_all()`.
   `preview_from_payslip` has no line builder to reuse (it returns column values), so the line building mirrors
   `_create_payslip_lines_from_formulas` — said here as the handover asked.
6. Lines shown: earning / deduction bands in payslip order, zero lines hidden; a "detail" line (inside another total) is
   band `info` (shown smaller). Employer cost and gross/taken off in the summary line; take-home large.
7. Notes: "Worked out by <scheme> for a full <Month>, from the scheme's usual values." always; the part-month sentence when
   the first day is not the 1st; pay data file / connected system notes when an input that DECLARES such a source fell to
   its usual value; the D3 mismatch sentence; "This pay scheme has no take-home line…" when there is no net line.

**Cache** (P6, needed — see timings): in-memory `OrderedDict` on the registry, 256 entries, 5 minutes, keyed on database,
company, scheme id + write date + rule count + newest rule write date + an md5 of every rule's content (NH53), and every
draft key except the name (the name only changes the words, rebuilt per call).

**Seat-limit sentence, verified (P4b)**: "An example cannot be shown because your plan has no free employee place." / "You
can still send the hire: once it is approved, it waits in Approvals until a place is free." — the test sends at the limit,
approves, sees the request `approved` with the refusal as its block reason and no employee, frees the place, presses
`retry_apply` as the sender → the employee exists.

### 1.2 What `action_confirm_joined` really reuses (FACTS_ONBOARD §K1 corrected, proved by H5 / H5b)
| Hiring leg | With the studio's employee linked first | What `pb_new_hire` does |
|---|---|---|
| `_ensure_employee` | returns `offer.employee_id` | links it: `offer.employee_id = employee` (Hiring's own link) |
| `_mark_applicant_hired` | runs (stage → hired) | — |
| `_ensure_contract` | returns `offer.contract_id`; else reuses the first contract found by search | links the studio contract; guard override searches, never creates |
| `_ensure_package` | draft `pb.employee.comp` from the offer lines (none existed) | — runs |
| `_ensure_benefits` | idempotent | — runs |
| `_ensure_login` | would make a WORK-EMAIL login whatever the studio chose | override under `pb_nh_joining_employee_id`: links `login_user_id` to the studio's sign-in, never makes one |
| `_ensure_case` | `_open_case` idempotent, but OPENS one when HR chose none | override: links the running checklist, never opens one |
| `_hand_over_buddy` / `_hand_over_laptop` | run against the studio's checklist (laptop note lands on the studio's laptop request) | — run |
| `_file_signed_copy`, state `joined`, `_stamp_hire_date`, requisition `_on_filled`, `_tell_them_they_joined`, hooks_p8 `joined` automation | run | — |

The close runs as a LATER leg (`hiring_close`, after login / case / buddy / equipment) so the links exist — see §3.1.

### 1.3 Every patch point in Hiring's and Updates' screens
| Where | What | Without `pb_new_hire` |
|---|---|---|
| `PbHiringBoard.prototype.setup` (`@pb_hiring/js/hiring_board`) | reads `hr.group_hr_user` once (`onWillStart`) into `pbnhHR` | not patched |
| `PbHiringBoard.prototype.p6OpenConfirm` (defined in `pb_hiring/static/src/js/hiring_p6.js`) | HR user + an offer → `doAction('pb_new_hire.action_new_hire_studio', {pb_nh_offer_id, pb_nh_step: 'who'})`; otherwise Hiring's dialog | Hiring's dialog |
| new `p6OpenConfirmPlain`, `p6FromOfferPlain` | Hiring's own dialog (`super.p6OpenConfirm`) | do not exist |
| template `pb_hiring.P6DrawerJoining` (extension) | after "Confirm they joined": ghost button "Confirm without the form" (HR only) | not inherited |
| template `pb_hiring.RoleDetails` (extension) | after the offer panel's "Confirm they joined": "Confirm without the form" (HR + recruit + signed) | not inherited |
| `PbUpdatesDesk.prototype.loadHome` (`@pb_updates/js/updates_desk`) | with context `pb_nh_joiners_sheet`: starts a lasting update and opens the blank new-employee sheet | not patched |

All three Hiring doors (drawer door, Next box `confirm_open`, offer panel `closeOffer` → `p6FromOffer`) call
`p6OpenConfirm`, so one method covers them (NH59).

## 2. Results

### 2.1 Numbered tests
`-u pb_new_hire --test-tags /pb_new_hire` on `nh5_b` (clean copy of the P3a database): **112 / 112 pass** (95 P1–P3b +
8 Part B + 9 Part A; static gates included). The 8 Part B tests also passed alone 3 times while being built; the 9 Part A
tests twice.

| # | Test | Result |
|---|---|---|
| P1 | 20 different drafts, none cached: every count in §2.2 equal, no commit-time hook left, no cache signal, no employee | pass |
| P2 | example = a REAL payslip (same draft sent through the fast lane, draft payslip for December, `compute_sheet()`): gross, deductions, net and employer cost equal to the cent; lines in the payslip's own order; zero lines and lines with no pay role hidden | pass |
| P3 | CPF switched off → deductions 0, net = gross, no employer cost, the zero line hidden; meal 300 → gross +150 | pass |
| P3b | the words: first note; part-month note only when the first day is not the 1st; mismatch note + the country's money; pay data file note for an input that declares a spreadsheet source; no vendor name | pass |
| P4 | no scheme (step `role`), no wage (step `pay`), no name (step `who`), a reported formula error ("…could not work out an example: the formula for … divides by zero."), non-HR → AccessError | pass |
| P4b | seat limit: the sentence, then a real send at the limit is approved and held with the reason, and added by "try again" once the place is free | pass |
| P5 | another session holds the calendar lock → `busy` at once (no wait); free → ok | pass |
| P6 | `took_ms` returned; same draft cached; another name cached (words rebuilt); a rule change empties the cache | pass |
| H1 | the list: team / job / manager / first day / wage + money; received chips (identity, degree, bank, photo) and missing (payslip, tax); background check amber; an HR user without Hiring's roles sees none; a dropped offer is not waiting | pass |
| H2 | bring across: every value, the buddy, `offer_id`; an offer in VND for a Singapore team → no wage + the sentence; step 5 marks (bank `hiring` default, "Received in Hiring"); a gone offer refused | pass |
| H3/H5 | apply: certificate filed (unverified), originals still on the Hiring request, photo set; the ID card held with the valid-until sentence; bank request waiting for the second person; offer joined on the first day, applicant hired, ONE contract (linked), ≤1 login, ONE checklist (linked), ONE laptop request, pay package made, signed papers filed, the buddy hand-over ran | pass |
| H4 | unreadable bank paper → request stays draft, amber sentence, other papers still filed; HR chose no checklist → Hiring's close opens none | pass |
| H5b | fast lane: the close links the studio's sign-in; a second `action_confirm_joined` makes nothing; Hiring's own path for another offer untouched; the joined offer no longer comes across | pass |
| H6 | nothing received is asked; the bank goes as `pb_nh_hiring_bank`; the approver's rows say "From Hiring" | pass |
| H7 | offer dropped between send and approval → both Hiring legs amber ("…is no longer signed…"), the hire stands, the offer untouched | pass |
| H8 | `_hiring_on` patched off → no tile, empty list, bring-across refused, no step 5 marks | pass |
| H9 | Many at once → the Updates action + context; with nobody approving new people → Updates' own sentence | pass |

**Neighbour suites** (modules extended: `/pb_people_advanced, /pb_hiring, /pb_updates, /pb_onboarding`, 785 tests) on two
fresh copies of `nh3_base` — code at `99e18a973` (`git archive`) vs P4: **the same 10 not-ok in both, nothing new**, all in
pb_hiring (TestRecruitPrivacy ×3, TestRecruitPrivacyFiles, TestClientReview, TestRecruitInterviewsP5, TestRecruitJoining
test_11, TestRecruitStages test_13, TestRegistersP9, TestTheCover) — pre-existing on this local base.

### 2.2 No-trace proof (B.4 P1)
Test `test_p1_no_trace`: 20 calls with 20 different drafts (none cached), a manager who signs in, then counts compared:

| Table / thing | Before = after |
|---|---|
| `hr_employee`, `hr_contract`, `hr_payslip`, `hr_payslip_line`, `hr_payslip_worked_days`, `hr_contract_advantage` | equal |
| `mail_message`, `mail_followers`, `mail_mail` (the mail queue), `mail_activity`, `bus_bus` | equal |
| `ir_attachment`, `resource_calendar`, `resource_resource`, `res_partner`, `res_users` | equal |
| `pb_shift_pattern_member`, `pb_new_hire_ask`, `pb_journey_case`, `pb_newhire_proposal`, `biz_approval_request` | equal |
| scheme-map stale flags (`hr_employee.pb_paid_by_stale`) | equal |
| `hr_formula_rule` count + newest `write_date` of the scheme; `hr_formula_config.write_date` | equal |
| next payslip number (`ir.sequence` `salary.slip` `number_next_actual`) | equal |
| precommit / postcommit hooks left on the cursor | equal (none added) |
| `registry.cache_invalidated` (would tell every worker to drop caches, NH51) | empty |
| an employee with the draft's name | none |

Walk DB check (shell, 6 calls incl. three countries, the large scheme, no scheme, a mismatch): the same 13 counts equal.

### 2.3 Timings (B.4 P6)
`took_ms` is logged on every call (`new hire: payslip example in N ms (ok, cached, busy, scheme)`).

| Scheme (walk world) | Uncached, median of 10 | Cached, median of 10 |
|---|---|---|
| Indonesia large scheme, 300 rules | **1,472 ms** (quiet laptop); 1,998 ms with three test servers running | 45 ms |
| Indonesia monthly staff, 11 rules | 958 ms (quiet); 1,326 ms under load | 42 ms |

The large scheme sits right at the 1.5 s line on a quiet laptop and over it under load, so the cache was built. The cost is
the employee + contract create (profile: ~0.8 s in the 17 `hr.employee.create` overrides, ~0.4 s in the contract create
incl. the fill-in), not the evaluation (~0.05 s on 300 rules) — a faster example would need a lighter create, i.e. a
second create path, which the ledger forbids.

### 2.4 Browser walk (local server `nh6_base`, Claude-in-Chrome, 1440 px; console read)
| # | Walk | Result |
|---|---|---|
| G1 | step 1: three tiles; From Hiring "2 signed offers are waiting…"; list with initials, "job · team · signed <date>", start + wage, green chips (Identity card, Highest certificate, Last payslip, Bank account, Photo), grey "Tax card not sent yet"; second offer all grey; info row; with no offer waiting the tile reads "No signed offers are waiting" | pass |
| G2 | Bring across Made Prasetya: name, personal email, first day 14 Dec, team, job, manager, wage Rp 11,000,000 filled; toast; rail: role and pay "Suggested. Check it"; step 5: Bank "Received in Hiring · 25 Nov … read, then a second person approves" with Use the Hiring paper / Ask / I have it; KTP row "Ask for the number / I have the number" ("Made is asked for the NIK only"); certificate "Came across"; right panel bank line "from the Hiring paper, then a second approval"; payslip example | pass |
| G3 | send → "Made Prasetya is with Dewi Lestari for approval" (asked list shows "NIK (identity number)" only) → approved as Dewi Lestari (engine `decide`, the inbox's own call) → legs: `hiring` amber ("2 papers from Hiring, the photo from Hiring. The bank paper came across but could not be read… Identity card needs a valid-until date…"), `hiring_close` "Hiring shows Made Prasetya as joined"; records: certificate + last payslip filed (unverified), photo set, bank request BCR/2026/0038 draft (no reader configured locally — the honest amber path), originals still on the Hiring request; offer `joined`/`confirmed`, joined on 14 Dec, contract/case/package/login linked, applicant stage "Joined"; ONE contract, ONE checklist, ONE laptop request; New joiners board has Made's row; Hiring board shows the role "Filled" | pass (bank amber is the local no-reader case) |
| G4 | Hiring › Accountant › Ananya Rao: drawer shows "Confirm they joined" + "Confirm without the form"; the first opens the studio with Ananya brought across ("Back to Hiring" chip, payslip example S$ 5,240.00); back; "Confirm without the form" opens Hiring's own dialog → "Yes, they started" → Hiring's toast "Ananya Rao has joined. Made: their employee record, a contract from 4 Jan, a sign-in, the welcome checklist." | pass (offer list empty under the brought-across offer — fixed during the walk: the door now loads the list) |
| G5 | Indonesia (Rp, BPJS lines, PPh 21, employer cost), Singapore (S$, CPF), Vietnam (₫, insurance lines; tax 0 hidden), mismatch Finance + Indonesia (the Singapore scheme in rupiah + the mismatch note), "Unpaid team" → grey card "No pay scheme pays this team yet." + fix (no "Go to step" link while already on that step — fixed during the walk), BPJS Kesehatan switched off → its line gone, take-home up by exactly the 1 % | pass |
| G6 | wage typed fast twice (one keystroke burst; then "98", a pause, "00000"): one request per pause; the "98" answer was never shown; old take-home dimmed (`is-stale`) until the new one landed: shown values were only old → new | pass (two requests at once from one screen met each other's lock — fixed during the walk, NH55) |
| G7 | 340 px studio root with the narrow rules forced (NH45): tiles stack, offer row wraps (chips under the name), payslip box 274 px; `scrollWidth` 340 = `clientWidth` | pass |
| G8 | console (errors only) across the walk: none; server log: no ERROR from our code (the P3a-known biz_access logged-out trace of the copied DB only) | pass |
| H9 walk | Many at once → leave dialog for the unsent hire → Updates opens on "Lasting changes" with "Blank sheet for new employees" open | pass |

## 3. Self-review against the handover — deviations

1. **Two legs, not one** (A.3 says one leg `hiring` right after `papers`). Files and the bank paper are in `hiring` (right
   after `papers`, as specified). The CLOSE is a separate leg `hiring_close` after `equipment`: run where the handover put
   it, Hiring's `_ensure_login` / `_ensure_case` would run before the studio's own sign-in and checklist legs existed —
   making a work-email login and Hiring's checklist first. After them, Hiring links what the studio made and its buddy /
   laptop hand-over lands on the studio's checklist.
2. **An "amber but kept" leg answer** (`welcome_legs.run`): a failed leg rolls its savepoint back, which would also undo
   the papers already filed when only the bank paper was unreadable. A leg may now return `{amber, message, done}`: the
   work stays, the row is amber, the record gets one note.
3. **The identity card from Hiring is not filed** in "ID Document": that category requires a valid-until date Hiring never
   collects (NH56); the leg says so in amber and the file stays on the Hiring request. Asking the date in step 5 for a
   received card is open question 1.
4. **The bank request is created as the hire's sender with sudo** (NH57) — HR approvers cannot create bank requests; FS-16's
   precedent for who the creator is.
5. **Received rows in step 5** use the existing answers with reduced choices: the merged ID / tax card rows keep "Ask" (now
   "Ask for the number", the ask row's label is the number's) and "I have it" (now "I have the number"); a paper row has one
   answer "Came across" (+ "Not needed" when optional); the bank row gets a new answer `hiring` ("Use the Hiring paper",
   the default). The photo and "Other papers" (payslip, unmatched lines) have no step 5 row: they come across in the leg.
6. **Offer wage**: brought across only when the offer's money is the money of the team scheme's country; otherwise the
   wage box stays empty with "The offer's pay is in VND. Type the monthly wage in SGD." (no conversion is invented).
7. **"Confirm they joined" for non-HR users** (recruiters without the HR right cannot use the studio) keeps opening
   Hiring's own dialog; "Confirm without the form" is shown only to HR users, for whom the main button opens the studio.
8. **Many at once**: the Updates desk had no deep link to its new-employee sheet; a context key read by a `loadHome` patch
   opens it. "Switched off" = Updates' own refusal (`_joiner_refusal`: not HR, or nobody approves new people), shown in
   the studio toast as Updates words it.
9. **Evaluation errors**: the kernel reports almost none (NH52) — a broken formula shows as a 0 line, exactly as on the
   real payslip. The "could not work out an example" card is tested with a reported error.
10. **The manager is not part of the example** (NH51) — the cache key and the preview drop it.
11. **Payslip line builder**: mirrored from `_create_payslip_lines_from_formulas` (the named precedent returns column values,
    no lines) — same filter and fields; P2 proves equality with a real computed payslip to the cent.
12. Approvals in the walk were made with the engine's own `decide` as the HR lead (shell), the same call the inbox makes.
13. Part B got a follow-up in the Part A commit: the client sends ONE example at a time (NH55) and the log line names
    `cached` / `busy`.

## 4. Design bar (ledger rule 4), scored honestly
- **Hero moment — 8/10.** The wage lands in the dark box with the person's real scheme lines within ~1–1.5 s (45 ms when
  cached), flipping a usual answer moves take-home by the exact amount; old numbers dim rather than vanish. Short of 10:
  the first answer on a cold server is 2–2.5 s, and numbers swap rather than count.
- **Zero dead-ends — 9/10.** Every state named: waiting for inputs, shimmer, busy (silent retry), no scheme (with the step),
  formula error, seat limit (true sentence), mismatch note, no take-home line; From Hiring empty, offer gone after a
  reload, offer no longer signed at approval (amber), unreadable bank paper, ID card without a date.
- **Plain language — 8/10.** Screen words; component names are the scheme's own (as on the payslip).
- **Motion — 8/10.** Tiles lift, offer list opens, the brought-across row tints, payslip box fades in, take-home lands,
  panel glides the box into view on step 3; all off under reduced motion.
- **Keyboard — 7/10.** Tiles and rows are buttons in Tab order; Enter brings across; no arrow-key movement between offers.
- **Versus Rippling / BambooHR "hire from ATS"** — ahead on the honest payslip preview and on "what came across"; behind on
  bulk (Many at once is a hand-off to Updates).

## 5. New gotchas
NH50–NH60 in the ledger: savepoint runs/clears precommit hooks; side effects a rollback does not undo (group write →
every worker's caches); the kernel swallows formula errors; write_date does not move inside a transaction; the calendar
lock lasts the transaction; two examples from one screen; ID Document needs an expiry; HR cannot create bank requests;
Hiring's close makes its own login/checklist and swallows failures; one patch point for every Confirm they joined;
signed offers need wkhtmltopdf locally.

## 6. Open questions for the architect / owner
1. **Identity card from Hiring**: ask its valid-until date in step 5 (the row would show a date box under "Received in
   Hiring"), or keep the amber "file it by hand" — or file it in "Other papers"?
2. **Bank paper reading**: locally there is no reader, so every Hiring bank paper stays a draft request (amber). On the live
   sites, is a reader set up (`payroll.ai.config` purpose `doc_ocr`)? If not, the default should be "Ask <first name>".
3. **Buddy**: Hiring's `_hand_over_buddy` re-chooses Hiring's first named buddy after the studio's buddy leg; the bring-across
   puts that same buddy in step 6, but if HR changes it in step 6, Hiring's choice wins at the close. Keep, or skip
   Hiring's buddy hand-over when the studio set one?
4. **Many at once** lands on Updates' sheet; should the studio's tile also offer the blank sheet's download directly?
5. **Example speed**: the create path is 1–1.5 s per uncached example. Accept with the cache, or invest in a lighter
   "preview" create (a second path — ledger rule 5 says no)?

## 7. Commits (not pushed)
- `cc915ceb4` NEWHIRE P4 Part B: a month's payslip example in the right panel
- `8ececf8e9` NEWHIRE P4 Part A: From Hiring, Many at once, and Hiring's "Confirm they joined"
- this docs commit (report, ledger NH50–NH60, fact corrections)

Local leftovers (not in git): DB `nh6_base` (+ filestore) with the P4 walk (Made Prasetya through the studio and approval;
Ananya Rao through Hiring's own confirm; Lina Hartono's offer still signed and brought across in an unsent draft; approval
route ON); DBs `nh7_a`/`nh7_b` (before/after neighbour runs); scratch `walk_seed_p4.py`, `seed_hiring_p4.py`,
`seed_hiring_p4b.py`, `walk_p4_roles.py`, `probe_p4.py`, `time_p4.py`, `time_p4b.py`, `prof_p4.py`, `runq.sh`, `cmp2.sh`,
`restart6.sh`, `approve4.py`, `check4.py`, `base4/` (code at `99e18a973`).
