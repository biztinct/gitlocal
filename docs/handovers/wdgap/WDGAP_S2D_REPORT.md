# WDGAP S2-D report — Tax details on My Payobook

Branch `wdgap-s2d` from `origin/19.1` @ 116386329. Local database `wdgap_s2d_t` (copy of
`upd_p6_t_tpl`, 44 behind modules upgraded on the origin tree, `pb_me_details` installed),
port 8781. Nothing deployed; the live server was not touched. Owner ruling G4.

## 1. What was built

### New module `pb_me_tax` 19.0.1.0.0
Depends `pb_me_details`, `pb_employee_vault`, `pb_hr_payroll_formula` (handover item 1).

| Item | Built | Where |
|---|---|---|
| Page `/my/tax` + tile under "Me" | `TILES.setdefault('/my/tax', group 'me', icon 'shield', tone 'green', seq 111)` — after My details (109) and Certificates (110), ledger S6M-4. Home tile entry (QWeb inherit of `portal.portal_my_home`). Pages: overview, change form per kind, one change (status + Now/Proposed, take back). | `pb_me_tax/models/pb_me_home.py:20-31`; `controllers/portal.py:31-152`; `views/portal_templates.xml` |
| "Needs you" | `tax_sent_back` row (HR sent a tax change back → `/my/tax`) | `models/pb_me_home.py:37-50` |
| "My requests" | My details' own source already lists the request model; tax rows are relabelled "Tax details", icon shield, link `/my/tax/request/<id>` (`_my_requests_rows` override, calls super) | `models/pb_me_home.py:52-66` |
| Country follows the scheme | `hr.employee._pbtx_country()`: `schemes_for_employee` (scheme map / "Paid by") first, then the scheme of the newest non-cancelled payslip; '' → plain message "Your tax details cannot be shown yet"; a country outside VN/ID/IN/SG → "Tax details for <country> are not on My Payobook yet" | `models/hr_employee.py:117-136` |
| Fields (existing first) | VN tax code = `vietnam_tax_code` (existing); ID NPWP = `pb_npwp_number` (existing), "Use my NIK as my NPWP" box fills it from `identification_id`; BPJS numbers view only (existing). NEW on `hr.employee`, all `groups='hr.group_hr_user'`: `pb_id_ptkp_status` (TK/0…TK/3, K/0…K/3, K/I/0…K/I/3), `pb_in_pan_number`, `pb_in_tax_regime` (new/old), `pb_in_uan_number` (view only for the employee), `pb_sg_tax_residency` (view only), `pb_sg_shg_fund` (CDAC/ECF/MBMF/SINDA/none). SG NRIC/FIN = `identification_id`, shown masked. | `models/hr_employee.py:39-69`; table `models/tax_rules.py` |
| VN dependants | Overview card lists the registered tax dependants (`vn_dependent_ids`) with their state (Counted for tax / Being checked / Not counted / No longer counted) and family members waiting for the pay team's tick; button to My details (the family flow is not duplicated) | `models/hr_employee.py:217-250` |
| Masking | last 4 characters everywhere on /my pages and in My requests titles; the full number only in the box where the person types their own new number, and for HR in the Approvals inbox rows (to compare with the proof) | `tax_rules.mask`; `tax_request._pb_rows(full=False)` |
| Requests | NO new request model: 4 kinds added to `pb.me.detail.request.kind` with `selection_add` (`tax_number`, `tax_status`, `tax_regime`, `tax_fund`) + fields `t_country` (fixed at send), `t_number`, `t_use_nik`, `t_ptkp`, `t_regime`, `t_fund`. Same process `me_details`, same route (HR lead), one open request per kind (pb_me_details' own check), sent back / turned down / take back as for details | `models/tax_request.py` |
| Kinds per country | VN: tax number. ID: NPWP, PTKP. IN: PAN, tax regime. SG: self-help group fund. A kind the country does not offer is refused server-side and the form route redirects | `tax_rules.KINDS_BY_COUNTRY` |
| Proof | required for tax number, PTKP and regime; optional for the SG fund. PDF/JPG/PNG ≤ 10 MB (pb_me_details' `_pb_file`). Made inside pb_me_details' ONE savepoint. On approval the SAME attachment moves to the person's documents (new category "Tax paper", no expiry, `noupdate`), verified by the approver — stored once | `tax_request._pbtx_file_proof` (`:196-221`); `data/document_category.xml` |
| Apply | writes exactly the proposed value into the one field for `t_country`, under sudo (approver needs no payroll right — W2B-2/S6A-1); refuse / send back / take back write nothing | `tax_request._pb_apply` (`:180-194`) |
| Inbox | before/after row; chips Country, File, Proof missing (when it is), "Pay: Changes only if a pay rule reads it"; VN "Tax dependants: Do not match the contract" when the check fires (also on VN family requests). Revision fingerprint gets a `tax` key ONLY for tax kinds (other requests' fingerprints unchanged, W2A-2) | `tax_request._approval_detail`, `_chain_revision_values` |
| What it does NOT do (HR) | Employee form → new page "Tax details": the sentence "Approving a tax detail … writes it to this record only. A payslip changes only where a pay scheme is set up to read that detail; none reads it when this is first switched on." + the new fields (HR edits them as with NPWP today) + the person's tax changes with the proof file downloadable (request form inherits pb_me_details' form). | `views/hr_views.xml` |
| Application sources | Registered in the engine's typed-source seam (pb_time_pay precedent): `tax.id_ptkp_status`, `tax.in_pan_number`, `tax.in_tax_regime`, `tax.sg_shg_fund` (stored codes, not labels), `tax.vn_confirmed_dependants` (= `vn_eligible_dependent_count`). Answer only for a component mapped to them; read with the payroll actor's own rights (no sudo fallback). NOTHING is mapped. VN tax code / NPWP were already sources (`employee.vietnam_tax_code`, `employee.pb_npwp_number`). | `models/formula_sources.py` |
| VN "does not match" | `hr.employee.pb_vn_dependants_check` (HR-only, computed, read-only): dependants HR confirmed for tax vs the running contract's registered-dependants component (codes from system parameter `pb_me_tax.vn_registered_dependants_codes`, default `VNREGISTER`). Never writes the contract. Shown on the employee form page, in Full details, and as an inbox chip. | `models/hr_employee.py:71-115` |

### Files edited outside the new module (lanes allowed by the handover)
- `pb_me_details` (extension points only) 19.0.1.0.0 → 19.0.1.0.1:
  `detail_request.py:241` — the kind check reads the field's selection (so `selection_add`
  kinds are offered); `detail_request.py:498` — new `_pb_page_domain()` (default `[]`) used by
  `pb_me_home.py:41` (its "sent back" count) and `controllers/portal.py:105` (its "Your changes"
  list), so tax changes live on `/my/tax` only. Behaviour with no override: identical.
- `pb_employee_vault` (Full details groups only) 19.0.1.6.0 → 19.0.1.6.1:
  `employee_details.py` `_SPEC` — PTKP row in the Indonesia group; new groups "India tax" (PAN,
  regime, UAN) and "Singapore tax" (residency, self-help fund); "Vietnam tax dependants" (the
  check, optional — dropped while empty). Rows are skipped where pb_me_tax is not installed.
  vi/id entries appended text-level. pb_me_tax also widens `_e360_gate` by inheritance: a
  country's group shows for a person paid by a scheme of that country.
- `pb_me_portal`: NOT edited (see merge-time task M1).

## 2. Sources (published rules) and INFERRED

| Rule | Source | Status |
|---|---|---|
| VN personal tax code 10 digits; 12-digit chip-ID number used as tax code from 1 Jul 2025 | Circular 105/2020/TT-BTC; Circular 86/2024/TT-BTC art. 35 | from published rules (no web lookup made) |
| ID NPWP 15 digits / NIK (16) as NPWP | PMK 112/PMK.03/2022 | same |
| ID PTKP TK/K/K-I × 0–3 dependants | UU PPh art. 7; PMK 101/PMK.010/2016; PER-16/PJ/2016 | same |
| IN PAN AAAAA9999A | Income-tax Rules, rule 114 | same |
| IN regime new (default) / old | Income-tax Act s.115BAC; CBDT Circular 04/2023 | same |
| SG self-help funds CDAC/ECF/MBMF/SINDA, opt-out allowed | CPF Board "Self-Help Groups" | same |
| **INFERRED**: the VN registered-dependants component is found by CODE `VNREGISTER` (Rize's code) — another customer's code must be added to the system parameter | repo (`tools/prepare_rize_vietnam_master.py`) | INFERRED |
| **INFERRED**: "approved dependant count" = `vn_eligible_dependent_count` (current, status eligible) | FACTS S2F-5 | INFERRED |

## 3. Tests (all on `wdgap_s2d_t`, employee calls as a real portal login)

| # | Test | Result |
|---|---|---|
| 1 | own employee only: other's employee refused; other's draft not re-sendable; form cannot set employee/state/country; portal has no model right; HTTP: crafted ids redirect, POSTed `employee_id` ignored, other's change not withdrawable (T1, H2) | PASS |
| 2 | each kind propose → nothing changes → approve → written: VN code, ID NPWP + PTKP + NIK-as-NPWP, IN PAN + regime, SG fund; refuse → nothing; send back → resend same request; withdraw → nothing; one open per kind; bad numbers in plain words (T2a–g) | PASS |
| 3 | proof required (VN/ID/IN) and optional (SG); failure after the file → no request, no file (one savepoint); wrong file type refused; approved proof = same attachment, moved, verified, one row per checksum; resend with a new file removes the old (T3, T3b) | PASS |
| 4 | masking on the page data, page HTML, titles, My requests; inbox rows full for HR (T4, H1) | PASS |
| 5 | rows follow the scheme country VN/ID/IN/SG; MY → not offered; no scheme → plain message and create refused (T5, H1) | PASS |
| 6 | approver with HR only, no payroll group: approved, written, proof verified by them (T6) | PASS |
| 7 | VN note: 2 confirmed vs contract 1 → note in Full details + inbox chip; contract component unchanged after approval; equal → no note/group; employee page never shows it; IN/SG Full details groups (T7, T7b) | PASS |
| 8 | sources in the catalogue, not writable; no rule mapped (`tax.%` = 0); unmapped scheme asks nothing; a mapped rule reads "missing" before and while waiting, "K/1" after approval (T8). Payslip + application-data inputs byte-identical with/without the hooks (T8b, T8c). **Before/after-INSTALL golden** (script): 3 seeded payslips (VN, ID, VN application-data) recomputed after `-i pb_me_tax`: inputs, sources, computed values, lines, application inputs **IDENTICAL**. The application "settings stamp" was excluded: it hashes rule write dates and moved the same way in a control run with the same code and no install. | PASS |
| 9 | silent install: no job, mail template, menu, process, route, rule, scheme; no request; no employee field set; no "Needs you" row (T9) | PASS |
| 10 | privacy: another employee, a line manager, a payroll officer without HR cannot read the request or the proof (ORM and `/web/content`), before or after approval; internal users see 0 requests; HR reads both; the new fields HR-only (T10, H5) | PASS |
| 11 | PO gate vi/id (parse, 3 loader rules, no empty, header "Payobook 19.0", no duplicate, no vendor word), no vendor word in views/data/manifest/`_()` literals, translations load (T11a–c) | PASS |
| 12 | browser walk (below) | PASS |
| 13 | My details seams: its sent-back row ignores tax changes, the tax row counts them; family/marital flow unchanged; non-tax fingerprint has no `tax` key; My details doors send tax changes to /my/tax (T13, H3); tile under Me (H4) | PASS |

**Suites vs baseline** (baseline run on an `origin/19.1` archive tree, same database copy, before any edit):

| Suite | Baseline | Branch (final run `t3`) |
|---|---|---|
| pb_me_details | 26 tests, 0 failing | 26, 0 failing |
| pb_employee_vault | 21, 0 | 21, 0 |
| pb_me_portal | 93: test_05_grid (E), test_06_font, test_01_registry_covers_every_tile (5 other modules' tiles not installed here), test_12_vi_po…, test_01_profile_change_flow_and_audit (E), test_t1_7… | the same six **+ `TestMeHome.test_02_tile_meta_default_and_hidden`** — expected: it pins the "Me" list; `/my/tax` is the new last entry → merge-time task M1 |
| pb_me_tax | — | 29, 0 failing |

Final run `t3` (fresh copy, after the last edit): 169 tests, 5 failed + 2 errors = the six
baseline failures + test_02 (M1); all 29 pb_me_tax tests pass. Baseline run: 140 tests, 4 failed
+ 2 errors.

**Browser walk** (Chrome, isolated contexts `s2d.localhost:8781` / `s2dhr.localhost:8781`, DEMO
logins): `/my/tax` Indonesia desktop; PTKP sent without proof → plain error, value kept; sent with
proof → toast, row "Change waiting for HR", "Your changes" pill; phone 390 px (no sideways
scroll); HR Approvals inbox card + drawer (Now/Proposed, Country, File, Pay chips, employee's
note) → Approve → PTKP K/1 on the record, proof filed as a verified document; employee form
"Tax details" page (sentence, fields, changes list); Vietnam page in vi at phone width (tax code
row, two dependants with green/amber states, button to My details); id page; no-scheme message;
NPWP form with "Use my NIK as my NPWP". Fixed from the walk: page titles said "(ESS)" (now "Tax
details", "Change a tax detail", "Your tax detail change"); a double gap in "Paid in  Indonesia";
the empty card touched the next card. Console: only the template's missing logo/favicon (500,
filestore not copied — S6A-7) and enterprise app icons (404), both pre-existing.

Static: pyflakes clean (only `__init__` re-exports), XML parse, no vendor word.

## 4. Rails
- No route takes an employee id; ids of requests are used only when the employee is the session's own.
- Nothing on the employee record before approval; apply writes exactly the proposed value; HR-only fields.
- No payslip or scheme change; no source mapped; golden before/after install identical.
- Contract VNREGISTER never written (tested).
- `pb_me_portal`, `pb_lifecycle`, `pb_pack_*`, other lanes: untouched.
- No credentials in files: tests use a made-up test-only password; the walk password lived in the scratch folder only.

## 5. Contracts other phases may rely on
- `hr.employee._pbtx_country()` → 'VN'/'ID'/'IN'/'SG'/other code/''.
- `hr.employee._pbtx_portal_data()` (dict for /my/tax), `pb_vn_dependants_check`.
- Fields: `pb_id_ptkp_status`, `pb_in_pan_number`, `pb_in_tax_regime`, `pb_in_uan_number`, `pb_sg_tax_residency`, `pb_sg_shg_fund`.
- Request kinds `tax_number`/`tax_status`/`tax_regime`/`tax_fund`; `t_country` + `t_*` fields.
- Sources `tax.id_ptkp_status`, `tax.in_pan_number`, `tax.in_tax_regime`, `tax.sg_shg_fund`, `tax.vn_confirmed_dependants`.
- pb_me_details: `_pb_page_domain()` extension point. Vault category xmlid `pb_me_tax.cat_tax_paper`.
- S2-B (year-end certificate download on My Payobook) can sit on `/my/tax` beside these rows.

## 6. Merge-time tasks
- **M1 (pinned tile test, `pb_me_portal`)** — `pb_me_portal/tests/test_me_home.py`, in
  `test_02_tile_meta_default_and_hidden`, change
  `added = [u for u in ('/my/details', '/my/certificates')`
  to
  `added = [u for u in ('/my/details', '/my/certificates', '/my/tax')`
  (and the comment: "… My details and Certificates (WDGAP S6, owner ruling ME1), Tax details
  (WDGAP S2-D)"). No version change needed (test only). With that edit the suite equals its
  baseline.
- M2 (optional, `pb_approval_config`): the Approvals drawer cannot open an attached file (chips are
  text). Pre-existing for ID papers too. HR opens the proof from the employee form → Tax details →
  the change. A `files` entry in the `_approval_detail` contract would let the drawer link it.

## 7. Deploy notes
- `-u pb_me_details,pb_employee_vault` then `-i pb_me_tax` on every database (`pb_me_details`,
  `pb_employee_vault`, `pb_hr_payroll_formula` must be installed — they are wherever Step 6 went
  live). Asset purge (new frontend SCSS).
- Silent-install proof to check per database: `select count(*) from pb_me_detail_request where kind like 'tax_%'` = 0;
  `select count(*) from hr_formula_rule where application_source_key like 'tax.%'` = 0; no new
  `ir_cron`; employee columns `pb_id_ptkp_status`… all NULL; the "Tax paper" document category exists.
- Normal tier (new columns on `hr.employee`, access unchanged, no pay calculation change). Rize
  rehearsal: recompute one run that computes (W2M-4) — expect 0 differences; open `/my/tax` as a
  rize employee on each of the four schemes.
- The VN dependants check reads codes from system parameter
  `pb_me_tax.vn_registered_dependants_codes` (default `VNREGISTER`); for Sudima set its code if it
  is different (owner/HR question below).

## 8. Gotchas → ledger rows (S2-A owns the ledger edit)
| # | Gotcha |
|---|---|
| S2D-1 | `pb.me.detail.request.pb_portal_create` checked kinds against the module-level `KINDS` list, so a `selection_add` kind was refused ("not offered here"). Fixed with an extension point (the field's selection). Check module-level constants before extending a selection. |
| S2D-2 | The engine's application "settings stamp" hashes each rule's `write_date`; recomputing a payslip in a later transaction moves it even with identical code. A before/after golden must exclude it and prove the churn with a control run (same code, no install). |
| S2D-3 | Calling `_pbme_needs_extra` directly in a test as superuser fails inside other modules' hooks (`pb_me_project_time`: "That is not your employee record"): call it `with_user(<the employee's login>).sudo()`. |
| S2D-4 | Website page `<title>` = the QWeb template's `name`: a template named "… (ESS)" shows "(ESS)" in the browser tab (all existing My Payobook pages do). Name portal templates in screen words. |
| S2D-5 | A worktree agent's chrome-devtools `upload_file` refuses files outside the workspace roots (the scratch folder): post the form with `FormData` + `Blob` from the page instead. |
| S2D-6 | A flex heading (`.pbmd-h2`, gap 8px) with `<span>A</span> <t t-esc/>` shows a double gap; wrap the words in one span. |
| S2D-7 | `hr.formula.config` reads need a formula group: a payroll officer without it gets AccessError in `_application_domain_values` — test sources as "pay team + formula user". |

## 9. Owner questions (plain)
1. When someone has no tax number on file, should My Payobook remind them on their home page
   ("Add your tax number")? Today it stays quiet, so nobody is nagged the day this goes live.
2. Should a person also be able to propose their India UAN and Singapore tax residency, or do
   those stay "kept by HR" as now?
3. In Vietnam, HR is told when the dependants HR confirmed differ from the number on the contract.
   Sudima's contracts may name that number differently from Rize — should we check Sudima's name
   before go-live?
4. When HR approves a new Vietnam tax code, only the employee record changes; the old copy on
   the contract stays. Should the contract copy be updated too?

## 10. Left for later
- Year-end certificate download (S2-B). Malaysia (not in G1).
- Approvals drawer link to the proof file (M2).

## Follow-up TD1–TD3 (owner rulings 2026-11-18 ~15:20)

The four §9 questions were answered (rulings TD1–TD3 + the Sudima lookup note). pb_me_tax stays
19.0.1.0.0 (not yet released anywhere); no other module changed in this follow-up.

| Ruling | Built | Where |
|---|---|---|
| **TD1** reminder | "Needs you" row `tax_number_missing` — "Add your tax number" / "Your company needs it for your pay", opens Tax details. Shown only when the country of the pay set-up keeps a tax number here (VN, ID, IN — not SG or any other country), the number is empty, and no tax-number change is waiting for HR or sent back (the sent-back row covers that). Through the `_pbme_needs_extra` hook; pb_me_portal not edited; nothing emailed. Silent-install note: this row is now deliberately visible on day one to people with no number on file (owner choice). | `pb_me_tax/models/pb_me_home.py` (`_pbtx_number_missing`) |
| **TD2** HR-only | Already so by design: no request kind exists for India UAN or Singapore tax residency; each kind's form whitelist ignores any other value. Now proven by test: crafted kinds refused; crafted extra values on an offered kind never written; rows read-only ("Kept by HR"), UAN masked. | `tests/test_followup_td.py` TD2 |
| **TD3** contract copy | Approving a Vietnam tax code writes the employee AND `hr.contract.vietnam_tax_code` on the CURRENT contract only (running, started, not ended — new helper `_pbtx_running_contract`); never a closed, past or future contract; other countries never touch the contract. Written with `mail_notrack`; the contract chatter gets one line "Personal tax code changed to •••• 5678: approved change DET/… from My Payobook." (last 4 only). | `models/tax_request.py` (`_pbtx_vn_contract_copy`), `models/hr_employee.py` |
| Dependants lookup without Rize's label | Keyed on the contract component CODE, never the label: setting `pb_me_tax.vn_registered_dependants_codes`, ordered, default `VNREGISTER,DEPS,NPT`; the first code the running contract carries is compared; a past contract is never read. Found read-only: Rize `VNREGISTER` (repo tools); the Vietnam starter scheme and the demo world `DEPS` ("Number of Dependents" / "Registered dependants"), one demo scheme `NPT` (local demo copy `upd_p5e_pay`; there they are pay-data inputs, not contract components, so no note); **Sudima's scheme as built in the repo (`tools/prepare_sudima_payroll_review.py`) keeps no dependants count at all — only a relief amount `VNRELIEF` — so no note can be shown there** (correct: nothing to compare). | `models/hr_employee.py` |

**Tests (all pass; `t5` + `t6`)**

| # | Test |
|---|---|
| TD1.1 | VN, ID, IN with no number → "Add your tax number", 1, `/my/tax` |
| TD1.2 | SG and MY → no reminder |
| TD1.3 | gone while waiting; sent back → only the sent-back row; gone once approved/on file; back after "Take it back" |
| TD1.4 | in the home data; no mail created |
| TD2 | crafted kinds `tax_uan`/`tax_residency`/field name refused; crafted UAN/residency values on PAN / fund requests never written; rows read-only, UAN masked |
| TD3.1 | current contract copy written after approval only; past contract unchanged; chatter shows `•••• 5678`, never the full number (no tracking value either) |
| TD3.2 | a future and an ended contract are not written |
| TD3.3 | an Indonesia tax number never touches the contract |
| TD3.4 | payslip inputs, computed values and lines identical before/after the contract copy |
| DL.1 | `DEPS` with a Vietnamese label is found; when a contract carries two codes the first in the setting wins |
| DL.2 | an unknown code is not guessed from its label; naming it in the setting makes the note appear |
| DL.3 | a past contract's component is never compared |

Golden (script, same three payslips as T8): before/after install **IDENTICAL**; then a Vietnam
tax code approved for the golden person (employee + running contract written: True/True) and the
three payslips recomputed — inputs, computed values and lines **identical** for all three.

Suites (`t5`, fresh copy): pb_me_details 26/0, pb_employee_vault 21/0, pb_me_tax 41/0,
pb_me_portal 93 with the baseline six + `test_02_tile_meta…` (merge-time task M1) — 181 tests,
5 failed + 2 errors, = baseline + M1. vi/id PO regenerated from a fresh export (149 entries,
none missing). The home row was checked through the home data (TD1.4) and the rendered /my page of test H4 (same person, Vietnam, no number); no separate browser pass for this one row.

**Deployer read-only check (dependants code)** — per database, before or after go-live:
`select t.code, t.name, count(a.id) from hr_contract_advantage_template t join hr_contract_advantage a on a.advantage_template_id = t.id join hr_contract c on c.id = a.contract_id and c.state = 'open' where t.name ilike '%depend%' or t.name ilike '%phụ thuộc%' or t.code ilike '%DEP%' or t.code ilike '%NPT%' group by 1, 2;`
If a database shows a registered-dependants code other than `VNREGISTER`/`DEPS`/`NPT` (Sudima is
expected to show none), set `pb_me_tax.vn_registered_dependants_codes` there (System parameters);
nothing else changes.

New gotchas: **S2D-8** the tax code on `hr.contract` and `hr.employee` are plain fields with no
tracking; a future `tracking=True` would print the full number in chatter — write the copy with
`mail_notrack` and post a masked line. **S2D-9** `setup.sh`-style conf regeneration silently put
the port back to a clashing one; keep the phase port in the generator itself.
