# NEWHIRE P3a — Details and documents: what is needed, who gives it

Read first: `NEWHIRE_LEDGER.md` (binding, NH1–NH31), `NEWHIRE_P2_REPORT.md` (the welcome-leg structure you extend),
`NEWHIRE_FACTS_ONBOARD.md` §A (My Payobook pages), §C (documents), §D (bank), §E (numbers per country). **Do not
re-derive.** Then open the POC and click step 5.

Work ONLY in `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). No deploy, no server access.

P3 is split: **P3a (this)** = the list of what is needed, HR's "I have it" entry, and the record of what the new person
will be asked. **P3b (next)** = the welcome email/link, the `/my/welcome` page, reminders and the New joiners tracker.
P3a must leave clean seams for P3b (the ask rows) but sends nothing to anyone.

**Hero moment**: flipping one row between "Ask <first name>" and "I have it" — the row opens its own little form or
file drop, the right panel's "Who does what" bar slides, and Payroll-ready tells the truth about the bank account.

## 1. Scope
1. **Papers needed per country of work** — a small table, seeded for Indonesia / Vietnam / India / Singapore, editable by
   an HR manager from inside step 5.
2. **Step 5 Details and documents** replaces the last `StepSoon`.
3. **"I have it"**: HR types the details/numbers/bank or attaches the paper; applied on approval.
4. **"Ask <first name>"**: recorded as ask rows on approval (P3b sends and tracks them).
5. Right panel: the "Who does what" bar and true Payroll-ready lines. Step 2 gains the "Papers needed" tile.
6. Carried over from P2's open questions (architect decisions):
   - **Contract letter leg**: the person applying may lack the payroll-manager right the letter needs. The approver has
     just approved this very wage, so the leg generates the letter with sudo for studio hires. Remove the fast-lane
     pre-switch-off P2 added; keep the amber row for real failures (no PDF tool, missing wording).
   - Everything else in P2 §open questions stays as built (logged for the closeout).

### Binding non-goals
- No email, link, `/my` page, reminder or board change (P3b). No "From Hiring" (P4). No `.po`, no Learn (P5).
- No new no-login page and no relaxation of the `user_id == env.user` guards on the self-service entry points (D8).
- Do not change `pb_employee_vault`, `pb_me_details`, `pb_me_tax`, `pb_bank_ocr` code. New models live in `pb_new_hire`
  (D10: a new table in a module installed on all five databases would break the databases that are not upgraded).

## 2. Plumbing decisions (made — follow them)

### 2.1 Dependencies
Add `pb_employee_vault`, `pb_me_portal`, `pb_me_details`, `pb_me_tax`, `pb_bank_ocr`, `pb_employee_bank_panel`
(all on all five databases, FACTS_ONBOARD §M3). Version 19.0.1.2.0.

### 2.2 `pb.new.hire.paper` — papers needed per country (new model, `models/paper.py`)
Fields: `category_id` (M2O `pb.employee.document.category`, required, cascade), `country_code` (Selection = the
studio's country list, required), `need` (Selection `first_pay` "Needed before first pay" / `joining` "Asked at joining"
/ `optional` "Optional"), `label` (Char, translate — what THIS country calls it, e.g. "KTP (identity card)"; empty →
category name), `sequence`, `company_id` (empty = shipped default; a company row for the same category+country overrides
it), `active`. SQL-unique (category, country, company). Access: read HR user; write HR manager + system. No reverse
O2M on the category.
Seeds (`data/papers.xml`, `noupdate="1"`), using existing categories only (FACTS_ONBOARD §C3):
ID: `cat_id_document` first_pay "KTP (identity card)"; `pb_me_tax.cat_tax_paper` joining "NPWP card"; `cat_other`
optional "Family card (Kartu Keluarga)"; `cat_certificate` optional "Highest certificate".
VN: `cat_id_document` first_pay "Citizen ID card"; `cat_health_check` joining "Health check"; `cat_certificate` optional.
IN: `cat_id_document` first_pay "Aadhaar card"; `cat_tax_paper` first_pay "PAN card"; `cat_certificate` optional.
SG: `cat_id_document` first_pay "NRIC or work pass"; `cat_certificate` optional.
MY: `cat_id_document` first_pay "MyKad or passport"; `cat_certificate` optional.
Reader `pb.new.hire.paper.for_country(country_code, company) -> ordered rows` (company row beats default; inactive
company row = "not needed here").
Editor (screen twin, HR manager only): facade `papers_edit_load(country_code)` / `papers_edit_save(country_code, rows)`
writing COMPANY rows only (never the shipped defaults; "Back to the usual list" deletes the company rows). In step 5 a
quiet "Change what is asked in <country>" opens a drawer (copy `SetupDrawer`, WS14): each category as a row with the
three-way need + "Not needed", editable label, add from the remaining categories. Others see no link.

### 2.3 The item list — `details_options(draft) -> {items:[…], papers_editable: bool}`
One server-built list drives the step (no country knowledge in JS). Item shape: `{key, group:'details'|'papers', icon,
label, sub, need:'first_pay'|'joining'|'optional', can_ask:bool, ask_why_not, can_have:bool, can_skip:bool,
fields:[{name, label, kind, options, required, hint}]|[], upload:{category_id, needs_expiry:bool}|false, ask_url}`.
Items, in order:
1. `personal` — "Personal details" (date of birth, gender, home address, city, personal phone). optional. Ask → `/my/profile`
   for the contact part. Fields → `birthday`, `sex`, `private_street`, `private_city`, `private_phone` (only fields that
   exist; step 1's phone is shown here prefilled, one source of truth in the draft).
2. `emergency` — "Emergency contact". optional. Ask → `/my/profile`. Fields → `emergency_contact`, `emergency_phone`.
3. `id_number` — label by country ("NIK (identity number)", "Citizen ID number", "Aadhaar number", "NRIC or FIN",
   "Identity number"). first_pay. Ask → `/my/details/papers?kind=national_id` (asks number + scan together). Field →
   the store payroll reads per FACTS_ONBOARD §E: `identification_id` everywhere, PLUS `vietnam_citizen_id` (VN) and
   `singapore_nric_fin` (SG) — write both stores where two exist (open question 8) and say so in the report.
4. One item per kind in `pb_me_tax`'s `KINDS_BY_COUNTRY[country]` (import the table; labels from pb_me_tax's own kind
   labels): e.g. `tax_number` ("NPWP (tax number)" / "Tax code" / "PAN"), `tax_status` (ID), `tax_regime` (IN),
   `tax_fund` (SG). Need: `tax_number` first_pay, others joining. Ask → `/my/tax/change/<kind>`. Fields → `NUMBER_FIELD`
   / `CHOICE_FIELD` targets with pb_me_tax's own validators (call them; do not copy the regexes). VN: also the running
   contract's `vietnam_tax_code` (the approval flow does that — mirror it).
5. `insurance` — only where the country has HR-kept numbers (§E "Kept by HR": ID BPJS Ketenagakerjaan + Kesehatan, VN
   social insurance number, IN UAN + ESI). `can_ask False`, `ask_why_not` "These numbers are kept by HR. Add them now or
   later on the record." optional. Fields → the §E fields.
6. `bank` — "Bank account". first_pay. Ask → `/my/details/bank`. Fields → `bank_name` (choices from the wizard's
   `_pb_bank_choices`, filtered/ordered by country when the registry has one), `account_number`, `account_holder`
   (default = the person's name) — these are the OLD wizard keys: put them in the values exactly as the old window did so
   `_pb_send_bank` → `_pb_hold_new_hire` runs unchanged (second person approves; P1 `send` must stop forcing
   `has_bank False` and run `_pb_bank_problem` as the old maker branch did).
7. Papers: one item per `for_country` row. `upload` set. `can_ask` = the category is `ess_uploadable`, OR it is
   `cat_id_document` (served by item 3's page — then the paper item is merged INTO `id_number`: one row "KTP (identity
   card) and number", ask = both, "I have it" = number field + file drop), OR it is `cat_tax_paper` (merged into
   `tax_number` the same way). Not self-uploadable → `ask_why_not` "Only HR can add this paper." `can_skip` = need is
   not first_pay.
Default choice per item: `ask` when `can_ask`, else `later` (a fourth quiet state "Later, on the record" for
can't-ask items HR leaves empty). `can_skip` items may be "Not needed".

### 2.4 Draft, send and storage of files
- Draft keys: `items` ({key: 'ask'|'have'|'skip'|'later'}), `have` ({field_name: value} — flat, whitelisted against the
  current `details_options` on the server at send time), files kept in component memory only (never sessionStorage).
- `send` validation: for every `have` item, its required fields/file must be present (jump-to-field errors, step `docs`).
  A first_pay item may be `ask` or `have`, never `skip`.
- Files: `send(draft, files=[{key, name, mime, data(base64), issue_date, expiry_date}])`. Same limits as the vault
  (png/jpeg/pdf, 10 MB each, 50 MB total, expiry required when the category requires it — check BEFORE proposing, with
  the vault's own sentences). After `propose`, create one `ir.attachment` per file with `res_model='pb.newhire.proposal'`,
  `res_id=<proposal>` (sudo) and store `{key: attachment_id}` on the proposal — add a Json field `pb_nh_files` on
  `pb.newhire.proposal` (lives in `pb_new_hire`; not inside `payload_json`, which is readonly after create — confirm).
  Fast lane (applied inside `propose`): the leg needs the files before the proposal id exists → pass the decoded files
  through a context key for that call only; never through the payload.
- Withdraw / reject / return: delete the held attachments (extend the P1 `_approval_withdraw` hook and the proposal's
  reject/return hooks). After "Withdraw and change" the client still holds the files in memory unless the page was
  reloaded; if reloaded, the affected rows show "Add the file again" (amber) — designed state.
- Bank numbers in the payload: parity with the old window (already stored there today, masked in the drawer). Unchanged.

### 2.5 New welcome legs (after P2's `own_fields`, before `login`)
- `details`: one `write` of the whitelisted `have` values on the employee (sudo, `tracking_disable`), validators re-run;
  VN contract tax code mirrored.
- `bank`: nothing new — the P1/old path sends it; report its outcome as a leg row (`sent`/`check`/`not_sent`).
- `papers`: per held file → `pb.employee.document` in its category with the attachment re-bound to the document
  (create as `pb.people.vault_upload` does: call it when the applying user is HR — they are, the gate is `require_hr` —
  with the attachment's content; then drop the held attachment). `verified` stays False (HR verifies on the record).
- `asks`: create the ask rows (2.6) for every `ask` item.

### 2.6 `pb.new.hire.ask` — what the new person was asked (new model, `models/ask.py`)
Fields: `employee_id` (required, cascade, index), `key`, `label`, `need`, `url`, `sequence`, `state` (Selection `open`
"Waiting for <them>" / `waiting` "Sent, waiting for HR" / `done`), `done_on`, `category_id`, `company_id`,
`proposal_id`. Access: HR read/write; the employee's own user read (record rule `employee_id.user_id = user`).
`refresh()` (recordset method, cheap, idempotent) recomputes `state` from the product's own data — never from a click:
- `personal`: done when `private_phone`, `private_street` are set (+ birthday when the field is employee-editable; else
  ignore); waiting when an open `pb.profile.change.request` (hr_review) exists.
- `emergency`: both emergency fields set / open profile request.
- `id_number` (+paper): `identification_id` set (and, when a paper is merged, a document in `cat_id_document`) / open
  `pb.me.detail.request` kind `id_paper`.
- tax kinds: the target field set / open detail request of that kind.
- `bank`: `pb_bank_on_record` / an open `pb.bank.change.request` (hr_review or finance_review).
- paper items: a `pb.employee.document` in the category / (no waiting state — uploads land directly, unverified).
`pb.new.hire.ask.summary(employee) -> {total, done, waiting, open, items:[{key,label,state,need,url}]}` — the ONE reader
P3b's page, home row, board chip and reminders will use.

### 2.7 Client
- `step_docs.js` per POC `vDocs`: two cards (Details · Papers for <country>), each row = icon tile, label, sub, need
  chip, segmented control built from `can_ask/can_have/can_skip` (disabled options stay visible with the reason as a
  tooltip AND as the sub-line when chosen is impossible). "I have it" expands the row (height animation) to its fields or
  the file drop (drag-and-drop + click; shows name, size, a remove ×; expiry/issue date boxes when needed; wrong type /
  too big → inline sentence from the vault's rule). Presets on top: "Ask <first name> for everything" / "I have
  everything here" (only touches rows where that choice is possible).
- The invite card of the POC becomes a **quiet summary card** in P3a: "<first name> will be asked for N things after the
  hire is approved. The welcome message is switched on in the next release." (true; P3b replaces the card with the
  phone preview and the reminders switch). No phone mock yet.
- Rail: `docs` done text "N for <first name>, M with you"; amber when a "have" row is incomplete.
- Right panel: "Who does what" split bar (You = have + step-6 own fields; <first name> = asks; Manager and IT = buddy +
  equipment + IT steps from the P2 timeline) with the POC's legend; Payroll-ready bank line: have → "Bank account:
  waiting for a second approval after sending"; ask → "Bank account: <first name> will be asked"; later → "Bank
  account: not asked yet" (amber).
- Step 2 tile "Papers needed": "N required, M optional" from `for_country`.
- Step 7 row for step 5; a first_pay item left "later" (only possible for insurance → never) — n/a; list the asks count.
- Approver drawer rows: one per "have" value (bank masked as today, numbers shown in full to the approver? NO — mask ID
  and tax numbers to the last 4 like the bank row), "Papers attached: <labels>", "Will be asked: <labels>".
- Done card legs: details / papers / asks rows join the collapsed green line.

## 3. Safety rails
- Server whitelists every `have` field against `details_options` for the SENT country; unknown keys are dropped and
  logged at debug, never written.
- File content never enters `payload_json`, `result_json`, chatter or logs. Held attachments are sudo-created with no
  public access and die with the proposal's withdraw/reject/return.
- ID, tax and bank numbers are masked (last 4) everywhere they are displayed back after typing loses focus? No — keep
  them readable while HR types in the studio; mask in the approver drawer, the done card and the chatter.
- Ask rows are created only on apply. `refresh()` only reads.

## 4. Tests (tag `newhire`) — D1…
D1 seeds: `for_country` per country; company override; "not needed here"; back to usual.
D2 editor gates: HR manager writes company rows only; HR user refused; defaults never modified.
D3 `details_options` per country: item keys/labels, merged id/tax paper rows, insurance not askable, non-self-upload
   paper not askable with the reason.
D4 `send` validation: have without required field/file; first_pay skip refused; expiry required; size/type limits.
D5 leg details: values on the employee incl. both stores for VN/SG id; validators reject a bad NPWP/PAN with pb_me_tax's
   sentence at SEND time (not at apply).
D6 bank through the studio = the old outcome (request waiting for a second person, employee not payroll-ready until
   approved); bad number refused at send with the old sentence. `test_fs16_newhire_bank` still passes.
D7 papers: pending → attachments on the proposal, none on any employee; approve (second user) → documents in the right
   categories, held attachments gone; reject and withdraw → attachments deleted; fast lane path.
D8 asks: rows per ask item with urls; `refresh()` state transitions for each key (open → waiting → done) driven by the
   real models; `summary` counts.
D9 letter leg with a non-payroll-manager approver succeeds (sudo decision); P2's W10 still passes.
D10 approver drawer masks numbers; payload has no file data. D11 P1+P2 suites still green; static gates.
Browser walk: E1 Indonesia default list (ask everything) → rail/right bar; E2 flip bank + id to "I have it", type, attach a
PDF, remove, re-attach; E3 presets; E4 wrong file type and >10 MB; E5 editor drawer: make NPWP card "Needed before first
pay", add a category, back to usual; non-manager sees no link; E6 send → approve as second user → record shows details,
documents, bank request waiting; asks rows exist (check in the DB); E7 withdraw and change keeps typed values, files
still attached without reload, "Add the file again" after reload; E8 Singapore (few items) and Vietnam lists; E9 340 px;
E10 keyboard through a row (segmented control arrows, Enter opens the form); E11 console clean.

## 5. Report back — `NEWHIRE_P3A_REPORT.md`
Same sections as P2. Add: the exact field written for every item per country (a table), and the seams P3b should call.
Commit feature-scoped with explicit paths, report + ledger (NH32+) as the final docs commit. Do not push.
