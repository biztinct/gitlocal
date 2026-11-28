# PAYBUILDER — build handover

**For:** the Codex build session. **From:** the architect session, 2026-11-28. **Base:** `origin/19.1` at `2882e1a38` or later.
**Read first, in this order:** `PAYBUILDER_LEDGER.md` → `PAYBUILDER_DESIGN.md` → `docs/design/pay-builder-poc.html`
(open it, click all four homes and both example schemes) → `PAYBUILDER_FACTS.md` → this file.

Facts are cited as **F§x** = `PAYBUILDER_FACTS.md` section x. They were verified with file:line; **do not re-derive
them**. If a line number has drifted, search the identifier.

---

## 0. Before you write code

1. Worktree: `git worktree add ../gitlocal-worktrees/paybuilder -b paybuilder origin/19.1` (never the main checkout).
2. Copy the design pack into the worktree (`docs/handovers/paybuilder/*`, `docs/design/pay-builder-poc.html`) and
   commit it first: `PAYBUILDER docs: design pack`.
3. Record a **test baseline** (counts + named failures) for `pb_new_hire`, `pb_formula_studio`, `pb_pay_package`,
   `pb_contracts`, `pb_job_change`, `pb_joining`, `pb_hiring` before changing anything (how to run: F§K).
4. Build a local database that has an **active** scheme of each shape in §3.1 (fixtures in §7.0).

## 1. Scope

One shared block, the **Pay Builder**, and its four homes (DESIGN §8):

| Phase | Delivers |
|---|---|
| **P1** | New module `pb_pay_builder`: server facade (work out / explain / work back), the OWL block, styles. Add employee step 3 swapped to it; hire writes every typed value to the contract. |
| **P2** | Formula Studio: the plainer "Where does this amount come from?" switch with its live-scheme warning; "Main pay amount" and "typed per month / per year" settings. |
| **P3** | Hiring offer: Pay Builder door, values travel into Add employee, pay table in the letter switch. |
| **P4** | Contract panel "Change pay" (before/after, dated, through Change job's pay-change route). Joining page "Your pay" card. |
| **P5** | Lessons, vi/id sweep, browser walks, release ×5, report. |

### Binding non-goals (do not build, do not "improve")

- N1 No second formula engine and no client-side evaluation of pay. One engine: `_Engine` (F§D.2).
- N2 No second take-home search. Reuse `take_home_solver.solve` (F§D.2).
- N3 No call to an external LLM, and no call to `explain_formula_ai`, from anything in this feature (F§E, F§M6).
- N4 No change to how a pay run resolves inputs (`_get_formula_input_values`, F§B.2), to `_pb_usual_answer_rules`
  (F§B.3 — the automatic fill depends on it), or to pay bands/totals (F§F).
- N5 No restyle of the Add employee right column (`RecordPanel`, `.pbnh-pv*`, `.pbnh-pvo*`) — owner decision D6.
  Its payload and template stay as they are.
- N6 `pb_contracts` gets **no** Python dependency on the formula engine (F§I, F§M15). Enter through a registry door.
- N7 No edit of formulas, rates or ceilings from the Pay Builder; no saving of what-if amounts.
- N8 No back-fill of existing contracts, no data migration, no change on any tenant's schemes at release.
- N9 Text-kind components (`is_text_component`, kinds `text/identifier/date`) are not Pay Builder lines in this build.
- N10 Do not retire "Build from a total" or the contract panel's existing "Work back from take-home" door; leave both.
- N11 Part-month examples, working back from gross or cost, two schemes for one person: out.
- N12 The word "Odoo" never appears in any user-visible string (labels, help, toasts, emails, manifest `name`/`summary`,
  `.po` msgstr). Technical identifiers are untouched.

## 2. The problem being fixed (know this before designing a query)

F§B and F§M1: a contract component with no line on the contract is **0 in the pay run** (`hr_payslip_formula.py:835-840`);
its `default_value` is only what the automatic fill writes for a *new* contract when it is non-zero. Add employee can only
write lines for `_pb_usual_answer_rules()` (non-zero defaults). So on a scheme driven by a zero-default contract
component (live: Rize India, `INANNFIX` "Annual Fixed CTC") a studio hire is paid 0: the typed wage lands in
`hr.contract.wage`, which that scheme never reads. The Pay Builder asks for **every** per-person amount the scheme needs
and writes each as a contract line.

## 3. Architecture

### 3.1 The five shapes of scheme the block must handle

| Shape | Example | Headline |
|---|---|---|
| S-WAGE | an input coded `BASIC`/`WAGE`/`BASE`, or mapped to `hr.contract.wage` (F§B.1, `_th_wage_codes`) | the contract wage, "Monthly wage" |
| S-COMP | no wage input; a money contract component drives the net (Rize India) | that component |
| S-BOTH | wage input **and** other contract components | the wage; the others are "Also asked" / You-set lines |
| S-NONE | no wage input and no contract component upstream of net (everything from the file) | the wage (kept, as today), with a quiet line: `This pay scheme takes its amounts from <source> each month.` |
| S-NONET | no take-home line | per DESIGN §4.2 foot |

### 3.2 New module `pb_pay_builder`

```
pb_pay_builder/
  __manifest__.py        depends: pb_formula_studio, pb_hr_payroll_formula, pb_import_kit, pb_scheme_map, pb_pay
                         (verify each is already in pb_new_hire's closure — F§K; add nothing standard)
  models/
    scheme_ext.py        _inherit hr.formula.config / hr.formula.rule: new fields + classification helpers (§3.3)
    builder.py           AbstractModel pb.pay.builder — work_out / explain / work_back (§3.4-3.6)
    formula_words.py     pure Python: formula text → tree → chips + sentence (§3.5)
  static/src/js/pay_builder.js      OWL component PayBuilder (§3.7)
  static/src/xml/pay_builder.xml
  static/src/scss/pay_builder.scss  classes pbpb-*, tokens per DESIGN §12
  i18n/ (pot, vi_VN.po, id_ID.po)   tests/   security/ir.model.access.csv (only if a model needs it)
```

Fields added by `_inherit` live in `pb_pay_builder` so that `pb_hr_payroll_formula` is **not** upgraded (F§K: its
dependent tree is large). Manifest `name`: "Pay Builder"; `summary` in plain words; no vendor name.

Why a new module: four homes in four modules need one block; `pb_new_hire`, `pb_pay_package` and `pb_joining` can depend
on it; `pb_contracts` reaches it through a registry (N6).

### 3.3 Classification — one function decides what every rule is

`hr.formula.config._pbpb_layout()` (sudo-safe, record-free, memoised per `(config.id, write_date, md5 of rule content)`
exactly like `_example_key`, F§D.2/NH53) returns, in scheme order:

| Rule | Becomes | Condition |
|---|---|---|
| `column_type == 'formula'`, band NET (`net_role == 'net'`) | the **Take-home** figure | first NET line (`pb_net_line` semantics) |
| `formula`, `appears_on_payslip`, `wants_number`, band earning / deduction / employer cost | **Worked out** line in Earnings / Deductions / Paid by the company | F§F bands via `_Engine` line specs |
| `input`, `is_contract_component`, numeric fill kind, has a band | **You set** line in that section | editable |
| `input`, `is_contract_component`, no band (info), **upstream of a shown line or of net** | **Also asked** (Card A) | control from `value_label_control()` / `value_kind` (F§C) |
| `input`, not contract component, has a band | **Each month** line | source word from `declared_sources()` (table below) |
| `input`, not contract component, no band, upstream | hidden; takes its full-month/usual value; counted in the note | e.g. days paid |
| `constant` | never a line; appears as a locked chip inside explanations | |
| anything else (text kinds, not upstream, not on the payslip) | not shown | N9 |

"Upstream" = `_Engine.upstream()` of the shown lines' codes + net (F§D.3). Detail lines
(`net_role_detail`, `pb_counts_in_totals()` False) keep their section and carry `detail: True`.
**Total-line rule:** when a section's only counting line is a formula and every other line in the section is a detail of
it (the common "Total (Earnings)" shape), render the details as ordinary rows and use that counting line as the section's
total row (its own name replaces "Gross pay"/"Total deductions" only if it differs meaningfully; otherwise keep the
design's label). Otherwise detail lines render indented and muted (DESIGN §4.2). Section totals always come from
`pb_pay_totals()` — never from summing rows in JS.

Source words for Each-month lines (first declared source by rank, F§B.1): `feed`/`rule` → "the connected system";
`excel` → "the pay data file"; period codes, worked days, clock → "the timesheet"; none → no source ("Each month").

**Main pay (the headline):**
1. `hr.formula.config.pbpb_main_rule_id` (new M2o, optional, domain: this scheme's contract-component money inputs) wins.
2. Else, if the scheme has a wage input (`_th_wage_codes`, F§B.1) → headline is the **contract wage** (`is_wage: True`).
3. Else the lowest-`sequence` money contract component that is upstream of net (S-COMP).
4. Else the contract wage (S-NONE).

**Period of a typed amount:** new `hr.formula.rule.pbpb_period` Selection `month` / `year`, no default stored; when empty,
`_pbpb_period_guess()` = `year` if the name or code contains (case-insensitive, whole token) `annual`, `yearly`,
`per year`, `ctc`, `p.a.`, or the code starts with `INANN`; else `month`. Used only for the suffix, the helper line and
the "a year" chips — **never** to scale a value. The engine always receives exactly what was typed.

**`hr.contract.wage` when the headline is not the wage (architect ruling A1):** the wage stays required by the platform
(F§A.6). Write `wage = headline` if `period == 'month'`, `headline / 12` if `year`, rounded to the currency. It is "the
agreed pay per month" for lists, bands and letters; the scheme does not read it. `_validate` then refuses an empty
headline with `Type the <headline name, lower-cased first letter>.` instead of "Type the monthly wage."

### 3.4 `pb.pay.builder` — the server facade

All three methods: `@api.model`, gate first (table §3.8), then **sudo** for scheme reads, return **plain values only**
(NH6/NH8 precedent, F§E). Never return formula text.

```python
work_out(home, ref, values, tries=None, open_codes=None) -> dict
# home: 'studio' | 'offer' | 'change' | 'joining'
# ref:  {'scheme_id', 'country', 'date_start', 'employee_id'?, 'contract_id'?, 'offer_id'?}   (what the home knows)
# values: {'wage': float|None, '<CODE>': float, ...}   typed per-person amounts (headline included)
# tries:  {'<CODE>': float}   what-if amounts for Each-month lines; never stored
# open_codes: ['<CODE>', ...] explanations to return in the same round trip
```

Returns:

```python
{'ok': True,
 'scheme': {'id', 'name'}, 'month_label': 'December 2026',
 'currency': {'symbol', 'name', 'position', 'decimals', 'step'},      # step: 1000 INR, 10000 VND/IDR, 100 else (§3.6)
 'head': {'code': 'wage'|'<CODE>', 'is_wage': bool, 'name', 'period': 'month'|'year', 'value', 'required': True},
 'asks': [{'code','name','hint','control': 'money'|'number'|'toggle'|'choice','options':[{'value','label'}],
           'value','usual','changed','period','from_offer': bool}],
 'sections': [{'key': 'earn'|'ded'|'er', 'total', 'total_name': str|False,
               'lines': [{'code','name','kind': 'set'|'calc'|'each','amount','was': float|None,
                          'usual','changed','in_bar': bool,'zero': bool,'detail': bool,
                          'source': str,'uses': ['<CODE>',...],'failed': False|'zero'|'unreadable'|'other',
                          'tried': bool,'from_offer': bool}]}],
 'totals': {'gross','deductions','net': float|None,'employer_cost','cost',
            'was': {...same keys...}|None},                              # 'was' only for home == 'change'
 'explains': {'<CODE>': {...§3.5...}},
 'state': 'ok'|'waiting'|'no_scheme',                                     # DESIGN §6
 'notes': [str], 'can_edit': bool, 'took_ms': int}
# refusal: {'ok': False, 'reason': str, 'fix': str}
```

How it works out the month (**record-free**, F§D.2):

1. `engine = _Engine(env, config)` (import from `odoo.addons.pb_formula_studio.models.take_home`; if the class or its
   methods are private in a way that makes this brittle, add a thin public seam in `pb_formula_studio` and list it in
   the report — do not copy the engine).
2. Inputs dict by code:
   - every input rule starts at `default_value` **only if** it is not a contract component; a contract component starts
     at `values[code]` if given, else — home `studio`/`offer`: `default_value` (that is what the fill will write, F§C.1);
     home `change`/`joining`: the contract's line amount, **0 when there is no line** (F§M2);
   - wage codes (`_th_wage_codes`) ← `values['wage']` (home `change`: contract wage when not typed);
   - Each-month inputs ← `tries[code]` when given;
   - period codes ← the pure helpers `pay_period.fill_period_inputs` / `default_standard_work_days` for the **full
     calendar month of `date_start`** (F§D.2). Worked-days codes: the month's standard days. No clock, no segments.
3. `results = engine.evaluate(inputs)`; build the in-memory lines **inside `hr.payslip.new(...)`** exactly as
   `take_home.py:114-124` (F§F, F§M8) and read `pb_pay_band()`, `pb_counts_in_totals()`, `pb_pay_totals()`.
4. `engine.diagnose(results)` once per call for formulas whose result is 0 or missing → `failed` (F§D.1, NH52).
   A failed line that feeds net makes `totals.net` and the totals it reaches `None`.
5. `notes`: the full-month sentence; the first-day sentence when `date_start.day != 1`; "Some values on this scheme come
   from the pay data file; the example uses the usual ones." (and the connected-system twin) when any hidden or shown
   Each-month input exists — reuse `payslip_example._notes` wording (same msgids).
6. Budget: **≤ 60 ms server time on a 400-rule scheme, warm** (assert `took_ms` in a test on the largest fixture; the
   compiled steps are memoised by `_pb_formula_steps`, F§D.1).

**The right column must agree (D6, F§M3).** The right panel keeps calling `payslip_example` (real records). Both now get
the same typed values (§4.1 extends `usual`), so on a scheme without clock/segment/mapped-field inputs they are equal.
Test T-17 asserts equality of gross, deductions and net between `work_out` and `payslip_example` on every fixture scheme.
When they still differ by more than one currency unit (client compares after both settle), the builder shows one muted
note under the foot: `The payslip example on the right also reads this person's working days and records, so it can differ slightly.`
Never hide either number; never "fix" one from the other.

### 3.5 `explain` — plain words, server-side (`formula_words.py`)

`explain(home, ref, values, tries, code)` (also batched through `open_codes`) returns:

```python
{'code','name','sentence': str,
 'parts': [{'t':'ref','code','name','amount','period'} | {'t':'fix','name','text'} | {'t':'num','text'} |
           {'t':'op','text': '×'|'÷'|'+'|'−'|'('|')'} | {'t':'word','text'}],
 'long': bool, 'uses': [{'code','name','amount'}],          # long = more than 14 parts → DESIGN §5.6
 'ladder': [{'from','to': float|None,'rate','part','amount','hit': bool}] | None,
 'result': float, 'failed': False|str, 'failed_words': str,
 'studio': {'can_open': bool, 'action': dict|False}}
```

- **Parser:** a small recursive-descent parser in pure Python over `excel_formula`, producing the same node kinds as the
  client mirror `parseFormula` (`num, str, ref, range, op, cmp, fn` — F§D.3; read `formula_flow_eval.js:178-260` as the
  reference grammar and port it; expand `BRACKET` and ranges the way `_expand_refs` does, F§D.3). Refs are column
  letters with a row number **or** bare codes; resolve through `column_letter` → rule (F§C). It must accept every name
  in `functions.FUNCTION_NAMES` (F§D.4); an unknown function → `long` fallback, never an exception.
- **Parts:** ref to an input/formula rule → `ref` with this run's amount; ref to a constant rule → `fix` (name +
  formatted value: `rate` kinds as a percentage, money with the currency); `MIN(a,b)` → `the smaller of a and b`;
  `MAX` → `the larger of`; `ROUND/ROUNDUP/ROUNDDOWN/INT/CEILING/FLOOR(x…)` → x's parts followed by word `rounded`
  (`rounded up` / `rounded down`); `SUM` over a range/list → `the total of` + refs (≤ 8) else `the total of N lines`;
  `IF(c, a, b)` → `if c then a otherwise b`, comparisons as words (`is less than`, `is at least`, `is`, `is not`);
  `ABS`, `AND`, `OR`, `NOT` as words; anything else → function name lower-cased as a `word` (still readable).
- **Sentence:** generated from the tree by pattern, every template wrapped in `_()`:
  single ref × number/constant → `%(pct)s of %(a)s.`; `a / 12` → `%(a)s spread over 12 months.`;
  subtraction chain → `%(a)s less %(rest)s.`; SUM → `The total of %(n)s lines.` / `%(a)s plus %(b)s.`;
  MIN/MAX cap → `%(x)s of %(a)s, counted up to %(cap)s.`; IF → `Depends on %(names)s.`; BRACKET → `Climbs in steps: the
  more %(a)s, the higher the rate.`; fallback → `Worked out from %(names)s.` Prefer an honest generic sentence over a
  clever wrong one. If the rule carries a non-empty human description field (check the model; F§C lists none — if none
  exists do not add one), nothing changes.
- **Ladder:** only when the top-level function is `BRACKET` (read its table semantics in `formula_engine/functions.py`):
  rows from the table, `hit` and `part` computed for this run's base amount.
- **Studio link:** `can_open` = caller in `pb_hr_payroll_formula.group_formula_user` (F§E); `action` = the Formula Studio
  client action opened on this scheme and component (find the existing deep-link precedent in `pb_formula_studio`; if
  none exists, open the scheme and report it).
- Three languages: every word above is a translatable msgid (en source, vi_VN, id_ID). No hard-coded English (the old
  `_explain` is not used, F§E).

### 3.6 `work_back` — take-home → headline

`work_back(home, ref, values, tries, target)` → `{'ok': True, 'head_value', 'net', 'evals'}` or a DESIGN §7 refusal.
Wrap `take_home_solver.solve(net_of, target, decimals, max_evals)` (F§D.2; read the module for its contract and its
exceptions `_OutOfTries`, `_NotANumber`): `net_of(x)` = `work_out` core with the headline set to `x` and everything else
as typed. Then round **up** to `currency.step` and re-evaluate so the returned `net` is the true one. `step`:
`1000` for INR yearly headlines, `10000` for zero-decimal currencies (VND, IDR, KHR), `100` otherwise, `1` when the
headline is monthly and the currency has decimals… keep it in ONE helper `_pbpb_step(currency, period)` with a test.
Gate: same as `work_out` for that home (the Studio's payroll-user gate does not apply — we are behind our own gate, sudo).

### 3.7 The OWL block `PayBuilder`

Props: `{ home, ref, values, tries?, readonly?, variant: 'full'|'slim', onChange(values, answer), strings? }`.
The **host owns the values** (in step 3 they live in the studio draft so Back/Next, "Skip to the end", the proposal and
the right panel all see them); the block owns only view state (open rows, shown zero lines, added-from-bar set, work-back
strip, what-if amounts).

- One request in flight, latest-wins token, change-during-flight re-sent, 250 ms debounce while typing, quiet retry —
  clone the pattern of `runExample` (`new_hire_studio.js:492-534`, F§A.4). Never disable or re-create an input while the
  user types (WS18: never NaN or "" into reactive state; `parseMoney`/`groupTyped`/`moneyNumber` from `studio_util.js`).
- Numbers tween client-side (DESIGN §10); the foot's live region announces once per settled answer.
- Icons through `icon()` (F§K; `calculator`, `pencil`, `calendar`, `lock`, `target`, `sparkles`, `info`, `plus`,
  `chevronDown`, `undo` exist in the kit). Markup cached — never a new `markup()` per render (OWL flicker gotcha).
- No JS globals in templates (NH11); child reads its own `useState` (NH27); `_t` literal first argument, exact import
  (WS39/WS40); money through the kit's formatters, never `toLocaleString` (WS42).
- SCSS: `pbpb-` prefix, declares the tokens it uses with the studio's fallbacks so it renders the same outside `.pbnh`;
  no Sass `min()/max()` (WS11); breakpoints 620 px (block) in addition to the studio's own.
- Keyboard and aria per DESIGN §11.
- Variants `compare` and `read` are props of the same component (`was` column / no inputs), not copies.

### 3.8 Who may use it (decide per home — F§M7; do not widen who sees pay)

| Home | Gate (server, before any sudo) | Why |
|---|---|---|
| `studio` | `pb.new.hire._gate()` (`require_hr`) | same people who see the payslip example today |
| `offer` | `pb.pay.package._offer_get` rules: recruiter + hiring reader, offer in draft and money not locked | same as "Build from a total" |
| `change` | contract panel write right (`_cd_may_write`) **and** `pb_job_change._may_see_pay` | take-home and every line are pay data |
| `joining` | the joining session (token + code) and `pb.pay.settings.portal_enabled` | the person, their own pay only |
| Formula Studio link | `group_formula_user` | F§E |

A refused caller gets `{'ok': False, 'reason': "You can look at this person but not at their pay.", 'fix': "Ask a payroll manager."}`
(or the home's existing wording). Unit-test every row of this table, both directions.

## 4. Home by home

### 4.1 P1 — Add employee step 3 (`pb_new_hire`, +dep `pb_pay_builder`)

Template (`new_hire_studio.xml`, `pb_new_hire.StepPay`, F§A.1): keep **Paid by** (501-520) and the **contract card**
(553-595) untouched. Replace the **Monthly wage** card (522-551) and the **usual answers** card (597-624) by one
`<PayBuilder home="'studio'" …/>` placed between Paid by and the contract card. The pay-scale lines, the off-scale pin
and the pay band (531-550) move **inside Card A under the helper line** through a named slot of the block
(`t-slot="under-head"`) and render only when `head.is_wage`. Keep `id="pbnh-f-wage"` on the headline input when
`is_wage` (lessons anchor `rep-newemp-wage`, F§L) and keep `data-coach="nh-step-pay"`; add `data-coach="nh-pay-builder"`
on the block.

Draft and state (`new_hire_studio.js`, F§A.3):
- **No new sent key.** Typed per-person amounts stay in `draft.usual` (`{code: amount}`); the headline of an S-COMP scheme
  is `draft.usual[head.code]`; `draft.wage` stays the wage for S-WAGE/S-BOTH/S-NONE and is **derived** for S-COMP (§3.3 A1)
  on the server in `_values`, not typed.
- `setUsual` (1190-1202) today accepts only codes in `nh.usual.rows` and deletes a value equal to the usual. Replace the
  source of accepted codes with the builder answer's `head`/`asks`/`set` lines; keep "equal to usual deletes the key".
- What-if amounts: `nh.tries` (view state on the root so they survive Back/Next); **not** in `DRAFT_KEYS`, not sent.
- `payReady` (1268-1273): headline > 0 (or pay-scale amount found, as today) and a valid end date. Rail text (1294-1301):
  `Take-home %s a month` when the builder answered with a net; `%s a month` (today's) when there is no net;
  `Pay needed` when empty — **but** keep the literal "Wage needed" if a lesson replica asserts it (check F§L; update the
  replica instead where you can).
- `EXAMPLE_INPUTS` already contains `usual` (F§A.4) — the right panel follows by itself. Do not touch `RecordPanel`.
- Scheme change (`loadUsual` 1014-1034): a different scheme clears `draft.usual` and `nh.tries` (already does the first).
- `usual_answers` RPC stays for callers that still use it; step 3 no longer calls it.

Server (`pb_new_hire/models/studio.py`, `create_ext.py`):
- New `hr.formula.config._pbpb_person_rules()` (in `pb_pay_builder`): **all** numeric-fill-kind contract components with a
  code, zero default included (F§M1). `_pb_usual_answer_rules()` is untouched (N4).
- `_usual_choices` (831-852): accept codes from `_pbpb_person_rules()`; keep "only values that differ from the usual" —
  for a zero-default rule that means any non-zero amount. **NH12:** an explicit 0 against a non-zero usual must survive
  (`0 in (None, '', False)` is True in Python — compare with `is None`).
- `_pb_nh_lines` (`create_ext.py:232-270`): same accepted set; everything else as today (sudo create, trail with
  `effective_date=contract.date_start`, then `_pb_fill_in_defaults()`; order F§C.1). Lines honour the template bounds —
  catch `_check_bound_limits` and refuse in words at **validation** time (`_validate`), not at approval:
  `<name> must be between <low> and <high>.`
- `_validate` (803-808) and the example's refusal (`payslip_example.py:156-158`): headline rule of §3.3.
- `_values` (884): derived wage for S-COMP. Proposal rows (`create_ext.py:378-384`): label the headline by its own name;
  list every typed line (already loops `usual`).
- `payslip_example`: no change beyond what flows from `_usual_choices` (its preview create uses the same `_values`).
  Extend `_example_key` only if you add a draft key (you should not).

### 4.2 P2 — Formula Studio (`pb_formula_studio`; fields from `pb_pay_builder`)

DESIGN §9. In the component editor INPUT body (`studio.xml:1351-1381`, F§G), directly above "Usual answer for a new
contract", add the two-way choice bound to `is_contract_component`; remove the old tick box from the "Advanced" section
(1525) but leave "Requires new contract" where it is. **New msgids** — do not reuse "Contract component", which the
source chip shares (F§M13). Formula and constant components show the grey line instead.

- **Live-scheme warning (F§M2 — the dangerous part).** New RPC `pb.pay.builder.switch_preview(rule_id, to_per_person)`:
  when turning **on**, count the running contracts this scheme pays (resolver: `pb.scheme.map`, the same one the pay run
  uses) that have **no** line for the component → inline amber panel before save:
  `From now on Payobook reads this amount from each person's contract. <N> people paid by this scheme have no amount there yet, so they get 0 for this line until someone types one.`
  with `Show who` (first 20 names, HR-readable) and buttons `Switch anyway` / `Keep as it is`. When turning **off**:
  `<N> people have this amount on their contract. It stays there but pay stops reading it; the amount will come from <source> each month.`
  N = 0 → no panel. The save itself stays `save_component` (allow-list already has the field).
- Add to the same body, for contract-component money inputs: `Typed per` segmented `Month | Year` (`pbpb_period`, shows
  the guess when unset). Add to the scheme's settings surface (find where scheme-level options are edited in the Studio;
  if there is none, put it in the component editor as a tick `This is the main pay amount for the scheme`, one per
  scheme): `pbpb_main_rule_id`. Add both fields to `_EDIT_FIELDS` by extension (precedent `studio_fillin.py:23-26`).
- A formula-manager-only surface; no approval is added (none exists for this field, F§G). Say so in the report's open
  questions (the owner may want one).

### 4.3 P3 — Hiring offer (`pb_pay_package`, +dep `pb_pay_builder`)

- Door: in the offer editor beside "Build from a total" (`offer_total.xml:9-22`, same visibility conditions) add
  **`Pay Builder`** as the solid door; "Build from a total" becomes an outline button (N10). It opens a dialog with the
  block `home="'offer'" variant="'slim'"`, scheme from `_offer_schemes` (chooser when several, as the card does),
  refusal when offer money ≠ scheme money (reuse the sentence at `offer_total.py:283-290`).
- Primary `Use these lines` → write the offer's monthly lines from the answer's **earnings** lines > 0 (kind `earning`,
  `pb_item_code` = code, `pb_from_total = True`, wage line tagged `pb_item_wage`; replace earlier builder/total lines —
  clone `offer_use`, `offer_total.py:353-366`) and store on the offer: `pb_total_config_id` (exists) and new
  `pbpb_values` (JSON text: `{code: amount, 'wage': …}`), `pbpb_net`, `pbpb_gross` (floats, same `groups` as the offer
  totals, F§H privacy).
- Letter: new Boolean `pbpb_letter_table` (default True) — DESIGN §8 toggle in the same dialog and in the offer editor
  next to the letter buttons. Off → `_lines_table()` (`offer.py:407-429`) returns the single gross sentence; on → today's
  table plus the take-home sentence `Take-home after the usual deductions is about %s a month.` when `pbpb_net` is set.
  Keep the doc-studio override working (`pb_doc_studio_hiring/models/offer.py:166-209`).
- Into Add employee: extend `offer_draft` (`pb_new_hire/models/hiring.py:268-313`) and Joining's `joining_draft`
  (`pb_joining/models/studio.py:93-120`) through a hook so that, when the offer has `pbpb_values` **and** its scheme is
  the one the studio resolves for the hire (or is offered by `_scheme_options`), the draft gets `scheme_id` and `usual`
  (and `wage`), flagged so the block shows `From the signed offer`. Different currency or scheme not available → today's
  behaviour and today's note. `pb_new_hire` must not depend on `pb_pay_package`: the hook is defined in `pb_pay_builder`
  (`_pbpb_offer_values(offer)` returning `{}` by default) and overridden in `pb_pay_package`.
- F§H "NOT VERIFIED": whether `pb_pay_package._pbpk_contract_lines` still runs for a studio hire. Find out (a test), and
  make sure the contract does not get **two** sets of lines for the same code; the studio's lines win. Report what you found.

### 4.4 P4a — Contract panel "Change pay" (new bridge code in `pb_pay_builder`, or a bridge module)

- Door: a third registry entry beside `pb_take_home` / `pb_build_total` (F§I): add the lookup of
  `registry.category("pb_contracts_drawer_doors")`-style key **`pb_change_pay`** in `contract_360.js` next to the two
  existing lookups and a `Change pay` outline button in the pay section of the Terms tab and the header of the Components
  tab, shown only when the server payload says the caller passes the `change` gate (§3.8). `pb_contracts` gets JS/XML
  only (N6); bump its version.
- The dialog: `New pay starts from` (date, default = first day of next month in company time — use the `pb_records`
  "today" helper Change job uses) + `Reason` + the block `home="'change'" variant="'slim'" compare`. Baseline = the
  contract's wage and lines as they are (missing line = 0, F§M2); editable = the same You-set set.
- Send: **through Change job's pay change** — `pb_start_for_employee` with `START_KEYS` `wage`, `lines`,
  `effective_date`, reason kind `pay` (F§I; `pb_job_change/models/job_change.py`), so the dated write, the trail
  (`Change.log(..., effective_date=…)`), the approval process `jobchange` and the future-dated cron are the existing ones.
  Do not write contract lines yourself and do not use `save_contract_360` for this (it is undated, F§I).
- Dependency: `pb_pay_builder` may depend on `pb_job_change` **only if** that creates no cycle and does not drag modules
  into installs that lack them; otherwise ship the door as a tiny bridge module `pb_pay_builder_change`
  (`depends: pb_pay_builder, pb_job_change, pb_contracts`, auto_install True). Decide from the manifests; report which.
- Found in the study, **not ours, report only:** `contract_approval.py:113` slices a dict (F§I). If the fix is ≤ 10
  lines and has a test, you may fix it in its own commit; otherwise list it.

### 4.5 P4b — Joining page "Your pay" (`pb_joining`, +dep `pb_pay_builder`)

- Public QWeb, no OWL (F§J). An `<article class="pbjp-card">` on the **hub** above the section list, also on `day_one`.
  It is **not** a section: never a key of `_section_states`, never part of progress or "Send to HR".
- Source, first that exists: the person's running or approved-to-start contract (`joining.employee_id`) → `work_out`
  with home `joining` from the contract's wage and lines; else the offer's `pbpb_values`; else **no card**.
- Shown only when `pb.pay.settings.portal_enabled` is on for the company (F§J) and the scheme has at least one shown line.
- Markup: earnings and deductions rows, take-home, the note; Worked-out rows are `<details><summary>` with the sentence
  and the chips as plain spans (no buttons, no Studio link, no company section, no cost). Values arrive as plain strings
  from Python (RC49), icons through `pb_joining.icon`, `[hidden]` rule (RC72), strings in en/vi/id.
- Security: nothing but this person's own figures; no employee id, scheme id or code in the HTML; same no-store headers.

## 5. Phases — commit and test at the end of each; one feature = one commit, pushed

| Phase | Commit title | Tests that must pass | Walks |
|---|---|---|---|
| P1 | `PAYBUILDER P1: Pay Builder in Add employee step 3` | T-1…T-34 | W1, W2, W6 |
| P2 | `PAYBUILDER P2: Formula Studio per-person switch` | T-35…T-42 | W3 |
| P3 | `PAYBUILDER P3: Pay Builder on the offer` | T-43…T-50 | W4 |
| P4 | `PAYBUILDER P4: Change pay + Your pay on the joining page` | T-51…T-62 | W5, W7 |
| P5 | `PAYBUILDER P5: lessons + release` | full suites, static gates | W8 |

Each phase ends with: numbered tests + full suites of every touched module (baseline failures only), the walks, explicit
file staging, push of `paybuilder`. Append every new gotcha to the ledger §4.

## 6. Lessons and words (P5 — a screen change updates its lessons, standing rule)

F§L is the list. Update: `learn_content.json` scenario `sc_people` step `wage` and its title (the box may no longer be
"Monthly wage" on every scheme — the lesson fixture is a wage scheme, so keep "Monthly wage" there and add one sentence
about the month working itself out); practice screen `newEmployeeHTML` (`screens.js:355-437`) to show a Pay Builder card
in place of the wage box and usual answers (keep `rep-newemp-wage`); `anchors.json` text of `nh-step-pay`; add reserved
anchor `nh-pay-builder`; L29/L33 one sentence on "Change pay". Learn is en + vi only (NH70).
Product `.po`: every new msgid in `vi_VN.po` and `id_ID.po` of each touched module, three markers per entry (F§K);
"The scheme's usual answers" and other removed strings leave the `.pot`.

## 7. Test cases (real tests; tag `paybuilder`; `TransactionCase` unless stated)

### 7.0 Fixtures (in `pb_pay_builder/tests/common.py`, reuse `NewHireCommon` where it helps)

Demo naming rule: names start with `DEMO`, never a client name. Active schemes, own company, with pay roles set:
- **FX-WAGE** (VND): input `BASIC` (wage), You-set `LUNCH` (default 730000), `PHONE` (0), contract-component count `DEP`
  (0, kind integer), yes/no `INS` (1, `value_labels` "0=No;1=Yes"), Each-month `OT` (0, excel source), constants for the
  rates and ceilings, formulas for insurance ×3, a `BRACKET` tax, net, three employer-cost lines.
- **FX-COMP** (INR): the Rize India shape from F§B.3 — `INANNFIX` (contract component, 0), `INANNVAR`, constants,
  `ROUND({INANNFIX}*rate,0)` chain, total-line earnings (`INGROSS` counting, others detail), Each-month `INPT`, `PIT`,
  net, employer PF.
- **FX-NONE**: every input from the file. **FX-NONET**: no net line. **FX-BIG**: 400 generated rules.
- **FX-BROKEN**: one formula dividing by a zero-valued input.

### 7.1 P1 — engine and step 3

1. `_pbpb_layout` FX-WAGE: kinds, sections and order exactly as the classification table.
2. `_pbpb_layout` FX-COMP: headline = `INANNFIX`, `is_wage` False, period `year` (guess); total-line rule applied.
3. Headline precedence: `pbpb_main_rule_id` beats the wage; wage beats lowest-sequence component; S-NONE falls to wage.
4. `_pbpb_period_guess`: table of names/codes → month/year; stored `pbpb_period` wins.
5. Layout cache invalidates when a rule's `is_contract_component`, `default_value` or formula changes in the same transaction.
6. `work_out` FX-WAGE with wage 30,000,000: hand-computed gross, each insurance, tax, net, employer cost.
7. `work_out` FX-COMP with `INANNFIX` 1,200,000: hand-computed Basic, HRA, conveyance, PF, gross, net.
8. Empty headline → `state: 'waiting'`, no lines, totals None.
9. No scheme → `state: 'no_scheme'` with the fix sentence.
10. You-set line typed → dependants move; `changed` True; equal to usual → `changed` False.
11. Zero-default You-set line untouched → `in_bar` True; typed non-zero → a row.
12. Each-month line: usual value; with `tries` → `tried` True and totals move; nothing is written anywhere.
13. Yes/no ask off → the lines that read it become 0.
14. Count ask (dependants) lowers tax by the relief.
15. FX-BROKEN: line `failed: 'zero'`, net None, other sections still totalled; no exception.
16. FX-NONET: `totals.net` None, note present.
17. **Agreement:** for FX-WAGE, FX-COMP, FX-NONE: `work_out` gross/deductions/net == `payslip_example` for the same draft.
18. FX-BIG warm `took_ms` ≤ 60 (skip-if-slow-machine guard allowed; record the number in the report).
19. `work_out` performs **zero writes** (assert no `INSERT/UPDATE` via a query counter or `flush` + compare `write_date`s) and creates no employee/contract.
20. Totals come from `pb_pay_totals()` on lines inside `hr.payslip.new` (assert a signed-deduction refund fixture totals right).
21. `explain` simple product: parts `[ref, op ×, fix, op ÷, num]`, sentence template, result.
22. `explain` MIN cap → words "the smaller of … and …"; ROUND → "rounded".
23. `explain` SUM range of 14 → `long` True, `uses` has 14.
24. `explain` IF with a text comparison parses; sentence is the "Depends on" form.
25. `explain` BRACKET → ladder rows, `hit` on the right steps, sums to the tax.
26. Parser battery: every name in `FUNCTION_NAMES` parses without exception (one tiny formula each); garbage → fallback.
27. `explain` never returns formula text or column letters (assert on the serialised answer).
28. `explain` strings come back in Vietnamese and Indonesian under `with_context(lang=…)` (NH64).
29. `work_back` FX-WAGE: returned headline is a multiple of the step, its net ≥ target, and headline − step gives net < target.
30. `work_back` refusals: no net line; target 0; unreachable target; out of tries.
31. Gate `studio`: HR officer allowed; a plain employee refused in words; a user from another company cannot name that company's scheme.
32. Hire on FX-COMP through `send` + approval: contract has an `INANNFIX` line = typed, trail row dated the first day, `wage` = typed/12; a draft payslip through the **real** `_get_formula_input_values` gives the same net as `work_out`.
33. Hire on FX-WAGE: typed `PHONE` 500000 → line; untouched `LUNCH` → filled by the automatic fill with the `pb_fill` mark; explicit 0 on `LUNCH` → a line of 0 (NH12).
34. Out-of-bounds amount (template with bounds) → refused at `_validate` with the between sentence; nothing created.
   Static: `pb_pay_builder/tests/test_static.py` cloned from `pb_new_hire` (S1 vendor name, S2 icons, S3 emoji, S4 `_t`, S6 pot).

### 7.2 P2 — Formula Studio

35. `switch_preview` on: counts only running contracts paid by this scheme without a line; names limited to 20.
36. `switch_preview` off: counts contracts with a line.
37. N = 0 → no warning payload.
38. Saving the switch through `save_component` flips `is_contract_component`; the layout moves the line from Each month to You set.
39. `pbpb_period` and `pbpb_main_rule_id` save through the editor allow-list; a second main rule replaces the first.
40. Formula and constant components do not accept the switch (refused in words).
41. Only a formula manager may call `switch_preview`/save; a formula user is refused.
42. New msgids exist in pot + vi + id; the old "Contract component" msgid is still present for the source chip.

### 7.3 P3 — offer

43. Gate `offer`: recruiter + hiring reader allowed; hiring user without reader refused with the existing sentence; locked money refused.
44. `Use these lines` writes one monthly earning line per shown earning > 0, tags the wage line, replaces a previous set, stores `pbpb_values`/net/gross.
45. Offer currency ≠ scheme currency → refused with the existing sentence.
46. Letter table on → table + take-home sentence; off → the gross sentence only; doc-studio letter still renders.
47. `offer_draft` with matching scheme: draft carries `scheme_id`, `usual`, `wage`, `from_offer` flags.
48. `offer_draft` with a scheme the studio would not offer, or another currency: today's draft and note, no `usual`.
49. Joining's `joining_draft` carries the same values (HR without Hiring rights, J-25).
50. Studio hire from an offer with lines: exactly one contract line per code (the "NOT VERIFIED" of F§H resolved by test).

### 7.4 P4 — change pay and joining

51. Gate `change`: contract manager who may see pay allowed; contract manager who may not see pay refused; reader refused.
52. Baseline uses contract lines; a missing line is 0 even when the rule's default is non-zero (F§M2).
53. `was` values and `totals.was` present only for changed lines; deltas right.
54. Send creates a Change job pay change with the date, wage and lines; nothing is written to the contract before approval / start date.
55. Future date → `scheduled`; the cron applies it on the day; trail rows carry the effective date.
56. No approval route → applied per Change job's own rule; the dialog's button reads `Save`.
57. `pb_contracts` still installs and its suite passes with `pb_pay_builder` uninstalled (door absent, no error) — N6.
58. (`HttpCase`) joining hub shows `Your pay` for a hiring-origin joiner whose hire is approved; figures equal `work_out`.
59. Invited joiner with no contract and no offer values → no card; hub progress unchanged with and without the card.
60. `portal_enabled` off → no card.
61. The page HTML holds no scheme id, code, formula text or other person's data; headers unchanged.
62. Card strings in vi and id.

## 8. Browser walks (mandatory; console open; screenshots to `docs/handovers/paybuilder/shots/`)

- **W1** 1440: Add employee step 3 on FX-WAGE — type, tween, flash, hover highlight, open three explainers, click a chip,
  add from the bar, Back to usual, Try an amount, Work back, empty the headline, Back/Next keeps values, step 7 summary
  and the proposal list the typed lines, right column unchanged and equal. Compare side by side with the clickable design.
- **W2** same on FX-COMP (yearly headline) and FX-NONET, FX-BROKEN, no-scheme, read-only viewer.
- **W3** Formula Studio: flip a component both ways on an active scheme, see the warning counts, Show who, Keep as it is.
- **W4** Offer: Pay Builder door → Use these lines → letter with and without the table → candidate page → accept →
  Add employee shows `From the signed offer`.
- **W5** Contract panel: Change pay, future date, before/after, Send → Approvals → approve → on the date the contract and
  trail change; a user who may not see pay has no button.
- **W6** widths 1180 / 820 / 600 / 400 for step 3; keyboard-only pass; reduced-motion pass; Vietnamese and Indonesian.
- **W7** phone 360×740: joining hub `Your pay`, open a line, vi and id.
- **W8** after release, on payobook: W1 short form with a `DEMO`-prefixed person.

Score the result against DESIGN §1 "the bar" in the report, honestly, line by line.

## 9. Release (the owner decided you also release)

Databases: **payobook, payobook_template, p0clone, rize, sudima** — these five, never `abm`. One addons directory
(`CLAUDE.md`, "Deploy contract").

1. Merge `paybuilder` into `19.1` (no rewrite), push.
2. `ssh Payobook19v2 'tail -40 /opt/deploy-notes.md'` — a `HOLD`, or a `START` without `DONE`, means stop and tell the owner.
3. Tier **risky** (new module, changes what a hire writes to a contract; last night's backup, no fresh dump):
   `WHO="Codex PAYBUILDER" tools/release.sh risky <all touched modules + pb_pay_builder> +pb_pay_builder,<touched…>`
   If a bridge module exists, add it with `+`. Not `OK` → stop and report the log.
4. Only when nobody has been active on rize, payobook or sudima for 15 minutes.
5. Verify + NOTE line: trees identical to the commit; manifest = installed version ×5; cron counts unchanged; zero
   ERROR/Traceback since start; five sites answer 200; **no scheme changed** on any database
   (`select count(*), sum(is_contract_component::int) from hr_formula_rule` identical before/after per DB — N8).
6. Live proof on **payobook only** (W8). On rize: open Add employee to step 3 for an India hire with a `DEMO` name and
   confirm the headline reads the scheme's yearly amount and the month works out — then **leave without sending**.
   Create nothing on rize or sudima.
7. A live sign-in is the owner's to do; never store a password.

## 10. Report back — `docs/handovers/paybuilder/PAYBUILDER_REPORT.md`

1. What was built per phase, commit hashes, module versions before/after.
2. Test counts per module before/after; named baseline failures; T-18's measured time.
3. Every deviation from DESIGN or this handover, and why.
4. Each "NOT VERIFIED" in the facts that you resolved, with the answer.
5. Walk results with screenshot paths; the self-score against the bar.
6. Release result (log tail, NOTE line, the N8 check numbers).
7. New ledger entries.
8. Open questions for the owner **in plain non-technical English** — at least: A1 (what the contract's monthly wage shows
   on yearly-package schemes), whether flipping the per-person switch on a live scheme should need approval, whether
   "Build from a total" should be retired now that the Pay Builder is on the offer.
