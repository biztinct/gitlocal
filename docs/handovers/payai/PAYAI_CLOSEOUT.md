# PAYAI "Do it for me" — close-out (P0–P4)

Program doc `PAYAI_PROGRAM.md` · ledger `PAYAI_LEDGER.md` (PA1–PA56) · handovers/reports `P1…P4_*` · design page
https://claude.ai/artifact/3t8BLmEm28WzzQehS5BsKa. Final code: ship commit `6327ca99b` (pb_payai_actions 19.0.4.0.0),
branch 19.1, not pushed.

## What PayAI can do now (plain English)
A person types (or says) what they want in the PayAI pill or the helper's Ask tab, in English or Vietnamese. PayAI
only ever does what that person could do on the screen themselves, and never anything on a screen that is switched
off for them under Settings › Access and delegations.

**Look (green — nothing changes, no confirmation)**
- Open any screen they can reach ("open the runs board", "mở Phiếu lương").
- Show where a pay run is: people, net pay, stage, who it waits for — one run or a whole month.
- Download an approved run's Excel.
- "What can you do?" — the list, with examples that work when tapped.

**Prepare (amber — a plan card first; nothing happens until Do it; a way back)**
- Run payroll for a month and a scheme (optionally named people) → a draft run, made by the same steps the Run screen
  takes, with progress; Undo deletes the draft for 10 minutes.
- Send a draft run for approval; Withdraw for 10 minutes while nobody has decided.
- Change one person's pay value through Records' normal approval route; Undo puts it back for 10 minutes.
- Email an approved run's payslips (cannot be undone — the card says so).
- Prepare a government filing as a file to check (nothing is sent to the authority).
- Every card has "Open in the screen instead", filled in.

**Decide (red — only the person's OWN approvals, confirmed by TYPING a word)**
- Approve / send back (with a reason) / reject (with a reason) what is waiting for them. Word: APPROVE / SEND BACK /
  REJECT or DUYỆT / TRẢ LẠI / TỪ CHỐI; a tap or a spoken yes never counts. PayAI cannot undo a decision.
- Not theirs → who decides it, a "Remind <name>" button, and the inbox opened on that request.
- Recorded under the person's own name ("Recorded: approved by … via PayAI, typed confirmation"); the Audit console
  shows a "Typed confirmation" badge.

**Never** — deleting runs, payslips or records; clean-and-run; anything destructive is refused with "Not through PayAI".

## Owner decisions (2026-10-12, do not re-ask)
1. Phased Fable↔Opus workflow; Fable coded the P0 security kernel.
2. Green + Amber + Red allowed at launch.
3. Same rights as the screen — no back door: refused whenever the screen is hidden/locked under Access and
   delegations (lent roles included) AND whenever the method's own right is missing.
4. In the chat, with an escape hatch on every card ("Open in the screen instead").
5. English first, Vietnamese last (done in P4).
6. Amber = one tap; spoken "go ahead" only when the company switch is on. Red = typed word, never voice.
7. First release = the commands above.
8. Security fix first, on all databases (P0, done).
Pre-decided: keep the OpenAI key; lives in the pill + Coach Ask tab; payobook.com first, tenants' switches off until
asked; no "Odoo" in any string.

## What is live where
| | payobook | rize / payobook_template / abm / tenants |
|---|---|---|
| P0 security fixes (pb_payrun_wizard, biz_approval_workflow, om_hr_payroll, pb_payroll_ai_insights, pb_demo) | live | live (P0 went to every DB) |
| pb_payai_actions | live at 19.0.3.0.0 (P3); **P4 19.0.4.0.0 not deployed yet** | **not installed** (owner: payobook only) |
| Tier switches (Settings › PayAI can act) | look / prepare / decide ON; spoken go-ahead off unless switched | all OFF by default (any DB other than payobook starts off) |
| P4 Vietnamese catalogues (pb_payrun_wizard, pb_audit, om_hr_payroll, pb_payroll_ai_insights) | pending P4 deploy | pending — `-u` + PO gate wherever installed |
| pb_approval_config deep link, pb_learn "Ask PayAI" content | pending P4 deploy | pending (harmless without pb_payai_actions) |
Deploy steps: `P4_REPORT.md › DEPLOY NOTES`.

## Carried debts
- **PA28** — the Run screen (and PayAI's run driver) sends `compute_batch` no `formula_config_id`, so payslips are not
  stamped with the scheme at creation (the run is). Changing it changes the screen too: owner/Fable decision.
- **Engine idempotency keys** — Red decisions carry `payai-task-<id>`; Records apply, Pay & Deliver send and filing
  generation do not have an engine-level key yet (PayAI's own task state stops a double press).
- **PA32** — preparing a filing needs Government Reports User on top of the payroll officer group; the Compliance screen
  has the same hole. PayAI refuses at plan time with a plain card.
- **PA40** — 20 pb_payrun_wizard tests use fixed 2026 months and fail on a shared clone holding walk runs; move them to a
  far-future year or a fresh company.
- **PA3** — twelve `*_approved_write` context switches are still strings (closed at the door by PA2; converting them to
  `object()` tokens is ~40 call sites).
- **Team scope** — "this is not waiting for you" looks in Mine, then Everyone (when allowed); a line manager's "My team"
  scope is not searched.
- **Seat-holder live walk** — the typed-word path was never walked live as the seat holder (the QA login holds no seat);
  covered by clone tests only. Same for the Vietnamese walk (`P4_REPORT.md` walk list) and the deep link.
- **Settings card for payroll managers** — admin-only today (P1 open question).
- **Two Vietnamese words for "scheme"** in the product (chương trình lương / phương án lương) — PA53.
- **Demo divisions only** have Vietnamese names; a real tenant's scheme is understood by its own name.

## Ledger summary (PA1–PA56)
- Security (P0): PA1 wizard methods were callable by anyone → `@runner_only`; PA2–PA3 approval context switches scrubbed
  at the door; PA4 company scoping of period runs; PA5 Clean-and-Run never clears finished payroll; PA6 pulse alerts need
  payslip read; PA7–PA9 provider/config/redaction fixes.
- Foundation (P1): PA12 gates are judged `with_user` (tests run as su); PA13/PA16 run-payroll rights and role lanes;
  PA15 no comma in an ACL name; PA17/PA18 one language helper `T()`, `payai.task` is the audit (read-only to people);
  PA19 doors are navigation only; PA20 switches default off off-payobook.
- Amber (P2): PA22/PA25 door ranking; PA23 a stored field upgrades every DB; PA26 Records source stays `desk`; PA27 undo
  refusal sentence; PA28 open; PA29 stale browser tasks; PA30 prefill stash; PA31 read related records with
  check_access; PA32 filing permission; PA33 no model names in errors; PA34 backdate create_date in tests; PA35 every
  tested module in `-u`; PA36 card container CSS; PA37/PA50 clone harness; PA38/PA41 stage and deploy from
  `git archive`, bump only in the ship commit; PA39 promise = outcome; PA40 open.
- Red (P3): PA43 real scenario keys; PA44 never rewrite shared-branch history; PA45 engine vs drawer step words; PA46
  approvers need run read; PA47 idempotency + lock revision → Stale → fresh card; PA48 remind = the engine's reminder;
  PA49 a typed reason is read before the phrase table.
- Vietnamese (P4): PA51–PA56 (catalogue layout, staged-only export, scheme word, Learn generator side effects,
  environmental clone failures, inherited test methods).

## How to add a new Action (for future engineers)
1. **Pick the tier**: look (changes nothing) / prepare (plan card → Do it → undo where the screen has one) / decide
   (typed word, own decisions only) / never. No new tier without the owner.
2. **Write the class** in `payai/actions_<tier>.py`, decorated `@payai_action`, subclassing `Action` / `_Amber` /
   `_Red`. Declare `key` (stable, it is the tool name), `title`, `summary` (model only, English), `examples` (shown on
   "What can you do?" — each must be a sentence the phrase table understands), `slots` (`Slot(key, label, kind,
   required, describe)` — the model passes WORDS, never ids), `screen_keys` (the `pb.sidebar.item` xmlids — the
   Access-home half of the gate, PA-R1), `door_id` (the ⌘K row for "open the screen instead"), `right_subject` /
   `right_label` (refusal wording), `phrases` (anchored English regexes; named groups = slot texts), `priority`.
3. **Gate**: implement `method_gate(env, user)` with the screen method's own right, judged for `user` (never su,
   PA12). Second-model rights are checked in `plan` (PA32). Never `sudo()` in an Action (PA-R2).
4. **Resolvers**: reuse `payai/resolve.py` (period, run, scheme, division, door, person, amounts, days) or override
   `resolve_slot`; search AS the person; return `resolved` / `ambiguous` (≤ 6 chips) / `missing` (with a plain note
   and, where useful, `actions` or `door_id`) / `{'status': 'ask'}` for typed answers. Never trust an id from the model
   or the browser (PA-R3); chips carry values the server offered.
5. **Cards**: build with `payai/cards.py` (`card`, `note`, `door_action`, `ask_action`); every string through
   `_lt(...)` and `T()`; numbers/months/times through `i18n.num / month_label / stamp`. Amber: `plan()` returns
   `{card, vals, fingerprint}` (vals = exactly what will run) and `confirm()` / `finish()` / `undo()` call the SAME
   methods the screen calls, as the person. Red: set `confirm_word` and `confirm_word_vi`; `confirm()` passes the
   task's idempotency key and the plan's lock revision; raise `registry.Stale` when the world moved.
6. **Vietnamese**: add the Action's rows to `payai/phrases_vi.py` (marked; folded matching is automatic), add every
   new string to `i18n/vi_VN.po` (module line first, `odoo-python`/`odoo-javascript`, `code:addons/…:0`; one line per
   msgid/msgstr), run the PoFileReader gate. `test_payai_p4.test_01b` fails until every shown string has Vietnamese;
   `test_04` fails until every example routes in both languages.
7. **Tests** (clone, PA35/PA50): gate refused for the wrong person and for a locked screen; ambiguous → chips; expired
   plan; fingerprint changed → fresh card; the plan's promise equals the outcome (PA39); undo; audit line under the
   person's name; no "Odoo". Fixtures in a far-future year (PA40).
8. **Learn**: if a walkthrough fits, offer `actions_amber.learn_action('<sc_key>')` on the done card (PA43).
