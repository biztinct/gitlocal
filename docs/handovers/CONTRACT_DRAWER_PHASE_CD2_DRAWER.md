# CD-2 — The contract drawer: the screen, read-only

**Programme:** CONTRACT DRAWER (CD). Phase CD-1 (commit `fd51bed3`) built the
server. This phase builds the screen that reads it. CD-3 makes it write.

**Why read-only first:** the owner chose "read beautifully, edit in place". The
reading half is where the design lives, and it is worth landing and looking at
before a single input box exists. CD-3 turns the same cells into editors.

Implemented by an Opus build agent. Fable designed this and will not re-review
the code — run the numbered test cases, do the Chrome validation, and report.

---

## 0. Standing rules that bind this phase

**WHITE-LABEL (hard rule).** "Odoo" and Odoo branding must never appear in
anything a user can see — labels, chips, tooltips, empty states, buttons,
notifications, `.po` msgstr. Use "Payobook" or a neutral term. The escape-hatch
button that opens the built-in form is called **"Full form"**, never "Odoo
form". **Never rewrite technical identifiers** (imports, model/XML ids, addon
names, log messages, comments, docs).

**PLAIN ENGLISH on every pixel.** Screen words only: "pay run", "pay data
file", "the connected system", "the contract", "components". Never a field's
technical name, never an internal ticket code.

**DESIGN BAR (binding, owner re-mandated 2026-08-29):** extreme WOW, intuitive,
out-of-this-world, best in class. Hero moment, zero dead-ends, plain language,
purposeful motion, bulk ergonomics. **Lucide icons, never emoji, never
FontAwesome.** Chrome-MCP validation on the live site is mandatory before
reporting done.

**DEPLOY CONTRACT** — `CLAUDE.md`. One addons directory. Clean staging dir.
Per-module `--delete`, **never** at the addons root. Upgrade all four
databases. **After any JS/SCSS change:**
`DELETE FROM ir_attachment WHERE name LIKE '%.assets_%' OR url LIKE '/web/assets/%';`
per database, then restart. (W10.)

**LEDGER:** `docs/WORKFORCE_REDESIGN_CONVENTIONS.md`. CD-1 appended CD1–CD4;
append CD5+ for anything new.

---

## 1. What CD-1 already gives you — DO NOT RE-DERIVE

Read `docs/handovers/CONTRACT_DRAWER_PHASE_CD1_SERVER.md` §2.1 for the full
payload contract, and the code in `pb_contracts/models/pb_contract_360.py`
(`_inherit = 'pb.contracts'`).

`get_contract_360(contract_id)` — one call, everything the drawer needs:

- top level: `ok, error, currency, can_write, unmask_wage, header, terms,
  readiness, components, history`
- `header`: `contract_id, reference, employee, employee_id, initials, avatar,
  job, dept, state, state_label, wage, wage_masked, ends_label, ends_tone,
  pipeline, next_actions`
- `terms`: ordered groups `money` (6 fields) / `dates` (4) / `place` (5) /
  `rules` (5) = 20. Each field: `name, label, kind, value, display, required,
  writable, hint, tone` (+ `options` for select/toggle, `comodel` and
  `value_label` for m2o). `kind` ∈ `money|number|integer|text|date|select|
  toggle|m2o|readonly`.
- `readiness`: four chips — salary structure, working schedule, tax number,
  employee category — each `{key, label, ok}`
- `components`: `{rows, count, total, addable}`; a row carries `id, code, name,
  value_type, amount, text_value, display, lower, upper, bounded, bounds_hint,
  value_kind, requires_new_contract, template_id, writable`
- `history`: `{rows, total, shown}`; a row carries `kind` (`component|field|
  retro`), `when`, `when_label`, `title`, `from`, `to`, `source`, `actor`,
  `tone`

Also available: `lookup_contract_m2o(comodel, term, limit)` (whitelisted
comodels only) — CD-3 uses it, not this phase.

**Measured on abm, contract 1051 (THANH HUYNH):** 21 component rows, **0
addable**, 1 history row, `components.total = 0.0`. Contract 1103 has 9 history
rows across two kinds.

---

## 2. THE FINDING THAT SHAPES THIS SCREEN — read before designing anything

CD-1 reported (ledger CD1):

> `hr.contract.create` (`om_hr_payroll/models/hr_contract.py:118`) auto-creates
> one advantage line per **existing** template, so a live contract already
> carries every template. abm 1051 has 21 lines and nothing to add.
> `components.total` is `0.0` because **every stored component amount on abm is
> genuinely zero — abm's numbers come per pay run, not from the contract.**

So a naive Components tab on the live tenant is **21 rows of ₫0 and an empty
"Add" button**. That reads as a broken screen, and it is not broken: those
components are simply filled from somewhere else.

**The fix is to say so.** Each component row must state where its value
actually comes from for this scheme. That information already exists and is
computed elsewhere — this phase surfaces it.

### 2.1 Server addition (the only server work in this phase)

Add to each row of `components.rows` in `get_contract_360`:

```python
'fills_from': 'records' | 'api' | 'excel' | 'rule' | 'none',
'fills_label': 'Held on this contract'
             | 'From the connected system'
             | 'From a pay data file'
             | 'Worked out by a formula'
             | 'Not fed by anything',
'fills_tone':  'indigo' | 'cyan' | 'green' | 'slate' | 'muted',
```

How to derive it, using machinery that already exists:

1. Find the scheme: `hr.formula.config` whose `connector_id`/company matches,
   or — better — the scheme that owns the `hr.formula.rule` with this
   component's `code`. The advantage↔rule join is **by string code**
   (`advantage_template_code` ↔ `hr.formula.rule.code`), the same join
   `_get_or_create_advantage_template` uses
   (`pb_hr_payroll_formula/models/payroll_import_batch.py:4957-4982`).
2. With the rule in hand, ask it what feeds it. **Do not re-derive the ladder.**
   The single accessor every consumer reads is
   `hr.formula.rule._config_kind_rank()`
   (`pb_hr_payroll_formula/models/formula_rule.py`), and the declared sources
   are `rule.declared_sources()` — a list of `{kind, key, …}` where `kind` ∈
   `feed | rule | excel | employee_field | contract_field | bank_account |
   contract_component`. That method **already filters by the scheme's enabled
   lanes and orders by the scheme's configured priority** (SOURCECTL SC-3,
   2026-08-31). The FIRST entry is the winner.
3. Map the winning kind → the three fields above:
   `feed` → api; `excel` → excel; `rule` → rule;
   `employee_field`/`contract_field`/`bank_account`/`contract_component`
   → records. No declared source at all → `none`.
4. There is a second thing worth showing and it is cheap: a **live wire** on the
   Mapping board (`hr.integration.field.mapping` with
   `target_rule_id = rule.id` and `active_state = 'active'`) means the
   connected system feeds it even when `declared_sources()` excludes live wires
   (it deliberately does — see the docstring). If a live wire exists and the
   api lane is enabled for the scheme, prefer `api`.
5. **Guard everything.** `pb_contracts` does not depend on
   `pb_hr_payroll_formula` and must keep installing without it. Use
   `self.env.get('hr.formula.rule')` and `'x' in Model._fields` guards exactly
   as CD-1 did (its rails 7 and 8). No rule, no scheme, no formula module →
   `fills_from = 'none'` and the row still renders.
6. Compute it **once for the whole set**, not per row — one search over the
   rules by code, one over the mappings. 21 rows must not cost 42 queries.

### 2.2 What the tab says when everything is zero

When `components.count > 0` and `components.total == 0` and every row has a
non-`records` `fills_from`, the tab shows a calm explanatory line above the
grid — not an error, not an empty state:

> "Nothing is stored on the contract itself. Every component below is filled
> when a pay run reads the connected system."

Adjust the last clause to name whichever source actually dominates. Compose the
sentence **server-side** as `components.explainer` (a string or `False`) so
there is one author of it.

### 2.3 The Add button

`addable` is empty on every real contract. Therefore: **render the "Add a
component" control only when `addable.length > 0`.** No disabled button, no
empty picker, no dead end. (Design bar: zero dead-ends.)

---

## 3. The screen to build

### 3.1 The thing you are mirroring

The employee slide-over is **`Employee360Drawer`**:
- `pb_employee_vault/static/src/js/employee_360.js`
- `pb_employee_vault/static/src/xml/employee_360.xml`
- `pb_employee_vault/static/src/scss/employee_vault.scss`

**Read all three before writing a line.** Mirror its structure, its motion and
its restraint. Do not copy its file — write a contract-shaped one.

Facts you will need (verified 2026-08-31):

| Thing | Employee drawer | file:line |
|---|---|---|
| root | `<div class="pev pbim">` | xml:5 |
| scrim | `.pev-scrim(.shown)`, fixed inset 0, z 1040, `rgba(16,12,40,.34)`, `.18s` | scss:26-32 |
| panel | `aside.pev-drawer(.shown)`, fixed right, z 1041, **580px / max-width 96vw**, `translateX(102%) → 0`, `.22s cubic-bezier(.22,.61,.36,1)` | scss:35-45 |
| open | `onMounted(() => this.state.shown = true)` — one frame after mount | js:38 |
| close | `state.shown = false; setTimeout(onClose, 180)` | js:65-69 |
| escape | `useExternalListener(window,"keydown",…,{capture:true})` → `Escape` closes | js:40, js:63 |
| props | **typed**: `{ empId: {type:[Number,String]}, onClose: {type:Function, optional:true} }` | js:24-27 |
| fetch | one `orm.call(MODEL, "get_employee_360", [id])`, error → `d.error` | js:51-59 |
| tabs | pure state `state.tab`, all panes in one template behind `t-if` | js:62 |
| head | `.pev-head` > `.pev-head-id`(`.pev-ava` + `.pev-head-tx`(h2 + `.pev-chips`)) + `.pev-head-side`(`.pev-tenure` + `button.pev-x`) | xml:21-43 |
| rail | `.pev-rail` > `.pev-rail-step(.done)(.current)` > `span.dot` + `span.lbl`; connector is `&:not(:last-child)::after`, not a DOM node | xml:65-71, scss:125-137 |
| grid | `.pev-grid` 2-col, `.pev-cell` > `span.k`(icon + label) + `span.v` | xml:74-106, scss:140-147 |
| chips row | `.pev-stats` > `.pev-stat(.ok|.off)` | xml:110-114, scss:148-154 |
| em-dash | `|| '—'` **inline in the template**, never in JS | xml:79-102 |
| body | `.pev-body` `flex:1; overflow-y:auto` — the drawer is a flex column and only the body scrolls | scss:122 |
| mutate | every mutation re-assigns the WHOLE payload from the server response, never patches locally | js:123,151,159 |

### 3.2 How it is opened — clone this exactly

`pb_people/static/src/js/people.js`:

```js
// :37   state flag
drawerEmpId: null,

// :53-60   soft registry probe
get drawerCmp() {
    const r = registry.category("pb_people_drawer");
    return r.contains("employee_360") ? r.get("employee_360") : null;
}
get drawerProps() { return { empId: this.state.drawerEmpId, onClose: () => this.closeDrawer() }; }
closeDrawer() { this.state.drawerEmpId = null; }

// :201-205   drawer if present, full-page action otherwise
openEmployee(id) {
    if (!id) return;
    if (this.drawerCmp) { this.state.drawerEmpId = Number(id); return; }
    this.action.doAction({ type: "ir.actions.client", tag: "pb_employee_detail", … });
}
```

Mount point, last child of the root div — `pb_people/static/src/xml/people.xml:124-125`:
```xml
<t t-if="state.drawerEmpId and drawerCmp"
   t-component="drawerCmp" t-props="drawerProps" t-key="state.drawerEmpId"/>
```
`t-key` on the id forces a remount, and therefore a fresh slide-in, when
switching records.

**Your version:** registry category `pb_contracts_drawer`, key
`contract_360`, and `pb_contracts/static/src/js/contracts.js:96-99`
`openContract(id)` gains the same guard, keeping the existing
`pb_contract_detail` full-page action as the fallback. Deep link: accept
`?contract=<id>` and `action.params.contract_id / active_id`, mirroring
`people.js:42-47`.

**The drawer lives in `pb_contracts` itself** — unlike the employee one, there
is no separate vault module to hold it. Registering through the soft registry
anyway keeps `contracts.js` free of a hard import and matches the house shape.

### 3.3 Palette — settled, do not deliberate

The employee drawer's teal comes from a **hardcoded fallback pair**
(`--pbim-teal` is never defined anywhere; `#0E7C86` / `#E1F3F4` always win).
`theme_setup.scss` records that the per-zone theme variants were **retired** and
the app is one uniform indigo system.

**The contract drawer uses the system's own indigo.** Put `pbim` on the root and
take `--pbim-primary` (`#5A4BB0`) and `--pbim-soft` (`#EDEAF8`) for the accent
and the header band. Semantic colours come from the tokens too: green
`--pbim-green` `#2E7D4F` (money, good), amber `--pbim-amber` `#D97706`
(warning), rose `--pbim-rose` `#DC2668` (error), cyan `--pbim-cyan` `#2563EB`
(info), slate `--pbim-slate` `#64748B` (muted).

**Never invent a hex** (W1). If you need a shade that is not a token, you are
solving the wrong problem.

This also earns the two drawers a useful distinction: teal is a person, indigo
is a contract.

### 3.4 Width

**680px, `max-width: 96vw`.** The employee drawer's 580 is right for a two-up
stat grid; a component grid with a code chip, a name, a value, a source chip
and a bounds hint needs the extra 100px. Do not use `min(px, vw)` — the
employee SCSS header warns against mixed-unit `min()/max()`; use `max-width`.

### 3.5 Structure

```
.pbc.pbim                                     root
├─ .pbc-scrim(.shown)                          click → close
└─ aside.pbc-drawer(.shown)                    680px, right, flex column
   ├─ .pbc-busy   (t-if !loaded)               spinner
   ├─ error branch: .pbc-head + .pbc-empty     one sentence + close
   └─ loaded:
      ├─ .pbc-head                             indigo-soft band, does not scroll
      │  ├─ .pbc-head-id
      │  │  ├─ .pbc-ava                        employee avatar or initials
      │  │  └─ .pbc-head-tx
      │  │     ├─ h2            employee name
      │  │     ├─ .pbc-ref      contract reference, small, muted
      │  │     └─ .pbc-chips
      │  │        ├─ chip  briefcase → job
      │  │        ├─ chip  building  → department
      │  │        ├─ chip.tone-{ends_tone}  calendar → ends_label
      │  │        └─ chip.tone-{state}      fileText → state_label
      │  └─ .pbc-head-side
      │     ├─ .pbc-wage      label "Monthly wage" + big value
      │     │                 (•••••• when wage_masked; never the number)
      │     └─ button.pbc-x   close
      ├─ .pbc-tabs                             underline tabs, sticky under head
      │  ├─ Terms
      │  ├─ Components   + .pbc-tab-c count
      │  └─ History      + .pbc-tab-c count
      └─ .pbc-body                             the ONLY scrolling element
         ├─ TERMS
         │  ├─ .pbc-rail        pipeline steps, dot + label
         │  ├─ .pbc-acts        next_actions as .pbim-btn.ghost / .pbim-btn.outline
         │  ├─ per group: .pbc-sec > .pbc-sec-h (label) + .pbc-grid > .pbc-cell
         │  │              .pbc-cell > span.k (icon + label) + span.v (display || '—')
         │  │              a field with a hint gets .pbc-hint under the value
         │  └─ .pbc-stats       readiness chips (.ok / .off)
         ├─ COMPONENTS
         │  ├─ .pbc-explain     components.explainer  (t-if)
         │  ├─ .pbc-comps
         │  │  └─ .pbc-comp × n
         │  │     ├─ .pbc-comp-code    code chip, monospace, tabular
         │  │     ├─ .pbc-comp-id      name + .pbc-comp-from (fills_label chip)
         │  │     ├─ .pbc-comp-v       display, right-aligned, tabular-nums
         │  │     └─ .pbc-comp-b       bounds_hint (t-if bounded), muted
         │  ├─ warning chip on a row whose requires_new_contract is true:
         │  │     "usually starts a new contract"
         │  └─ .pbc-comp-add  (t-if addable.length)
         └─ HISTORY
            ├─ .pbc-tl
            │  ├─ .pbc-tl-sep    month separator (clone employee timelineRows())
            │  └─ .pbc-tl-item.tone-*
            │     ├─ .pbc-tl-ic     icon by kind
            │     └─ .pbc-tl-body
            │        ├─ .pbc-tl-l1  title + .when
            │        ├─ .pbc-tl-d   "from → to"  (t-if from or to)
            │        └─ .pbc-tl-a   source chip + actor
            ├─ .pbc-tl-more   "Showing 120 of 340" (t-if total > shown)
            └─ .pbc-empty     "Nothing has changed on this contract yet."
```

**Footer:** a thin `.pbc-foot` pinned below the body with one control —
`.pbim-btn.ghost` "Full form" opening the built-in form. Clone
`pb_contracts/static/src/js/contract_detail.js:60-62`:
```js
this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.contract",
    res_id: this.cid, views: [[false, "form"]], target: "current" });
```
CD-3 replaces this footer with the Save bar and demotes "Full form" to a small
link. Build the footer as its own block so CD-3 can extend it without a rewrite.

### 3.6 Motion — purposeful only

Three movements, no more:
1. the slide-in / slide-out already specced (`.22s`, the stated easing);
2. the scrim fade (`.18s`);
3. the tab underline sliding between tabs — a `transition` on the underline,
   not a keyframe animation.

Respect `prefers-reduced-motion`: wrap the transform transitions so a user who
asked for less motion gets an instant panel. Nothing else animates. No
staggered card reveals, no counting numbers.

### 3.7 Icons

`import { ic } from "@pb_import_kit/js/import_icons";` — **the `js/` segment is
mandatory** (W17.4; this has bitten three phases). Expose it as a method
(`ic(n, s = 16) { return ic(n, s); }`) and use `t-out`, never `t-esc` — it
returns `markup()`.

**W2: Lucide only, and new icons are ADDED to the shared registry** at
`pb_import_kit/static/src/js/import_icons.js`. **Do not create a per-module
icon file** — the employee vault's `pev_icons.js` predates the rule and is not
a precedent to follow. Icons that already exist and you will want: `briefcase,
building, calendar, banknote, creditCard, fileText, user, users, clock,
history, check, x, alert, plus, trash, chevronDown, settings, mapPin, award,
shield, stamp`.

---

## 4. Safety rails

1. **Read-only phase.** No `write`, no `create`, no `unlink` from the client.
   The only server change is §2.1's `fills_*` keys and `components.explainer`.
2. **W22 — an XML comment may not contain a double hyphen**, and OWL templates
   are XML. `<!-- ---- x ---- -->` is a parse error that kills **every**
   `t-name` in the file and blanks the whole backend bundle. Use
   `<!-- ==== x ==== -->`. **Run `xmllint --noout` on every XML file you touch**
   before deploying.
3. **W23 — one `class` attribute per element.** `t-att-class` and
   `t-attf-class` compile to the same attribute and the last wins. Safe pair:
   static `class="…"` plus `t-att-class="{ 'x': cond }"`. Nothing may sit
   between a `t-if` and its `t-else`.
4. **W96 — a template expression is compiled against the COMPONENT and nothing
   else.** `String(x)`, `Object.keys(x)`, `Math.max(...)` in a template become
   `ctx.String(...)` → `TypeError` at mount, no dialog, nothing in the log.
   **Put every expression in a method.** Enforced by
   `pb_integrations/tests/test_one_door.py::test_no_template_expression_calls_a_javascript_global`.
5. **W35 — a typed OPTIONAL prop still rejects `null`.** Pass `undefined` or a
   stable `{}`, never `null`.
6. **W21 — no fresh object literal in props on every render**; it recreates
   every child. Compute props in a getter over stable state.
7. **W148 — never write a fresh array into reactive state from `onPatched`**
   without a fixed point; it is a permanent rAF loop that looks like an idle
   screen.
8. **Formatting stays on the server.** Render `display`, `fills_label`,
   `bounds_hint`, `when_label` verbatim. The client's only formatting job is
   the em-dash for an empty value, inline in the template.
9. **Nothing may render `[object Object]`, `undefined`, `null`, `NaN` or
   `false`.** Every optional value gets `|| '—'`.
10. **The drawer must survive a payload from an older server** — a missing key
    renders an em-dash or an absent block, never a crash.
11. `hr.contract.advantage` has **no `company_id`** (W97): a multi-company
    record rule can hide rows. If the component list comes back short, that is
    why — report it, do not paper over it with `sudo` in the client.

---

## 5. Numbered test cases

OWL unit tests go in `pb_contracts/static/tests/` and need
`'web.assets_unit_tests': ['pb_contracts/static/tests/**/*']` in the manifest
(precedent `pb_records/__manifest__.py:97`). Python tests extend
`pb_contracts/tests/test_cd1_contract_360.py`'s package with a new file
`test_cd2_fills_from.py`.

**Python (server, cases 1–8):**

1. `fills_from` is present on every component row and is one of the five
   allowed values.
2. A component whose rule declares a `feed` source reports `api` with the label
   "From the connected system".
3. A component whose rule declares an `excel` source reports `excel`.
4. A component with a record destination (employee/contract field) reports
   `records` with "Held on this contract".
5. A component with **no** matching formula rule reports `none` and the row
   still renders every other key.
6. The scheme's configured lane ORDER decides the winner: with records ranked
   above the connected system, a component declaring both reports `records`;
   flip the order and it reports `api`. (This is the SC-3 pin — it proves you
   read `_config_kind_rank()` rather than hardcoding the ladder.)
7. `components.explainer` is a sentence when every amount is zero and the
   dominant source is not `records`, and is `False` when the contract genuinely
   holds values.
8. **Query budget:** computing `fills_*` for 21 rows issues a bounded number of
   queries — assert with `assertQueryCount` (or count via the cursor) that it
   does not scale per row.

**OWL / Chrome (cases 9–18) — verify on the live abm site:**

9. Clicking a contract row in the Contracts lens opens the drawer, not the
   full-page action.
10. The drawer slides in from the right and the scrim fades; Escape closes it;
    clicking the scrim closes it; the close button closes it.
11. The header shows the employee's name, the contract reference, the job,
    department, ends and state chips, and the wage.
12. All three tabs switch, and the Components and History tabs show their
    counts in the pill.
13. Terms renders four sections in the order money / dates / where they sit /
    payroll rules, with 20 cells, and an unset value shows an em-dash — not
    "false", "None" or an empty box.
14. Components shows 21 rows in code order, each with a source chip, and the
    explainer line appears above them on abm.
15. The "Add a component" control is **absent** on abm (`addable` is empty).
16. History shows its rows with month separators, and a contract with no
    history shows the empty sentence.
17. The whole drawer contains **no** "Odoo" anywhere — grep the rendered page
    text.
18. **No console errors** on open, on every tab switch, and on close.
    (C18.71: OWL template errors only surface at runtime; `-u` and Python tests
    are not enough.)

---

## 6. Build, test and deploy

1. Bump `pb_contracts/__manifest__.py` to `19.0.1.2.0`. Add the assets in the
   house order — **scss, then js, then xml** — and leaf JS before importers.
2. `xmllint --noout` every XML file you touch (rail 2).
3. Deploy per §0, upgrade all four databases, **purge the asset cache in each**,
   restart.
4. Run the Python suite detached and scoped:
   `-d payobook -u pb_contracts --test-enable --test-tags=/pb_contracts`
   (**never a bare `--test-tags`** — W9). Use `payobook`, not
   `payobook_template`: CD-1 found the template cannot build persona users
   (W159), so ACL-shaped cases skip there.
   Read `/var/log/odoo/odoo-server.log`.
5. **Chrome MCP validation on `https://abm.payobook.com` is mandatory** — you
   have standing approval to run it and to start or restart the browser
   whenever it is down. Never skip it, never pause to ask. Go to the People
   hub → Contracts lens, open a contract, and walk cases 9–18. Take a
   screenshot of each tab and describe what you see.
6. **One feature-scoped commit**, explicit file staging, reviewer-focused
   message. **Do not push.**

---

## 7. Report back

1. Test results — the exact result line; for any failure, whether it is yours.
2. Chrome validation: what you saw on each tab, with the screenshots, and the
   console output.
3. The real `fills_from` distribution on abm contract 1051 — how many of the 21
   rows landed in each of the five buckets, and the explainer sentence that was
   composed.
4. Anything in §1 or §3 that was **wrong or stale**. This is the most valuable
   item.
5. Judgement calls the spec did not settle, and what you chose.
6. Test cases you could not write, and why.
7. Whether the 680px width was right once real content was in it, and what you
   would change.
8. What CD-3 (in-place editing) will find hard, given what you now know about
   these cells.
9. A one-paragraph plain-English summary for a non-engineer.
