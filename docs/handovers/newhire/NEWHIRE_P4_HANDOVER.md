# NEWHIRE P4 — From Hiring, Many at once, and the payslip example

Read first: `NEWHIRE_LEDGER.md` (binding), the P3a and P3b reports (structure), `NEWHIRE_FACTS_ONBOARD.md` §B4, §D6, §K
(Hiring), `NEWHIRE_FACTS_CORE.md` §F (payslip example — the design verdict there is the plan; **do not re-derive**).
Open the POC: step 1's three tiles and the right panel's dark payslip box.

Work ONLY in `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). No deploy, no server access.

**Hero moment**: typing the wage and seeing a real payslip — worked out by the person's actual pay scheme, with their
usual answers — settle in the right panel within a second, and change when one answer is flipped.

Two independent parts. Build and commit Part B (the example) first: it is the riskier one and must not be squeezed.

## Part B — "A month's payslip · example" (right panel)

### B.1 What it is
`pb.new.hire.payslip_example(draft) -> {ok, month_label, lines:[{name, amount, band:'earning'|'deduction'|'info'}],
gross, deductions, net, employer_cost, currency:{symbol, position, decimals}, scheme, notes:[str], took_ms}` or
`{ok: False, reason, fix, step}`. Display only. It never leaves a trace.

### B.2 How (FACTS_CORE §F verdict — follow it)
Behind `require_hr`. Inside `with self.env.cr.savepoint(): … raise _Rollback()` (clone the `_Rollback` precedent in
`pb_blueprint/models/blueprint_components.py`), context `tracking_disable=True, mail_notrack=True,
mail_create_nolog=True, mail_create_nosubscribe=True`, sudo:
1. Create the employee and the contract **through the same hooks the real apply uses** (call the P1/P2 create path with
   the draft's values in a "preview" mode that skips every welcome leg and the proposal) so Country of work, currency,
   the usual answers and the person's changes are exactly what a real hire would get. `flush_all()` (NH4).
2. Create a draft `hr.payslip` for ONE FULL calendar month — the month of the first day — with the resolved scheme
   (`formula_config_id`, `calculation_method='formula'`), worked days from the product's own onchange
   (`onchange_employee_id(date_from, date_to, emp.id, contract.id)`).
3. Inputs from `slip._get_formula_input_values(config)`; evaluate with the read-only sample kernel
   (`hr.formula.sample.data.new({'config_id': id})._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)`).
   **Never call `compute_sheet`** (it writes on the shared scheme rules). Build `hr.payslip.line.new({...})` for each
   payslip-visible rule exactly as the preview precedent `pb_formula_studio.preview_from_payslip` does (read it and reuse
   its helper if it is callable; otherwise mirror it and say so) and take totals from `.pb_pay_totals()` — the one
   pay-band rule. Lines shown: earnings and deductions the payslip itself would print, in payslip order, zero lines hidden.
4. Copy plain Python values out, THEN roll back, then `self.env.invalidate_all()`.

### B.3 Honesty rules (they are the feature)
- Title "A month's payslip · example". First note always: "Worked out by <scheme> for a full <Month>, from the scheme's
  usual values." When the first day is not the 1st: "<First name> starts on <date>. Whether the first pay is reduced for
  the part month depends on how this pay scheme counts days." (FACTS_CORE §F: no engine-wide joiner proration — never
  show a prorated figure the engine did not produce.)
- Inputs that come from a pay data file or a connected system fall back to the scheme's usual values → note "Some
  values on this scheme come from the monthly pay data file; the example uses the usual ones." (detect via the
  provenance the input builder returns when asked for it).
- Evaluation errors → `{ok False, reason "<scheme> could not work out an example: <first error in plain words>", fix
  "The hire is not affected. Check the scheme in Mapping."}`. No scheme → `{ok False, reason "No pay scheme pays this team
  yet.", step 'role'}`. Country mismatch → compute with the team's scheme and add the mismatch note.
- Seat limit (NH7) or any create refusal → `{ok False, reason "An example cannot be shown because your plan has no free
  employee place.", fix "You can still send the hire; it will wait for a place."}` — verify what a real send does at the
  limit and make the sentence true.

### B.4 Rails and proof (tests P1…)
P1 **no trace**: after 20 calls — counts of `hr_employee`, `hr_contract`, `hr_payslip`, `hr_payslip_line`,
`hr_contract_advantage`, `mail_message`, `mail_followers`, `ir_attachment`, `resource_calendar`, `resource_resource`,
`res_partner`, `pb.shift.pattern.member`, scheme-map stale flags and every `write_date` on `hr.formula.rule` /
`hr.formula.config` of the scheme are unchanged; no sequence number consumed for payslips (compare the next real payslip
number before/after); no row in any mail queue. P2 the example equals a REAL payslip computed the product's normal way
for an identically-created person on a fixture scheme (gross, deductions, net to the cent) — create the real one in the
test, compare, let the test transaction roll back. P3 usual answer flipped → example changes accordingly. P4 errors:
no scheme, evaluation error, seat limit, non-HR. P5 concurrency: two calls in two cursors do not deadlock (the calendar
clone takes an advisory lock — FACTS_CORE §F risk a) — if they can, take the lock with NOWAIT semantics and answer
"busy, try again" which the client retries silently. P6 time: log `took_ms`; on the walk world's largest scheme report
the median of 10; if over 1.5 s, cache by a hash of (scheme id + rule write dates, country, wage, month, answers) in an
in-memory LRU on the registry for 5 minutes and report the cached/uncached numbers.
Client: `record_panel.js` replaces the "appears in a later release" line with the dark box per POC `.pvo`: debounce 500 ms
after the last change of wage / team / country / first day / usual answers / contract kind, sequence-guard replies,
skeleton shimmer while waiting (never a spinner over old numbers — old numbers dim to 50 % until the new ones land),
amounts via the currency's own formatter, the notes as small text under the total, `{ok False}` as the calm grey card
with reason + fix (+ a "Go to step" link when `step`). Reduced motion respected. Nothing is requested until name, team,
country and wage exist.

## Part A — From Hiring and Many at once

### A.1 Step 1 source tiles (POC `vWho`)
"Type it in" (default) · "From Hiring" (shown only when `pb.hiring.offer` is installed and the user may read offers;
count of signed offers waiting in the sub-line; zero → the tile stays, its sub-line reads "No signed offers are waiting")
· "Many at once" (opens the Updates joiners sheet — find the action/xmlid the Updates desk uses for the joiners sheet and
open it; if that sheet is switched off for the company say so in a toast with where to switch it on).
`hiring_offers() -> [{offer_id, name, job, team, team_id, job_id, manager_id, first_day, wage, wage_currency, signed_on,
received:[{key,label}], missing:[{key,label}], bgv:{ok, sentence}}]` — domain per FACTS_ONBOARD §K2 (`state == 'signed'`,
join status pending/changed), company-scoped, in the user's own rights. Each row shows green chips for what the
candidate already sent and grey ones for what is missing (labels in the studio's own item words), and the background
check sentence as an amber line when `check_ready()` is not ok (warning only, as in Hiring).
"Bring across" fills the draft (name, work/personal email, phone, team, job, manager, first day, wage) and sets
`offer_id`. Truthful info row under the list (ledger §2): "Files the candidate sent come across to <first name>'s
record. The bank paper becomes a bank request for a second person to approve. Numbers are asked for in the welcome
link."

### A.2 What "received" means (mapping without touching `pb_hiring`'s tables — D10)
Hiring's request items carry no category (FACTS_ONBOARD §B4). Map by the seeded request lines (match the item's name
to the seeded templates' names in the company's language and in English; xmlids in `hiring_doc_templates.xml`):
identity → the studio's `id_number` paper row (file only — the number is still asked/typed); degree → the certificate
paper; tax → the tax-card paper (file only); bank → the `bank` item; photo → the person's photo; payslip and anything
unmatched → "Other papers" (comes across, satisfies nothing). In step 5 a matched row shows "Received in Hiring · <date>"
with the choices reduced to what is still open (e.g. identity card received → the row asks only for the number: "Ask for
the number" / "I have the number").

### A.3 Apply (new leg `hiring`, right after `papers`)
For `offer_id` (re-validated: still signed, same company, not joined):
1. Each received file → a `pb.employee.document` in its mapped category (COPY of the attachment; the original stays on
   the Hiring request), unverified. Photo → `image_1920` when the person has none.
2. Bank paper → `pb.bank.ocr.create_from_upload({name, mime, data, employee_id})`, `run_ocr`, then `do_action('submit')`
   only when the reading produced an account number that passes validation; otherwise leave the request in draft and
   report amber "The bank paper came across but could not be read. Open it in Bank requests to finish." Never invent values.
3. **Close the offer through Hiring's own method**: read `pb_hiring/models/offer_closure.py:70-301` first and establish,
   with tests, what `action_confirm_joined` does when the applicant ALREADY has this employee, a running contract, a
   login and an open joining case (FACTS_ONBOARD §K1 left `_ensure_employee`/`_ensure_contract` reuse unverified). Link the
   applicant to the studio's employee the way Hiring itself links them, then call `action_confirm_joined(joined_on=first
   day)` so Hiring's remaining legs run (applicant marked hired, pay package draft, benefits, signed offer papers filed,
   "tell them", requisition filled, hire date stamped). Where a Hiring leg would DUPLICATE what the studio already made
   (second contract, second login, second case, second laptop request), neutralise that leg for this call only via an
   inherited override in `pb_new_hire` keyed on a context flag — never by editing `pb_hiring` — and prove each with a test.
   Hand-over of the candidate's buddy/laptop wishes (`_hand_over_buddy`, `_hand_over_laptop`) must still run.
4. Ask rows are not created for items already received.
A failed step is an amber leg row (the hire stands), as every welcome leg.

### A.4 "Confirm they joined" in Hiring
From `pb_new_hire` (patch/inherit, no edits in `pb_hiring`): where Hiring's board offers "Confirm they joined" for a
signed offer, the button opens the studio with that offer brought across. Keep Hiring's own confirm reachable as a quiet
secondary action "Confirm without the form" for the user roles that can use it today, so nobody is blocked on joining day.
Report exactly which JS/XML you patched and how it degrades when `pb_new_hire` is not installed (it must simply not exist).

### A.5 Tests (H1…) and walk
H1 `hiring_offers` domain, rights, chips from a seeded request with some items received. H2 bring-across draft values.
H3 apply: documents copied to the mapped categories, originals intact, photo set. H4 bank paper: readable → request
waiting for a second person; unreadable → draft + amber. (Stub the reader in tests — no outside calls.) H5 closing: offer
joined, applicant hired, ONE employee / ONE running contract / ONE login / ONE case / ONE laptop request; Hiring's
package/benefits/signed-copy legs ran. H6 asks skip received items. H7 offer no longer signed at approval time → leg
amber, hire stands. H8 no `pb.hiring.offer` model → tile absent (patch the feature check). H9 Many at once opens the sheet.
Walk (seed two signed offers, one with most papers and a bank file, one with none): G1 tiles and offer list; G2 bring
across → steps 2, 3, 5 reflect it; G3 send → approve → record, documents, bank request, offer shows Joined in Hiring,
New joiners row; G4 Hiring's "Confirm they joined" opens the studio; "Confirm without the form" still works; G5 the
payslip example on three countries, mismatch, no scheme, flip a usual answer; G6 type fast in the wage box (no flicker,
no stale number); G7 340 px; G8 console clean.

## Report back — `NEWHIRE_P4_REPORT.md`
Same sections as before. Add: the no-trace proof table (B.4 P1) with the counts; the timing numbers; what
`action_confirm_joined` really reuses (correct FACTS_ONBOARD §K1); every patch point in Hiring's screens. Commit
feature-scoped with explicit paths (Part B first), report + ledger gotchas as the final docs commit. Do not push.
