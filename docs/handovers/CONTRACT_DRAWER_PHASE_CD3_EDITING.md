# CD-3 — Editing a contract in place, inside the drawer

**Programme:** CONTRACT DRAWER (CD). CD-1 (`fd51bed3`) built the server; CD-2
built the read-only drawer and is live on all four databases. This phase turns
the same cells into editors and closes the last dead-ends.

**The owner's choice, verbatim:** "Read beautifully, edit in place — everything
on one page. Click a wage or a date and change it right there, with a Save bar.
Components can be added and removed. You'd rarely need the old form again."

Implemented by an Opus build agent. Fable designed this and will not re-review
the code — run the numbered test cases, do the Chrome validation, and report.

---

## 0. Standing rules that bind this phase

**WHITE-LABEL (hard rule).** "Odoo" never appears in anything a user can see —
labels, buttons, tooltips, refusal sentences, confirmation dialogs, toasts,
empty states, `.po` msgstr. The escape hatch stays **"Full form"**. **Never
rewrite technical identifiers** (imports, model/XML ids, addon names, log
messages, comments, docs).

**PLAIN ENGLISH on every pixel and in every refusal.** Screen words: "pay run",
"pay data file", "the connected system", "the contract", "components", "the
employee record". Never a technical field name, never an internal ticket code.

**DESIGN BAR (binding):** extreme WOW, intuitive, out-of-this-world, best in
class. Hero moment, **zero dead-ends**, plain language, purposeful motion, bulk
ergonomics. Lucide icons only, added to the shared registry — never emoji,
never FontAwesome. **Never invent a hex**; the drawer is indigo
(`--pbim-primary`).

**DEPLOY CONTRACT** — `CLAUDE.md`. One addons directory. Clean staging dir.
Per-module `--delete`, **never** at the addons root. Upgrade all four
databases. **Purge the asset cache per database after any JS/SCSS change**
(`DELETE FROM ir_attachment WHERE name LIKE '%.assets_%' OR url LIKE
'/web/assets/%'`) and restart. ssh alias `Payobook19v2`. Run odoo detached via
`systemd-run`; read `/var/log/odoo/odoo-server.log`, never a `/tmp` sentinel.
Never a bare `--test-tags` without a scoping `-u`.

**LEDGER:** `docs/WORKFORCE_REDESIGN_CONVENTIONS.md`. CD1–CD9 are already
there; append CD10+.

---

## 1. What already exists — DO NOT RE-DERIVE OR REBUILD

### 1.1 The server (CD-1, live)

`pb_contracts/models/pb_contract_360.py`, `_inherit = 'pb.contracts'`:

- `get_contract_360(contract_id)` — the whole payload. Field entries carry
  `name, label, kind, value, display, required, writable, hint, tone`, plus
  `options` (select/toggle) and `comodel`/`value_label` (m2o).
  `kind` ∈ `money|number|integer|text|date|select|toggle|m2o|readonly`.
- `save_contract_360(contract_id, terms=None, components=None, note=None)` —
  the one write path. `terms` = `{field_name: raw_value}`. `components` =
  `{'edits': {advantage_id: {'amount': x} | {'text_value': s}},
    'adds': [{'template_id': n, …}], 'removes': [advantage_id, …]}`.
  Returns `{'ok', 'saved', 'refusals': [{'scope','key','why'}], 'msg',
  'detail': <the full fresh payload>}`.
  It writes **in place** on the existing contract, never creates a version,
  writes an `hr.contract.advantage.change` row with `change_source='manual'`
  for every accepted component change, and **never raises for a user mistake**.
- `preview_contract_360(contract_id, terms=None, components=None)` — the same
  validation, writes nothing, returns `{'ok', 'refusals', 'accept'}`. Save and
  preview share one private validation helper, pinned by CD-1 test 20.
- `lookup_contract_m2o(comodel, term='', limit=12)` — returns
  `[{'id','label'}]`. **Comodels are whitelisted** to `hr.payroll.structure,
  hr.contract.type, resource.calendar, hr.department, hr.job, res.users,
  wfp.pay.grade, account.journal`; anything else returns `[]`.
- `run_contract_action(contract_id, method, value=None)`
  (`pb_contracts/models/pb_contracts.py:164`) — whitelisted to `set_running`,
  `terminate`, `cancel`; `terminate` back-fills `date_end` with today.

**You do not need new server methods.** If you find you do, say so in the
report rather than inventing one quietly.

### 1.2 The drawer (CD-2, live)

`pb_contracts/static/src/js/contract_360.js` / `xml/contract_360.xml` /
`scss/…`, registered in the soft registry `pb_contracts_drawer` under
`contract_360`, opened from `contracts.js`'s `openContract` guard with the
full-page `pb_contract_detail` action as fallback. 680px, indigo, three tabs
(Terms / Components / History), footer with a "Full form" button.

Read the whole of it before you change it.

### 1.3 What CD-2 measured on the live tenant — this shapes the work

- abm contract 1051: 21 components, **20 of them `fills_from == 'excel'`**
  ("From a pay data file"), 1 `records`. `addable` is empty on every real
  contract because `hr.contract.create` seeds one line per template.
- `components.explainer` reads: *"Nothing is stored on the contract itself.
  Most of the components below are filled when a pay run reads a pay data
  file."*
- The floating assistant pill owns the bottom-right corner of every screen
  (ledger CD9) — a right-aligned footer control gets covered.

### 1.4 The editing precedents in this codebase

**The best one is `pb_records` (Records Desk).** Read these before designing:

| Thing | Where |
|---|---|
| the editor component + `get kind()` switch | `pb_records/static/src/js/records_cells.js:260` |
| editor markup per kind | `pb_records/static/src/xml/records_desk.xml:36-80` |
| number input — `type="text" inputmode="decimal"`, **not** `type="number"` | `records_desk.xml:67`, SCSS `records_desk.scss:385` (`tabular-nums`, right-aligned) |
| date input — native `type="date"` | `records_desk.xml:62` |
| YES/NO — two buttons, not a checkbox | `records_desk.xml:40-49`, SCSS `:387-397` |
| m2o / select — `RdPicker`, a filterable popover | `records_cells.js:98`, `records_desk.xml:51,56` |
| m2o feed | `records_desk.js:465` (`lookup_m2o`), debounced 220ms `:171` |
| keyboard contract — Enter commits, Tab commits + moves, Escape cancels, **every branch `stopPropagation()`** | `records_cells.js:293` |
| blur **commits**, never discards | `records_cells.js:311` |
| dirty map keyed per cell, with counts | `records_grid.js:70,78` |
| debounced server preview → refusals painted into cells | `records_desk.js:417,442`; the ruling is the docstring at `:412` — *"a refusal is a red dot with a sentence, not a modal"* |
| Cmd/Ctrl-Enter saves from anywhere | `records_desk.js:120-124` |
| pluralisation written out in both forms, never interpolated | `records_desk.js:396`, rationale `:388` |
| "nothing is saved until you apply" toast | `records_desk.js:511` |
| failure toast is **sticky** and says nothing was written | `records_desk.js:577` |

Simpler dirty-patch + one Save button:
`pb_formula_studio/static/src/js/component_treatment.js:148,158,194,229` and
its Save bar markup `xml/component_treatment.xml:18`. Note `:198` — the patch
key is **deleted** when the value returns to the record's, so the count is
truthful.

Add / remove rows: `pb_integrations/static/src/js/rule_composer.js:810,818` and
markup `xml/rule_composer.xml:189-218` (`.itgrc-x` trash per row,
`.itgrc-add` footer button, an empty-state sentence).

Confirmation dialogs (destructive only): `ConfirmationDialog` from
`@web/core/confirmation_dialog/confirmation_dialog` —
`pb_payrun_wizard/static/src/js/payrun_wizard.js:682`.

Error surfacing: `this.notif.add(msg, {type})`; the extraction idiom everywhere
is `error?.data?.message || error?.message || _t("…")`. A refused write is a
**notification or an inline sentence, never a dialog**.

---

## 2. The design to build

### 2.1 The editing gesture: click to edit, in place

The cell keeps its read design. Hovering it lifts a faint indigo tint and shows
a small pencil at the right edge. Clicking it — or tabbing to it and pressing
Enter — swaps the value for an editor **in the same box, at the same size**, so
nothing on the panel moves. Escape reverts that cell. Blur commits to the dirty
map (not to the server).

Rejected alternatives, so nobody re-opens them: a global Edit mode (a mode is a
thing to remember), and always-live inputs (turns a beautiful card into a form).

A cell that is not editable — `writable: False`, or `can_write: False`, or a
masked wage — does not hover, does not show a pencil, and is not tab-reachable.
It must be visibly inert, not merely unresponsive.

### 2.2 One editor component, one `kind` switch

Clone the shape of `RdCellEditor`. Nine kinds:

| kind | editor |
|---|---|
| `money` | `type="text" inputmode="decimal"`, right-aligned, `tabular-nums`, currency prefix shown outside the input |
| `number` | as money, no currency |
| `integer` | as number, rejects a decimal point with the refusal sentence |
| `text` | plain text input |
| `date` | native `type="date"` |
| `select` | popover list built from `options`; filterable when more than 8 |
| `toggle` | two buttons, YES / NO — clone `.rd-bool` |
| `m2o` | filterable popover fed by `lookup_contract_m2o(comodel, term)`, 220ms debounce |
| `readonly` | never becomes an editor |

**The m2o and select popovers must be `position: fixed`,** with coordinates
from the cell's `getBoundingClientRect()` on open. The drawer body is
`overflow-y: auto` and will otherwise clip the list — CD-2 flagged this as the
hardest thing here. Reposition or close on scroll; close on Escape and on
outside click.

**Every popover must offer a way to clear an optional field** ("Leave empty",
clone `.rd-editor-clear`, `records_desk.xml:77`) and **must not offer it for a
required one**.

Keyboard, copied verbatim from `records_cells.js:293` because it is a scar:
Enter commits and moves to the next cell; Tab commits and moves; Escape
cancels; **every branch calls `stopPropagation()`**, or the drawer's own
Escape-closes handler fires and the panel vanishes mid-edit.

### 2.3 The dirty map and the Save bar

- `state.dirty.terms` = `{field_name: value}`; `state.dirty.comps` =
  `{'edits': {}, 'adds': [], 'removes': []}`.
- A key is **deleted** when the value returns to what the record holds
  (`component_treatment.js:198`), so the count never lies.
- `dirtyCount` = terms keys + component edits + adds + removes.
- The footer becomes the **Save bar** the moment `dirtyCount > 0`: it slides up
  (120ms), shows `Save 3 changes` (primary) and `Discard` (ghost), and demotes
  "Full form" to a small text link on the left. Pluralise by writing both
  sentences out, never by interpolating a count into one
  (`records_desk.js:396`).
- **Pad the Save bar's right edge clear of the floating assistant pill**
  (ledger CD9) — measure it, do not guess.
- Cmd/Ctrl-Enter saves from anywhere in the drawer.
- **Closing the drawer with unsaved changes asks first** — a
  `ConfirmationDialog`: "You have 3 unsaved changes on this contract. Leave
  them?" / "Leave" / "Keep editing". This applies to Escape, the scrim and the
  × alike. An edit that vanishes silently is the worst outcome on this screen.

### 2.4 Refusals while typing

Debounce 400ms after the last change, call `preview_contract_360` with the whole
dirty set, and paint each refusal **under its own cell** as a red sentence with
a small dot. Clone `records_desk.js:417,442`; the ruling stands — *a refusal is
a red dot with a sentence, not a modal.*

The Save button's label carries the arithmetic when some will fail:
`Save 4 · leave 1` (clone `records_desk.js:552`). It stays enabled — the server
saves the good half; that is the designed behaviour, not a fallback.

### 2.5 Saving

1. Send the **entire** dirty set in one `save_contract_360` call. Because the
   Save bar is the only way to write, there is never an in-flight edit
   elsewhere to clobber — which is the question CD-2 left open. State that in a
   code comment so nobody re-derives it.
2. On the response: **replace the whole payload from `detail`** (the house
   "mutate returns everything" contract). Drop every accepted key from the
   dirty map. **Keep every refused key dirty**, with its sentence, so the
   person can fix it — the Records Desk does exactly this
   (`records_desk.js:590-596`).
3. Toast the `msg` — `success` when nothing was refused, `warning` when some
   were.
4. **Scroll the first refusal into view** and switch to its tab if it is on
   another one. A refusal the person cannot see is a screen that lies about
   having saved.
5. If the call itself throws: a **sticky** `danger` toast that says nothing was
   written, using the standard extraction idiom. Do not clear the dirty map.

### 2.6 Components — editing, adding, removing

- Amount and text rows edit in place with the `money` / `text` editors, keyed
  by advantage id.
- **The `fills_from` chip becomes a warning at the moment of editing.** Twenty
  of abm's 21 components read "From a pay data file". Typing into one is a
  value the next pay run will overwrite, and the person must be told **while
  they type**, inline under the cell, in amber, not red:
  > "The next pay run will replace this with the value from the pay data file."
  Word it for the actual source: the connected system, a pay data file, or a
  formula. A `records` component gets no warning. **This is information, not a
  refusal — never block the edit.**
- A row whose `requires_new_contract` is true gets a second amber line:
  > "A change like this usually starts a new contract. This one is saved onto
  > the contract you are looking at."
  That is the owner's ruling of 2026-08-29 stated honestly, not an error.
- Out-of-bounds is a **red refusal** with the bounds spelled out, from the
  server's own sentence — do not re-word it in the client.
- **Remove**: a trash button per row (clone `.itgrc-x`), which stages a removal
  and greys the row with an "Undo" link rather than making it disappear. A row
  the server refuses to remove says why.
- **Add**: render the control only when `addable.length > 0` — it is empty on
  every real contract today, and a permanently empty button is a dead end.
  When it does appear: a picker of `addable`, then a staged new row at the
  bottom.

### 2.7 The lifecycle actions — close the last dead-end

CD-2 sent `next_actions` to the full form because the drawer could not write.
Now it can. Wire them to `run_contract_action`:

- **Set running** — acts immediately, then replaces the payload from a fresh
  `get_contract_360`.
- **Terminate** and **Cancel** — destructive, so a `ConfirmationDialog` first,
  naming the person and the consequence in plain words: "Terminate THANH
  HUYNH's contract? It will be marked as ended today and will stop feeding pay
  runs." Confirm / Keep it running.
- Refuse the action while the drawer is dirty, with a plain toast: "Save or
  discard your changes first." Mixing a state change with unsaved edits is a
  question nobody should have to answer.

### 2.8 When the person may not write

`can_write: False` → no pencils, no Save bar, no lifecycle buttons, and one
quiet line at the top of Terms:

> "You can see this contract but not change it. An HR manager can."

No disabled controls scattered through the panel. One honest sentence.

---

## 3. Safety rails

1. **Never create or unlink an `hr.contract`.** Removes are component rows.
   Writes are in place. (Owner ruling 2026-08-29.)
2. **Never send a key the payload did not mark `writable`.** The server refuses
   it anyway; sending it is a bug that hides behind a refusal.
3. **A masked wage never becomes an editable box.** `wage_masked` and
   `writable: False` travel together; honour both.
4. **W22** — no `--` inside an XML comment; it kills every `t-name` in the file
   and blanks the whole backend bundle. Use `<!-- ==== x ==== -->`. **Run
   `xmllint --noout` on every XML file you touch.**
5. **W23** — one `class` attribute per element; static `class` + `t-att-class`
   object is the safe pair. Nothing between a `t-if` and its `t-else`.
6. **W96** — no JavaScript global in a template expression (`String`,
   `Object`, `Math`, `Number`, `parseFloat`). It compiles to `ctx.String(...)`
   and throws at mount with nothing in the log. **Every expression goes in a
   method.** Gated by
   `pb_integrations/tests/test_one_door.py::test_no_template_expression_calls_a_javascript_global`.
7. **W35** — a typed optional prop rejects `null`; pass `undefined`.
8. **W21** — no fresh object literal in props per render.
9. **W148** — no recompute→state→patch cycle without a fixed point.
10. **No `t-model`.** Nine occurrences exist in the whole repo and none is an
    editor of record; the house pattern is explicit `t-att-value` +
    `t-on-input`/`t-on-change` because the handler must coerce, diff against
    the record to clear the dirty key, and trigger the preview.
11. **A picker must not offer what the server will refuse** (W29). The comodel
    whitelist is the server's; do not widen it client-side.
12. **Formatting stays on the server.** After a save, read `display` from the
    fresh payload — never format the number you just typed.
13. **`prefers-reduced-motion`** — the Save bar's slide and the popovers'
    transitions must degrade to instant.
14. **Focus must be visible** on every editor and every button, and the popover
    must trap Tab within itself while open.

---

## 4. Numbered test cases

Python: extend `pb_contracts/tests/` with `test_cd3_edit_paths.py`.
Browser: walk on live abm with Chrome MCP.

**Python (1–8):**

1. `save_contract_360` with one term writes it and the contract count for that
   employee is unchanged (the in-place pin, re-asserted at the edit boundary).
2. `preview_contract_360` and `save_contract_360` return the same refusal keys
   for a mixed payload of four good and two bad values.
3. A component amount edit through the save path creates exactly one
   `hr.contract.advantage.change` with `change_source == 'manual'`.
4. A staged remove of a mapping-fed component is refused with a sentence; the
   row still exists afterwards.
5. `lookup_contract_m2o` returns rows for each of the eight whitelisted
   comodels and `[]` for `res.partner`.
6. `run_contract_action(cid, 'terminate')` sets `state` and back-fills
   `date_end`; an unlisted method name is refused and changes nothing.
7. As a reader without contract-write rights: `can_write is False`, every term
   `writable is False`, and a `save_contract_360` call writes nothing and
   refuses with a plain sentence.
8. No string anywhere in a refusal produced by cases 1–7 contains "odoo",
   case-insensitively.

**Browser on `https://abm.payobook.com` (9–24):**

9. Hovering a writable cell tints it and shows the pencil; hovering a
   non-writable one does neither.
10. Clicking a money cell opens a right-aligned decimal editor **without the
    panel shifting**; typing and blurring stages the change.
11. The Save bar appears on the first change, reads "Save 1 change", and reads
    "Save 2 changes" on the second — both spellings correct.
12. Returning a value to its original removes it from the count and the Save
    bar disappears.
13. Escape inside an editor reverts that cell **and does not close the drawer**
    (the `stopPropagation` pin).
14. Enter and Tab commit and move to the next cell.
15. A date cell opens a native date picker and stages a date.
16. A select cell (Employment status) offers Active / Resigned / Terminated /
    Long Leave / New Hire and stages one.
17. A toggle cell (Union participation) flips between YES and NO.
18. An m2o cell (Salary structure) opens a **filterable popover that is not
    clipped by the drawer edge**, filters as you type, and stages a choice.
19. Typing `abc` into the wage paints a red sentence under that cell within a
    second, and the Save button reads `Save N · leave 1`.
20. Saving a mixed set writes the good ones, keeps the bad one dirty with its
    sentence, scrolls it into view, and toasts a warning.
21. Editing a component whose chip says "From a pay data file" shows the amber
    overwrite warning inline and still allows the edit.
22. Closing the drawer with unsaved changes asks first; "Keep editing" returns
    to the drawer with the changes intact.
23. "Terminate" asks for confirmation naming the person, and on confirm the
    state chip and the rail both update without a page reload.
24. **No console errors** through all of the above — open, edit, preview, save,
    refuse, confirm, close.

---

## 5. Build, test and deploy

1. Bump `pb_contracts/__manifest__.py` to `19.0.1.3.0`.
2. `xmllint --noout` every XML file you touch.
3. Deploy per §0; upgrade all four databases; **purge the asset cache in each**;
   restart.
4. Python suite detached and scoped: `-d payobook -u pb_contracts
   --test-enable --test-tags=/pb_contracts`. Read
   `/var/log/odoo/odoo-server.log`. (Use `payobook`, not the template — it
   cannot build persona users, W159.)
5. **Chrome MCP validation on `https://abm.payobook.com` is mandatory.** You
   have standing blanket approval to run it and to start or restart the browser
   whenever it is down — never pause to ask, never skip it. Walk all sixteen
   browser cases and screenshot each state.
   **Use a contract you can safely change and put every value back afterwards**
   — abm is not in production, but leaving a tenant's contract altered by a
   test is not acceptable. Record the before and after of everything you touch
   and confirm the restore.
6. **One feature-scoped commit**, explicit file staging, reviewer-focused
   message. **Do not push.**

---

## 6. Report back

1. Test results — the exact result line; for any failure, whether it is yours.
2. Chrome validation: what you saw at each of the sixteen states, with
   screenshots and the console output.
3. Exactly which contract and which values you changed on abm, and proof you
   put them back.
4. Anything in §1 or §2 that was **wrong or stale**. Most valuable item.
5. Judgement calls the spec did not settle, and what you chose.
6. Test cases you could not write or walk, and why.
7. How the `position: fixed` popover behaved in practice — that was the
   flagged risk.
8. What is still weak about this screen, honestly. What would you do next?
9. A one-paragraph plain-English summary for a non-engineer.
