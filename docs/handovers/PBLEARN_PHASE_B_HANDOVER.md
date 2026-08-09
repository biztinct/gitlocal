# pb_learn Phase B — Implementation Handover (Run B1 + Run B2)

**Read first:** `docs/handovers/PBLEARN_LEDGER.md` (all sections, including the Run A1/A2
additions and Deploy notes), then `docs/tutorial_poc/design_v2.html` §2–§7. Phase A is
merged (commits `a9aaf462…9c5b7351`) — the module, generator, authoring source and tests
are your reference implementation; extend them, do not restructure them.

**Mission:** (B1) extend pb_learn to the **Setup section** — Formula Engine, Salary
Structures, Statutory, Integrations — at the same quality bar as Pay Run; (B2) the
**demo live track**: per-user division assignment, the live capstone mission mL1, and
the live-value resolver. All content flows through `docs/tutorial_poc/author/` + one
generator run per commit; generated files are never hand-edited.

## Binding non-goals (Phase B)

- NO LLM (`_compose` stays unported).
- NO pb_coach changes; NO PayAI changes.
- Live missions run ONLY for `pb_demo.group_payobook_demo` users (inverse isolation
  test extends to the runtime); fixture missions stay fixture-pure (the never-call-a-
  product-method test must keep passing).
- The live mission runner NEVER intercepts, blocks or performs product actions — it
  instructs, observes state, and verifies. (Consequence cards are teaching steps shown
  BEFORE the user acts; enforcement stays with the product's own gates.)

---

# Run B1 — Setup section

## B1-1 · Verified plumbing (do not re-derive)

- Sidebar leaves (pb_sidebar/data/pb_sidebar_data.xml): `pb_sidebar.item_formula`
  (tag `pb_formula_studio`), `item_structures` (tag `pb_structures`), `item_statutory`
  (tag `pb_statutory`), `item_integrations` (tag `pb_integrations`). Groups: formula =
  officer+; structures/statutory = manager+; integrations = integration_user/manager+.
- Cockpits (all OWL client actions):
  - `pb_structures/static/src/xml/structures.xml` (t-name `pb_structures.PbStructures`,
    registered structures.js:86; data via `pb.structures.get_board`). Regions: head
    :10-16, "New structure" btn :15, KPI band :18-24, filters :26-62, card roster
    :64-77, footer link :80-83.
  - `pb_statutory/static/src/xml/statutory.xml` (registered statutory.js:61; data via
    `pb.statutory.get_statutory_data`). Regions: head+2 buttons :10-19, KPI band
    :21-28, "Active insurance rates" table :30-49, "Tax brackets" panel :51-67,
    seg toggle+chips :70-85, policy roster :86-94, tax roster :96-104, launches
    :107-113.
  - `pb_integrations/static/src/xml/integrations.xml` (registered integrations.js:97;
    data via `pb.integrations.get_board`). Regions: head :10-14, "Connect a system"
    :15-17, KPI band :20-27, filters :29-56, connector roster :58-70, links :74-80.
  - Formula Engine: `pb_formula_studio/static/src/xml/studio.xml` already carries 35
    `data-coach` anchors (fs-config, fs-components, fs-formula, fs-namesletters,
    fs-deps, fs-flow, fs-preview, fs-editai, fs-add, fs-arrows, fs-card, fs-simulate,
    fs-whatif, fs-payslip, fs-mapping, fs-rates, fs-views, …). ADD NOTHING to
    studio.xml; instead **promote the anchors pb_learn content references from the
    `foreign` whitelist to registered `product` entries** in anchors.json (they are
    literal attributes; the registry tests must then own them).
- Statutory backend (`pb_statutory/models/pb_statutory.py`; models in
  `pb_hr_payroll_vietnam/models/`):
  - `vietnam.insurance.policy`: fields `effective_date`(:30) `end_date`(:35)
    `active`(:45), rates `si_employer_rate`(:51) `si_employee_rate`(:56)
    `si_max_salary_ceiling`(:61) `hi_employer_rate`(:78) `hi_employee_rate`(:83)
    `ui_employer_rate`(:101) `ui_employee_rate`(:106), computed `total_employer_rate`
    (:167) `total_employee_rate`(:172). `_sql_constraints` `code_company_uniq`
    (:181-184). **There is NO version/supersede chain** — the cockpit selects the
    current policy as latest `effective_date` among `active=True`
    (pb_statutory.py:54-59).
  - `vietnam.tax.table`: `tax_year`(:31) `personal_deduction`(:68)
    `dependent_deduction`(:73), `slab_ids` → `vietnam.tax.slab`
    (`income_from/income_to/tax_rate/fixed_amount`).

## B1-2 · Content scope (design_v2 §5 pattern, Setup line)

- New station line `setup` in the selection; stations (4): **formula** (lesson L5),
  **statutory** (lesson L6 ★ with the **trace moment**), **structures** (outline —
  legacy framing per design), **integrations** (outline).
- **L5 · "The formula is the payslip"** (~7 steps over a NEW formula replica screen):
  config switcher → component list → the formula in plain language (chips) →
  names/letters → depends-on/used-by → live preview → edit-with-care consequence
  (editing a live config affects every future slip of that division). Reuse the v1
  prototype's formula screen content/tone (docs/tutorial_poc/data.js SCREENS.formula +
  v1 tour_formula ideas) — numbers from the worked example only.
- **L6 · "Statutory — the rules the law writes"** (~8 steps): what/why → who pays what
  (8/17.5 · 1.5/3 · 1/1 as the PRACTICE policy's numbers) → base & ceiling → PIT table
  + relief → **trace moment**: `moment_from` the practice policy's BHYT rate,
  `moment_to` the BHYT line on Mai's payslip replica (this is the §11-promised trace —
  cross-screen: render the payslips replica for that step) → **the versioning truth**:
  teach the REAL product mechanics — a rate change = a NEW policy record with its own
  `code` (unique per company) and `effective_date`, end-dating the old one; the cockpit
  applies the latest effective active policy → consequence card (affects every future
  slip in every division; not applied retroactively unless a slip recomputes) → quiz
  (the m2-style effective-date judgement from v1, adapted to the real mechanics).
- **Mission m4 · "Apply a BHYT rate change — properly"** (fixture, full, confidence
  `setup` +30): on the statutory replica — create new policy record (new code) → set
  BHYT employee 2.0% (wrong values coached: 1.5 = current, 3.0 = employer's) →
  effective-date decision (immediate vs 01/08 boundary; immediate triggers recovery
  because June/July runs are open) → preview impact (Mai −57,000 net: BHYT 240,000,
  taxable 1,960,000, PIT 98,000, net 12,862,000 — recompute via the `payslip()`
  function, don't hand-type) → commit with undo step. m5 outline: "Map a new allowance
  into a config" (formula line).
- **Screens (4)** + SCREEN_CTX + suggest chips; **intents (~10)**: whysetup (dynamic),
  changerate (the F5-style consequence answer, statutory screens), whichpolicy ("which
  policy applies today" — the latest-effective-active rule), ceiling (insurance base &
  cap calc), pitcalc (relief + brackets calc on Mai), configvsstructure (formula vs
  legacy structures), editlive (consequence of editing a live config), whichconfig
  ("which config does division X use" — DEMO_<DIV>_END convention), syncbroken
  (integrations: broken sync → dashboard warning → fix before payroll week), practice.
  Reuse/extend existing `bhxh` intent to also cover statutory screens.
- **Columns**: the 6 statutory KPIs, 5 structures KPIs, 6 integrations KPIs, and the
  key formula-studio regions the lesson names (~20 records).
- **Replicas** (engine/screens.js): 4 new — formula (3-pane: components list, formula
  chips card, live preview — port from v1 prototype's SCREENS.formula), statutory
  (policy rates table + PIT slabs + practice-policy card — port v1 SCREENS.statutory
  including the practice-version affordances m4 needs), structures (KPI band + card
  list), integrations (KPI band + connector cards). All anchors kind `practice`.
- **Contract checks (add ~8):** insurance-policy field names exist
  (`si_employee_rate, hi_employee_rate, ui_employee_rate, effective_date, end_date`);
  `code_company_uniq` constraint present; cockpit selection rule (`effective_date
  desc` + `active` filter) still in pb_statutory.py; tax-table fields
  (`personal_deduction, dependent_deduction, tax_year`); the 4 Setup sidebar leaf
  xmlids; formula studio anchors the content references are literal in studio.xml;
  DEMO config code convention `DEMO_%s_%s` in demo_generator.py:116-118 (taught by
  whichconfig).
- Glossary additions (~4): policy, effective date, ceiling/trần, config code.
- VI throughout, same register; tenant slot additions only if a name is genuinely
  tenant-variable (probably none — do not add speculative slots).

## B1-3 · Verify + commit

Full A-suite (gen --check, check_contract, py_compile, node --check, XML, anchor lint,
resolver simulation, VI parity) + confirm Pay Run content unchanged (regenerated files
for Pay Run should show zero diff except where shared files append). Commit:
`feat(pb_learn): Phase B1 — Setup section (formula, statutory, structures, integrations)`.

---

# Run B2 — the demo live track

## B2-1 · Verified plumbing (do not re-derive)

- Demo divisions: 6 keys `retail, manufacturing, logistics, corporate, it,
  construction` (pb_demo/models/demo_catalog.py:274-303; name_en/name_vi per key).
  Configs `DEMO_<DIV>_END|MID` (12) with `pb_division` on `hr.formula.config`
  (demo_generator.py:37,247); `resolve_config(division, cycle)` at :116-118.
- Open month is **June 2026** (`_OPEN_MONTH = 6`, demo_history.py:22-26): per division
  a Mid run (done) and an END June run left `draft`, `locked=False`. April/May runs
  `done`+`locked`.
- The wizard is division-aware only for demo users: `pb_demo/models/demo_payrun.py` —
  `get_defaults` override :88-109 injects `divisions` and locks period to June
  (:104-108); `prepare_run` :153-201 (creates run `is_demo=True`, company = group co);
  `compute_batch` :203-268 (formula-config payslips). Run's division is DERIVED:
  `hr.payslip.run.pb_division` stored compute from first slip's
  `formula_config_id.pb_division` (pb_payruns/models/hr_payslip_run.py:106-125).
- Signup seam: `pb_demo_portal/controllers/main.py:235 _create_demo_user` (writes
  user_vals :243-274, partner extras :277-283). Demo group
  `pb_demo.group_payobook_demo` (implied: base.group_user + payai user). Demo company
  identified by NAME `'Payobook Vietnam JSC'` (demo_catalog.py:25) — **no is_demo on
  res.company**.
- Approval chain states for predicates: draft → level0 → level1 → level2 → done
  (ledger); submit is `pb.payrun.wizard.submit_for_approval` → `run.done_payslip_run()`
  (pb_payrun_wizard/models/pb_payrun_wizard.py:299-335).

## B2-2 · Per-user division assignment (touches pb_demo + pb_demo_portal — allowed)

- New field `res.users.pb_demo_division = fields.Char()` (in pb_demo). At
  `_create_demo_user`, assign round-robin over the 6 division keys (count existing
  demo-group users modulo 6 — simple, no new model). Existing demo users without an
  assignment: helper `_ensure_demo_division()` assigns lazily on first read.
- `demo_payrun.get_defaults` override (extend, in pb_demo): when the user has an
  assignment, reorder `divisions` so the assigned one is FIRST and set `d['division']`
  to it. Do not remove the others — prospects may explore; the mission validates
  against the assignment.

## B2-3 · Live mission runner (pb_learn)

Model: `learn.mission.kind='live'` becomes runnable. New step mechanics, additive to
the existing schema:

- `learn.mission.step` gains `check` (Char, optional): the key of a **server-side
  predicate**; and `is_ack` (Boolean): a step the learner confirms manually when no
  state is observable. A live step with neither is instructional (Next-gated).
- New model method `learn.mission.live_check(mission_key, step_key)` → the predicate
  registry, a dict of key → callable(env, user) returning `{'ok': bool, 'note': str}`.
  Phase B predicates (all read-only searches, no sudo beyond what the demo user can
  read):
  - `june_run_computed`: an `hr.payslip.run` exists with `is_demo=True`,
    June 2026 dates, `pb_division == user.pb_demo_division`, slip count > 0.
  - `june_run_submitted`: same run `state in ('level0','level1','level2','done')`.
  - `june_run_officer_done`: state in level1+ … `june_run_done`: state == 'done'.
  - Guard: every predicate returns `ok=False, note='live missions need the demo
    world'` when the user lacks the demo group OR company name != 'Payobook Vietnam
    JSC' (the inverse isolation, enforced server-side).
- Runner UX (journey.js): live missions render the SAME mission panel but over the
  REAL app — the panel is a slim docked card (reuse coach drawer chrome, no dimming),
  steps advance on `live_check` polling (10s while the mission is open, plus a
  "Check now" button — no websockets) or on ack. `nav` steps deep-link via
  `doAction` to the real action (`pb_payrun_wizard.action_pb_payrun_wizard` etc.).
  The consequence step (`is_consequence`) renders BEFORE the compute instruction —
  teaching, not interception.
- Events: reuse mission_* event kinds; detail carries the step key only.
- Tests: extend test_mission — live missions refuse to start for non-demo (server
  method raises/returns refusal); fixture missions still never call product methods;
  predicate registry only contains read-only calls (assert no `create/write/unlink`
  tokens in the registry source, same style as the coach-cannot-act contract check).

## B2-4 · mL1 content (authored, generated like everything else)

`mL1 · "Run your division's June payroll — for real"` (kind live, line payrun, demo
screen runpayroll, confidence `run_live` +40): intro (what's real, the ephemeral-demo
note, soft-gate nudge "do m1 first" with link — nudge only) → open Run Payroll (nav +
ack) → consequence card (REAL: scope = your division's June END run in the shared demo
world; reversible = drafts deletable, submit is not silently undoable; verify = your
division is preselected) → compute (check `june_run_computed`) → open the run, review
flags (ack, with pointers) → submit (check `june_run_submitted`) → approval journey
(ack steps per gate with `june_run_officer_done`/`june_run_done` checks where the demo
user's own role can act; otherwise observe) → debrief comparing with the m1 fixture
rehearsal + confidence. Bilingual, worked-example-free (live numbers are on screen —
the mission never asserts amounts).

## B2-5 · Live-value resolver (small, bounded)

- New model `learn.live` with ONE method `values(keys: list[str]) -> dict`, whitelist
  registry key → read-only lambda. Phase B keys (6): `june_net_total(division)`,
  `june_run_state(division)`, `active_policy_rates` (si/hi/ui employee+employer from
  the latest-effective-active policy), `pit_relief` (personal_deduction/
  dependent_deduction from latest tax table), `flagged_count(division)`,
  `division_name`. Unresolvable/absent → key omitted.
- Token syntax in content: `{{live:key}}` resolved at ask()/bundle time in the
  answer/step body; **fallback = the static authored text**: the generator validates
  that any body containing `{{live:` also carries a `live_fallback` (new optional
  field on step/block) and the renderer swaps the whole sentence, never a bare token.
  Use it SPARINGLY: exactly 2 sites — the statutory `whichpolicy` intent (live rates)
  and the payruns `whatnext` for demo users (June run state). No other content uses it.
- Contract: the whitelist source must contain no write tokens (checker entry).

## B2-6 · Verify + commit

A-suite + new tests compile; grep-proof no interception (no patches of product
components, no `click` synthesis outside pb_coach); commit
`feat(pb_learn,pb_demo,pb_demo_portal): Phase B2 — live capstone, per-user division,
live-value resolver`.

Report back (both runs, single message each): per-section done/how, counts, deviations
+ why, server-only list, ledger additions, commit hashes.
