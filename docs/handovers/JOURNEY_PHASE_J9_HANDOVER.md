# JOURNEY — Phase J9: every source on the card, and a stated order of precedence

**Status:** handed to Opus 2026-08-26
**Reads first:** `docs/handovers/JOURNEY_LEDGER.md` (MJ1–MJ43), which inherits the MAPFIX (MF) and
COLROLES (CR) ledgers. Everything in those is load-bearing and none of it is repeated here.
**Predecessor:** J8 (commit `0de538f3`, `pb_formula_studio` 19.0.1.153.0 live ×4).

---

## 0. The owner's request, verbatim

> To avoid any confusion, I want you to display all the sources in the Payroll Schema cards eg
> SPREADSHEET, CONTRACT COMPONENT, CONNECTED SYSTEM. This would mean API and Excel can both map to
> the Payroll Schema component. (This is the change from what i earlier requested that only one can
> be allowed - i now want to remove that restriction). On top of it there is already allowed a
> mapping from Contract Component. So a card should show all the mappings done.
>
> Now who wins should be decided as per following logic
> - If API/Connect system data for that mapping exists then it has priority 1
> - If API/connected system field data is blank than Excel wins if it has data - it has priority 2
> - If Both API and Excel is blank then Contract Component wins - it has priority 3.
>
> Other logic of populating/updating the contracting component by API or Excel still remains same if
> the data is present in them.
>
> Also as mentioned above show in the Payroll Schema card all the sources and if more than 1 source
> is mapped then show a small number as superscript 1, 2, 3 accordingly.

This **supersedes** the earlier either/or restriction (J3's source-conflict dialog). It does **not**
supersede J-D5 — see §2.

---

## 1. Scope, and the binding non-goals

### In scope

1. A component may carry **more than one declared source** at the same time: a connected-system key,
   a rule output, a spreadsheet column, and the contract-component flag, in any combination.
2. The resolver walks those declared sources **in a stated order**, taking the first that actually
   delivered a value, and falling through to the next when one is blank.
3. Every board that draws a Payroll Schema card shows **all** of them, each with a superscript rank
   when the card has two or more.
4. The exclusivity enforcement is removed from the three places that impose it (§4.5).

### Non-goals — do not do these

- **Do not reorder the resolver ladder.** See §2. The rungs stay where they are.
- **Do not change what counts as blank.** `_feed_value_is_empty`
  ([`integration_field_mapping.py:507`](../../pb_hr_payroll_formula/models/integration_field_mapping.py#L507))
  is the one definition and the owner has re-confirmed it: `None` or a whitespace-only string is
  *nothing arrived*; **`0` and `False` are real values**. A connector reporting zero overtime has
  answered the question. Do not add a numeric-zero branch anywhere.
- **Do not touch the writeback.** The owner: *"Other logic of populating/updating the contract
  component by API or Excel still remains same"*. Whatever source wins, the existing writeback runs
  exactly as it does today.
- **Do not run `action_process` on any live database.** It writes into employee, contract and bank
  records. No live external API pulls during validation.
- **Do not build a new promotion path, a new board, or a new lane.** J8's `contract_component` lane
  stays as it is.
- **Do not rename or restructure `_declared_source`'s return value** (§4.2, trap T3).

---

## 2. Why this is not a J-D5 ladder reorder

J-D5 locked: *the resolver ladder order never changes in this programme — precedence becomes
visible and chosen.* That still holds, and the argument is worth having straight before you write
anything, because it also tells you what the safe implementation is.

The order the owner has asked for is the order that is already in the file:

| Owner's word | Today's rung | Where |
|---|---|---|
| API / connected system, priority 1 | connector pre-pass, assigns before the input loop and the loop then skips a filled code | [`payroll_import_batch.py:3148`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3148) |
| Excel, priority 2 | the bound branch, and the header/column-letter ladder under it | [`:3314`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3314), [`:3360`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3360) |
| Contract component, priority 3 | the tail | [`:3371-3376`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3371) |

The precedence is stated in prose at [`:3103-3114`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3103)
and again at [`:3138-3146`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3138). Read
both blocks before you touch the function.

**What is actually missing is not order — it is arity.** A component can declare exactly ONE source
today, because the binding is a single pair of Chars
([`formula_rule.py:179-190`](../../pb_hr_payroll_formula/models/formula_rule.py#L179)). When a
component is bound to `excel`, the feed side is consulted only as an unnamed heuristic fallback
(`side_o`, searched by the bound key then the natural candidates,
[`:3327-3329`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3327)). The owner wants
both sides *declared*, both *visible*, and the order between them *stated*.

So J9 gives the binding a plural form and walks it in the order that already exists. **No rung
moves.**

---

## 3. Verified facts — do not re-derive any of these

Everything in this section was checked against the code and against the live `abm` database on
2026-08-26. Treat it as given.

### 3.1 A run carries at most two payloads, and that machinery already exists

SOURCING S3 built it. [`payroll_import_batch.py:2961-2974`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L2961):

```python
topup = topup_data or {}
primary_origin = 'feed' if self.source_type == 'api_data_store' else 'excel'
topup_origin = 'excel' if primary_origin == 'feed' else 'feed'

def blob_for_kind(kind):
    want = 'feed' if kind == 'rule' else kind
    if want == primary_origin:
        return raw_data, primary_origin
    return topup, topup_origin
```

- `_merge_topup_rows` at [`:702`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L702)
  stamps a line `source_origin` of `both` / `topup`; `get_topup_data()` is read at
  [`:2469`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L2469).
- **`blob_for_kind` is the whole answer to "how do I read the API side on an Excel run".** You do
  not need to invent anything. `rule`-kind reads the feed side, because a transformation rule's
  output is delivered in the feed payload.

### 3.2 The connector pre-pass is a *different mechanism* from a feed binding

- The pre-pass ([`:3148`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3148)) walks
  `connector._sync_mapping_ids()` — rows of `hr.integration.field.mapping` with a `target_rule_id`.
  It runs **only when `self.source_type == 'api_data_store'` and `config.connector_id` is set.**
- A `feed` binding is two Chars on the rule, read in the bound branch.
- **On abm these two are the same source recorded twice.** All 9 feed-bound rules have a field
  mapping whose `source_field` is character-for-character the binding key:

  ```
  BANKNAME|Bank_Name|Bank_Name|t          NOOFDEPENDEN|No_of_Dependents|No_of_Dependents|t
  DESIGNATION|Designation|Designation|t   PITNUMBER|PIT_Number|PIT_Number|t
  EMPLOYEENAME|Name|Name|t                WORKEMAIL|EmailID|EmailID|t
  EMPLOYMETYPE|Employee_type|…|t          FULLNAMEVN|Full_Name_Vietnamese|…|t
  INSBOOKNO|Insurance_Book_Number|…|t
  ```

  This is because `api_mapping_create` draws the field mapping **and** writes the S3 binding (the
  S6 commit `1fb21315` did that deliberately). **Hence the dedupe rule in §4.3 — and trap T1.**

### 3.3 What `abm` looks like today (the before-picture your MF37 diff must restore)

| | count |
|---|---|
| rules with a binding | 13 (4 `excel`, 9 `feed`) |
| rules flagged `is_contract_component` | 20 |
| distinct rules targeted by a connector field mapping | 22 |
| rules with **both** a binding and a wire | 9 — all same-key, so **one** logical source each |
| rules with **both** a binding and the component flag | **1 — `GASALLOWANCE`** |

So after J9 ships, exactly **one card on abm** will render two chips (`GASALLOWANCE`:
Spreadsheet¹ · Contract component²) until the owner draws more. That is the correct outcome and it
is what you must report. **A change that lights up nine cards with two identical "Connected system"
chips has failed**, not succeeded.

The four `excel` bindings are `COSTCENTEFOR`, `GASALLOWANCE`, `LASTWORKIDAY`, `RESIDENCSTAT`, all
keyed `SEVL|<name>`.

### 3.4 The display seams

- [`pb_formula_studio.py:519-553`](../../pb_formula_studio/models/pb_formula_studio.py#L519)
  `_declared_source(rule, emp_dest_rule_ids, wire_dests=None)` — **the pivot.** Returns ONE
  `{'kind', 'key', 'wirable'}`. Its tiers: sealed column type → S3 binding → live connector wire
  (`wire_dests`) → `is_contract_component` → employee field → `none`.
- [`:557-583`](../../pb_formula_studio/models/pb_formula_studio.py#L557) `_SOURCE_LABELS` and
  `_source_label` — the closed vocabulary of eight words, mirrored in `source_vocab.js` as
  `srcLabel`. **A ninth term must not appear.** Note `_(variable)` extracts nothing (S19) — every
  literal is written out.
- [`:730-790`](../../pb_formula_studio/models/pb_formula_studio.py#L730) `_mc_right_item` — builds
  the card; sets `srcKind`/`srcNote`; blanks `srcKind` for a sealed card (S6 D1).
- Callers of `_declared_source` you must not break: [`:815`](../../pb_formula_studio/models/pb_formula_studio.py#L815)
  (right column), [`:829`](../../pb_formula_studio/models/pb_formula_studio.py#L829) and
  [`:842`](../../pb_formula_studio/models/pb_formula_studio.py#L842) (source note / transform board),
  [`:6022`](../../pb_formula_studio/models/pb_formula_studio.py#L6022) (Journey lane bucketing).
- [`mapping_canvas.js:891-910`](../../pb_formula_studio/static/src/js/mapping/mapping_canvas.js#L891)
  `srcChip(it)` — one chip from the scalar `it.srcKind`; returns `null` for `meta.wirable === false`.
- [`mapping_canvas.js:927-947`](../../pb_formula_studio/static/src/js/mapping/mapping_canvas.js#L927)
  `itemChips(it)` — assembles `[provChip, srcChip, badge, conflictChip]` **and drops any chip whose
  lowercased label duplicates an earlier one.** That rail is S6 D1's structural fix. See trap T2.

### 3.5 Where exclusivity is enforced today

1. `source_conflict_probe` at [`pb_formula_studio.py:5271`](../../pb_formula_studio/models/pb_formula_studio.py#L5271)
   — read-only probe behind J3's replace/fallback/cancel dialog.
2. `_already_fed_by` at [`:825-837`](../../pb_formula_studio/models/pb_formula_studio.py#L825) —
   produces the *"Already fed by %(src)s “%(key)s”"* sentence.
3. `employee_mapping_make_component` at [`:8379-8415`](../../pb_formula_studio/models/pb_formula_studio.py#L8379)
   — **unlinks any existing mapping at `:8402-8404`** before setting the flags.

### 3.6 Gotchas from the ledger that will bite this phase specifically

- **MJ42** — `node --check` on a `.js` ES module **exits 0 without parsing**. Checking the exit code
  is satisfiable by a check that never ran. Verify JS by fetching the **served bundle**.
- **MJ43** — a `//` comment *inside* an `import { … }` list makes the transform emit `require({)`
  and kills the entire bundle; the hoot runner shows a red banner with **zero tests executed** while
  the source parses fine as `.mjs`. Never put a comment inside an import list.
- **MJ15** — the Float `0.0` trap. Restated in §1 as a non-goal because this phase is the one most
  likely to reintroduce it.
- **MJ11** — take your own suite baselines; do not trust a number quoted in a doc.
- **MJ38 / MJ12** — the overlap sweep's definition of "layer" and its SVG exclusion. J8 fixed both;
  `pb_formula_studio/tools/mapping_overlap_sweep.js` now measures wire heads by name. Chips growing
  a superscript **changes card height**, so re-run it.
- **MJ40** — any fixed-width neighbour on a card's name line steals the name's width. You are adding
  chips to that line. `0 of 357 clipped` is J7's result and it is a regression gate.
- **CR18** — `hr.contract.create` seeds one EMPTY advantage line per template, so line-existence
  proves nothing; count only lines with a value.

---

## 4. Architecture — the exact seams

### 4.1 Storage: the binding becomes plural

New model `hr.formula.rule.source` in `pb_hr_payroll_formula`:

| field | type | note |
|---|---|---|
| `rule_id` | m2o `hr.formula.rule`, `ondelete='cascade'`, required, indexed | |
| `kind` | Selection `excel` / `feed` / `rule` | same three values as `source_binding` — **do not add a fourth**; the contract component is a boolean, not a binding (§4.3) |
| `key` | Char, required | the column header, feed key or rule output name |
| `origin` | Selection `user` / `board` / `import` / `migration` | mirrors `source_binding_origin` |
| `set_date` | Datetime, readonly | |
| `set_uid` | m2o `res.users`, readonly, `ondelete='set null'` | |

- One2many `source_ids` on `hr.formula.rule`.
- **Two Chars, never a foreign key** — the reasoning at
  [`formula_rule.py:162-178`](../../pb_hr_payroll_formula/models/formula_rule.py#L162) applies
  unchanged to `key`. A spreadsheet header has no record to point at, and a FK to
  `hr.api.transformation.rule` would rebuild the exact `ondelete='set null'` failure S2 spent a
  phase repairing.
- **At most one row per `(rule_id, kind)`.** Enforce in Python (`@api.constrains`) — Odoo 19
  silently ignores legacy `_sql_constraints` (see the warning repeated in a dozen models, e.g.
  [`formula_rule.py:1620`](../../pb_hr_payroll_formula/models/formula_rule.py#L1620)).

**Compatibility is mandatory.** `source_binding` and `source_binding_key` become **computed,
stored, readonly**, `@api.depends('source_ids.kind', 'source_ids.key')`, taking the
highest-ranked row (§4.2). There are **74 non-test references** to `source_binding` across six
files (`formula_rule.py`, `payroll_import_batch.py`, `excel_connector.py`,
`pb_integrations/models/pb_integrations.py`, `pb_formula_studio.py`, and the 19.0.1.77.0
migration). Every one must keep working untouched. Do not rewrite them.

`set_source_binding(kind, key, origin='user')`
([`formula_rule.py:261`](../../pb_hr_payroll_formula/models/formula_rule.py#L261)) **keeps its
signature** and changes meaning to *upsert the row for this kind, leaving other kinds alone* —
which is precisely "remove the restriction". Add `clear_source_binding(kind=None)` for removal
(`None` = all). `set_source_binding(False, …)` must keep meaning "clear everything", because
existing callers use it that way.

**Migration** (new version dir under `pb_hr_payroll_formula/migrations/`): one child row per
existing non-empty binding, carrying `origin`/`date`/`uid` across. 13 rows on abm. Idempotent.
Guard against `_check_source_binding` firing on a sealed column during the upgrade (trap T4).

### 4.2 The ranked walk — one function, used by both the resolver and the boards

```
RANK = ('feed', 'rule', 'excel')      # contract component is not a binding; it is rank 4, always last
```

`feed` before `rule` because both arrive in the feed payload and the connector's own field mapping
is the more specific statement. `excel` third. The contract component is **always last** among
declared sources, and below it the existing tail (header ladder → mapped employee/contract field →
default) is untouched.

Add on `hr.formula.rule`:

```python
def declared_sources(self):
    """Every source this component declares, in the order the resolver reads them."""
```

returning an ordered list of `{'kind', 'key', 'origin'}` — the `source_ids` sorted by `RANK`, plus a
trailing `{'kind': 'contract_component', 'key': ''}` when `is_contract_component`. **This one
function is the single definition of precedence** and both the resolver and every board must read
it. Two implementations of an order is how the boards started disagreeing in the first place.

On the studio side add `_declared_sources(rule, emp_dest_rule_ids, wire_dests=None)` returning the
ordered list **including** the live-connector-wire tier (§3.4) and the `employee_field` /
`calculated` / `constant` / `none` answers, and make the existing **`_declared_source` return
`list[0]`** so its four callers are byte-compatible. Do not change its return shape (trap T3).

### 4.3 Dedupe by `(kind, key)` — the rule abm proves

A `feed` binding and a connector field mapping naming the same `source_field` are **one source**.
Fold them before ranking, comparing `kind` and `key` exactly as stored. The 9 abm rows in §3.2 are
the fixture for this and case 3 below is its gate.

The contract component is deliberately **not** a `source_ids` row: it has no key, it is a boolean
that also controls a writeback, and giving it a second representation would create two ways to say
one thing. It joins the list only in `declared_sources()`.

### 4.4 The resolver — additive, with a neutrality rail

In `_transform_data_to_formula_inputs`:

- Replace the scalar `bound_kind`/`bound_key` read at
  [`:3234-3237`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3234) with the ranked
  list from `declared_sources()`.
- The bound branch at [`:3314`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3314)
  walks that list, `blob_for_kind(kind)` per entry, taking the first non-empty by the **existing**
  emptiness test. Reaching the end with nothing sets `value = None; bound_empty = True` and falls
  through to the untouched tail, exactly as today.

**The neutrality rail — this is the most important requirement in the phase.** When a component
declares **exactly one** source, the resolver must behave **byte-identically to today**, including
today's heuristic "search the other side by bound key then natural candidates"
([`:3327-3329`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3327)) and today's
fallback provenance (`via='fallback'`, `fell_back=True`). That heuristic is retained for kinds the
component has **not** explicitly declared. Only a second *explicit* source changes anything.

Consequence, and it is the right one: **nothing about how abm resolves changes until the owner draws
a second wire.** A component bound to `excel` still reads Excel first with the feed as an unnamed
fallback. The moment a `feed` source is declared on it, the feed becomes rank 1 and the order is
stated rather than inferred.

Assert this with a class counter in the S3 precedent's style
(`_sourcing_bound_branch_entered`, [`:3315`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3315)):
add `_multi_source_walk_entered`, and prove in a test that a full single-source run leaves it at
**zero**. Numbers merely agreeing is a weaker claim than the new path never having run.

Provenance: keep the existing `input_provenance.entry(...)` vocabulary. A win at rank 1 is
`via='binding'` as today. A win below rank 1 is `via='fallback'`, `fell_back=True`, and the skipped
higher-ranked sources are reported through the existing `ignored_side` helper — the owner's standing
rule is that the unused side is reported, never silently discarded
([`:3112-3114`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3112)).

### 4.5 Removing the restriction — the three sites

1. **`employee_mapping_make_component`** — delete the mapping unlink at
   [`:8402-8404`](../../pb_formula_studio/models/pb_formula_studio.py#L8402). Promoting to a
   contract component now *adds* a source instead of replacing one. J8's type-clash **refusal**
   stays exactly as it is.
2. **`source_conflict_probe`** — keep the name, keep it read-only, change what it returns: the
   resulting **ranked list** rather than a conflict. The dialog stops offering "replace" as its
   default and becomes a priority notice: *"Gas Allowance will read Connected system first, then
   Spreadsheet."* with **Add source** / **Cancel**. Keep a **Replace** button as the secondary
   action so the old behaviour is still reachable in one click.
3. **`_already_fed_by`** — the sentence *"Already fed by X"* now reads as a warning about something
   that is legal. Reword to state the resulting order, e.g. *"Also read from %(src)s “%(key)s” —
   this will be tried first."* / *"…tried after."* Keep it inside `_SOURCE_LABELS`' vocabulary.
   `conflictChip` in the canvas follows: it is no longer a conflict, and on a card that now renders
   ranked source chips it is **redundant** — drop it when the card carries ≥2 ranked chips, so the
   reader is not handed the same fact twice (S6 D1's principle).

### 4.6 Display — all sources, ranked

Server: `_mc_right_item` gains `srcKinds`: an ordered array of `{'kind', 'key', 'rank', 'note'}`.
**Keep `srcKind` populated with `srcKinds[0].kind`** so a stale bundle against a new server still
renders one correct chip. A sealed card sends `srcKinds: []` and `srcKind: ''`, as today.

Client, `mapping_canvas.js`:

- `srcChip(it)` → `srcChips(it)` returning an array; when `it.srcKinds` is absent, fall back to the
  single-chip behaviour built from `it.srcKind`, so **every board not yet migrated renders exactly
  as it does now**.
- **The superscript shows only when the card has ≥2 sources**, and it is the rank **among the
  sources actually mapped on that card** — the owner chose this explicitly over a fixed-per-type
  numbering. A card with Spreadsheet + Contract component reads **Spreadsheet¹ · Contract
  component²**, not ²·³.
- Mark it up as a real `<sup>` inside the chip with `font-variant-numeric: tabular-nums`, not a
  Unicode superscript character — screen readers and the font stack both handle the element better.
- `itemChips` pushes each ranked chip in order. **Leave the lowercased-label dedupe rail in place**
  (trap T2).
- Tooltip on each chip: the key it reads and its place in the order, e.g. *"Reads `SEVL|Gas
  Allowance` from the spreadsheet. Tried first."* / *"Used when nothing above delivered a value."*

Apply it on **all three boards** — the mapping canvas, the Transformations board and the Journey
board — via the shared `itemChips`. The owner's standing complaint is running around between screens
that each tell part of the truth.

Stylesheet: chips already wrap (`flex-wrap`, J7/MJ40). Verify the name line still measures **0
clipped** and re-run the sweep, because chip height changes card height.

### 4.7 White-label — absolute

The word **"Odoo"** must not appear in any user-visible string: labels, chips, tooltips, help text,
placeholders, empty states, toasts, action names, field `string=`/`help=`, selection labels,
reports, exports, emails, `.po` msgstr. Use **Payobook** or a neutral term. Technical identifiers
are untouched: `from odoo import …`, model/XML ids, `odoo-bin`, config paths, addon names, log
messages, code comments, and this document. There is one **pre-existing** "Odoo" in an SCSS comment
in `import_wizard.scss` that survives into the served bundle — leave it; it is a recorded owner debt
and not this phase's.

---

## 5. Traps

**T1 — nine cards saying "Connected system" twice.** abm's 9 feed-bound rules each also have a
connector wire with an identical `source_field` (§3.2). Without the `(kind, key)` fold they render
two identical chips. `itemChips`' label dedupe would then *hide* it, so the board would look right
while the resolver walked a duplicate. Gate: case 3.

**T2 — the label dedupe masks the bug.** `itemChips` drops a chip whose lowercased label matches an
earlier one ([`mapping_canvas.js:931-932`](../../pb_formula_studio/static/src/js/mapping/mapping_canvas.js#L931)).
Do **not** remove that rail and do **not** make the superscript part of the dedupe key — a genuine
duplicate must still collapse. The real guard is the `(kind, key)` fold upstream.

**T3 — four callers of `_declared_source`.** The right column, the source note, the transform board
and the Journey lane bucketing all read the scalar dict (§3.4). It must keep returning
`{'kind', 'key', 'wirable'}`. Journey's via→bucket map has a fourth `computed` bucket (MJ24–MJ29) —
do not disturb it.

**T4 — the constraint fires during upgrade.** `_check_source_binding`
([`formula_rule.py:249`](../../pb_hr_payroll_formula/models/formula_rule.py#L249)) raises when
`source_binding` is set on a non-`input` column. Making the field computed-stored writes it for
every rule at upgrade time. If any sealed column ends up with a source row the upgrade aborts
mid-way on a live database. The migration must skip non-`input` columns and the compute must not
manufacture a binding for a sealed card.

**T5 — the pre-pass only runs on an API-primary run.** [`:3148`](../../pb_hr_payroll_formula/models/payroll_import_batch.py#L3148)
is gated on `source_type == 'api_data_store'` **and** `config.connector_id`. **No config on any of
the four databases has `connector_id` set** — a standing owner debt. So on every live database the
pre-pass never fires, and a `feed`-declared source is served by the bound branch through
`blob_for_kind('feed')` reading the top-up blob. Your tests must cover both: pre-pass present, and
pre-pass absent with a feed top-up. Do not "fix" `connector_id` — that is the owner's decision to
make, not this phase's.

**T6 — `binding_dangling` is singular.** [`formula_rule.py:204-247`](../../pb_hr_payroll_formula/models/formula_rule.py#L204)
computes one boolean from the one binding, and it must now be per-source. `excel` stays advisory
(never dangling); an **empty** catalogue means "unknown", not "dangling", and must not raise a false
alarm. Keep it unstored — it is a statement about the world outside the record.

**T7 — MJ43.** No `//` comment inside an `import { … }` list. Verify by fetching the served bundle,
not by `node --check` (MJ42).

**T8 — the writeback must not double-fire.** With two sources declared, only the winning value is
written back to the contract component. Assert the component is written once, with the winner.

---

## 6. Test cases — run every one and report each by number

Server (`pb_hr_payroll_formula/tests/`):

1. A rule with **one** `excel` source resolves byte-identically to a rule with the equivalent legacy
   `source_binding`/`source_binding_key`, provenance included, and `_multi_source_walk_entered`
   stays at **0**.
2. `set_source_binding('excel', k)` then `set_source_binding('feed', k2)` leaves **both** rows;
   `source_binding` computes to `feed` (rank 1). `set_source_binding(False, '')` clears both.
3. **T1 gate.** A rule with a `feed` source keyed `Bank_Name` and a connector field mapping whose
   `source_field` is `Bank_Name` yields **one** entry from `declared_sources()`, not two.
4. Both declared, feed delivers → feed wins, `via='binding'`, and the skipped Excel value is
   reported through `ignored_side`, not dropped.
5. Both declared, feed delivers `''` → **Excel wins**, `fell_back=True`.
6. Both declared, feed delivers **`0`** → **feed wins** (MJ15). The Excel value is not used.
7. Both declared, feed delivers `False` → **feed wins**.
8. Feed blank, Excel blank, `is_contract_component` true with a contract line carrying a value →
   the **contract component** wins.
9. All three blank and no contract line → the existing tail (header ladder → mapped field →
   default) produces exactly what it does today.
10. **T5.** Cases 4–8 again on an **Excel-primary run with a feed top-up** and `connector_id` unset,
    so the pre-pass never runs. Same outcomes.
11. **T8.** With feed winning over Excel, the contract component is written back **once**, with the
    feed value.
12. `@api.constrains` refuses two rows of the same `kind` on one rule.
13. **T4.** Migration on a copy of abm's shape: 13 bindings → 13 rows; sealed (`formula`/`constant`)
    columns untouched; running it twice changes nothing.
14. **T6.** `binding_dangling` per source: a `feed` key absent from a synced catalogue is dangling;
    the same key with an **empty** catalogue is not; `excel` never is.

Client (hoot):

15. `srcChips` returns one chip and **no superscript** for a single-source card.
16. Two sources → two chips, `<sup>1</sup>` and `<sup>2</sup>`, in rank order; three → 1/2/3.
17. **Rank is among the mapped sources**: Spreadsheet + Contract component renders ¹ and ², not ²
    and ³.
18. A card with `srcKind` but no `srcKinds` (stale server) renders exactly one chip, unranked.
19. A sealed card renders **no** source chip and keeps its badge (S6 D1 must not regress).
20. **T2.** Two chips with the same label still collapse to one.

Live, on **abm only**:

21. `GASALLOWANCE` renders **Spreadsheet¹ · Contract component²**; the 9 feed-bound rules each render
    **exactly one** chip (§3.3).
22. Draw a second source onto a bound component by mouse: the dialog states the resulting order,
    **Add source** keeps both, and the card gains a ranked chip. Then **undo it** — nothing is left
    behind.
23. Sweep + `maxErr` at 1440 and 1024: 0 overlaps, 0 dock-over-card, 0 occluded/clipped heads, and
    names still **0 clipped** (MJ40 gate).

---

## 7. Safety rails

- **Never** `action_process` on a live database. No live external API pulls.
- Every live write goes through a **throwaway rule** (J8's precedent: `J8PROBE`, created → exercised
  → reversed → deleted). Name yours `J9PROBE`.
- **MF37 — the database is the oracle.** Take before/after row counts and fingerprints on abm for
  `hr_formula_rule`, the new source table, `hr_integration_field_mapping`,
  `hr_contract_advantage_template`, `hr_contract_advantage`. The last two are at **0 rows** and must
  stay there. Close with a clean diff and say so.
- Suites: take your **own** baselines (MJ11). Current: Python **467**, hoot **126**, with **three
  known pre-existing reds** — `TestBankDestinations.test_09_make_text_component`,
  `TestEndpointFieldCatalogue.test_05c`, `pb_integrations TestLedgers.test_the_ledgers_never_sudo`.
  They are an owner debt in files this programme never edited; do not silence them, and do not count
  them as yours. Any *fourth* red is yours.
- One feature-scoped commit with explicit file staging and a reviewer-focused message. **Do not
  push.**
- Append MJ44+ to `docs/handovers/JOURNEY_LEDGER.md` for anything new you learn the hard way.

---

## 8. Deploy — abm first, the other three batched

The owner has asked for less wall-clock, and the upgrade fan-out is the cost. So:

1. Build, test and validate against **abm only**.
2. Once every case in §6 passes, upgrade the remaining three in one pass:
   `acme`, `payobook`, `payobook_template`.

Ritual (MAPFIX, unchanged): rsync → `sudo chmod -R a+rX` → stop the service → detached `systemd-run`
with `sudo -u odoo /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <db> -u
pb_hr_payroll_formula,pb_formula_studio --stop-after-init` → start → verify
`ir_module_module.latest_version` in psql (`sudo -u postgres`) on **all four**.

Logins: abm `ash@biztinct.com` / `J5validate!2026`. acme's `lan@acme.com` shares the password but
**lacks the Formula Engine groups** — do not validate there.

---

## 9. Report back

- Commit sha; both module versions; `latest_version` confirmed on all four databases.
- Each of the 23 cases by number: pass / fail / deviation, with the deviation stated plainly.
- `_multi_source_walk_entered` = 0 on a single-source run (case 1) — quote the number.
- Suite deltas from **your own** baselines, and the count of reds with names.
- `employee_mapping_data` round-trip before/after in ms.
- Sweep results at 1440 and 1024, and the clipped-name count.
- The MF37 diff, including that both advantage tables are still at 0 rows on abm.
- **The abm picture after the change**: how many cards render two or more chips, and which. Expected:
  one (`GASALLOWANCE`). If it is nine, T1 has failed.
- Anything you found that contradicts §3. Say so; that section is a claim, not a scripture.
