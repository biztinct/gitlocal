# COLROLES Phase 2 — The lens (studio, visible)

Read `docs/handovers/COLROLES_LEDGER.md` FIRST (standing rules + CR decisions + gotchas appended by
Phase 1). Phase 1 delivered: `column_role`/`column_role_source`/`is_text_component` on
hr.formula.rule, classifier, typed components, wizard classification, migration, `reclassify_roles`
RPC. This phase makes roles VISIBLE: the studio opens in a Payroll lens, People & Data collapses to
one row, the grid hides data columns, the Cell Editor gets a role picker, and five health hints land.

NOTE: pb_formula_studio.py line numbers below are pre-Phase-1; Phase 1 inserted an RPC, so
re-locate by SYMBOL when lines have shifted. formula_studio.js / studio.xml / grid_studio.js were
untouched by Phase 1 — their line numbers hold.

## Scope

1. Serializer + edit-surface exposure of the new fields.
2. `_group_for` fifth group "People & Data"; sidebar collapsed section + count chip; lens switcher
   (Payroll | Everything) persisted to localStorage.
3. Grid filtering under the Payroll lens (first real consumer of `is_visible_in_grid`).
4. Role chips/icons; Cell Editor role picker + explicit "Apply role defaults" affordance.
5. Five health hints + icons.
6. Command palette entries; SCSS; vi_VN labels.

**Binding non-goals**: NO mapping-surface changes (Phase 3). NO bank model/batch changes (Phase 3).
NO import-wizard UI beyond what Phase 1 shipped. NO behavior change to computation.

## Verified plumbing facts (frontend explorer, pre-Phase-1; do not re-derive)

- **Serializer**: pb_formula_studio.py, inside `get_studio_data` — the per-rule dict append
  (symbol: `components.append({`, was :294-317). Current keys: id, col, code, sequence, category_id,
  note_count, review_open, name, type, group, excel_formula, constant_value, tokens, explain,
  category, number_format, is_valid, validation_message, appears_on_payslip, depends_on, used_by.
  ADD: `column_role` (fallback-safe), `column_role_source`, `is_contract_component`,
  `is_text_component`, `is_visible_in_grid`. Frontend must guard `c.column_role || 'payroll'`.
- **Edit whitelists** (pb_formula_studio.py): `_EDIT_FIELDS` (symbol, was :958-966) — add
  `column_role`; `_BULK_FIELDS` (was :745) — add `column_role`; `get_component_edit` payload (was
  :969-1008) — add `column_role`, `column_role_source`, `is_text_component`. IMPORTANT: when
  `save_component` writes a role change, also set `column_role_source='user'` server-side (do it in
  `save_component`, not the client).
- **Grouping**: `_group_for(rule)` (pb_formula_studio.py, was :72-82) — insert BEFORE the
  input-check: `if rule.column_role and rule.column_role != 'payroll': return 'People & Data'`.
  Consumed also by get_problems' offpayslip check (was :3266) — verify that check still only fires
  for Totals (it will: non-payroll returns earlier).
- **Sidebar**: studio.xml:919-951 — `.pbfs-outline`, head :921-940 (4 action buttons), group loop
  :940-951 over `visibleGroups`/`groupItems(grp)`. JS: `GROUPS` array formula_studio.js:46
  (["Inputs","Earnings","Deductions","Totals"] → append "People & Data");
  `groupItems(g)` :1356; `get visibleGroups()` :1357; `catKey(group)` :1441 (colour keys — add a
  muted key for the new group). SCSS: studio.scss:115-125 (.ol-grp/.ol-item), sidebar styling.
- **Fold precedent** (collapse mechanics to imitate): `state.folds` formula_studio.js:469,
  `onToggleFold` :936-940, cleared on config switch :610-617.
- **localStorage precedent**: `pbfs_raw_mode` — read :258, write :1472 (try/catch for private mode).
  New key: `pbfs_lens`, values 'payroll'|'all', default 'payroll' when absent.
- **Grid**: grid_studio.js `get ordered()` :117-120 (sorts props.components; NO filter today) —
  add the lens filter here; everything downstream (viewOrdered :128-144, displayColumns :942-971,
  keyboard nav, drag-fill) keys off it. Lens state lives in the PARENT (formula_studio.js state),
  passed as a prop (see how `components` is passed: studio.xml:1338 `<GridStudio
  components="state.components" .../>` — add a `lens` prop next to it and thread through
  grid_studio props registration).
  Filter rule (CR): show iff `lens==='all' || role==='payroll' || c.is_visible_in_grid === true`…
  BUT Phase 1 set is_visible_in_grid=False only for NEW non-payroll rules; legacy rules have it
  True (default) — meaning legacy configs would show everything under the Payroll lens via the
  is_visible_in_grid===true clause. DECISION (locked): the Payroll-lens grid filter is
  `role === 'payroll' || (role !== 'payroll' && c.is_visible_in_grid === false ? false : role === 'payroll')`
  — simplify: show iff `lens==='all' || (c.column_role || 'payroll') === 'payroll'`. Ignore
  is_visible_in_grid for the LENS (it remains an independent per-column hide honored in BOTH lenses:
  a rule with is_visible_in_grid===false is hidden even in 'all'). Two orthogonal mechanisms, both
  finally consumed.
- **Grid footer**: add count pill; grid_studio.xml has fold chips precedent :19-33.
- **Cards/Cell Editor**: single-card view studio.xml:954-1307; editing block :1134-1307; Identity
  section (full scope) :1234-1252 — put the role picker here as a 6-chip row; `state.editScope`
  'simple'|'full' (formula_studio.js:448, toggle :2486); `state.draft` = verbatim
  `get_component_edit` response (:2465-2468); `setDraftField` :2488-2493; save via `save_component`
  (:2536-2554). "Apply role defaults" = when draft role changed payroll→non-payroll, show an inline
  suggestion chip that (on click) also sets draft.appears_on_payslip=false,
  draft.is_visible_in_grid=false — explicit, never silent (CR).
- **Problems**: `get_problems` (pb_formula_studio.py, symbol; was :3122-3305); `_add(kind,severity,
  title,detail,rule,col,note_id)` helper (was :3141-3153); rail renders any kind generically;
  client `probIcon` map formula_studio.js:4058-4063 — add 5 entries. Hints (from plan §5):
  - `noident` error: config has ≥1 input rule AND zero rules with column_role='identity'.
  - `refinformula` error: rule with role!='payroll' (or is_text_component) whose code appears in
    another rule's formula_dependencies (comma-split, CR2).
  - `bankunmapped` warning: role='bank' rule with no hr.payslip.import.mapping row for this config
    referencing it (Phase 3 adds bank destinations; until then ANY mapping row on the rule counts).
  - `idunmapped` hint: role in (identity, profile, contract) AND not is_contract_component AND no
    mapping row → "imported but going nowhere". Severity 'hint'.
  - `nonpayslip` warning: role != 'payroll' AND appears_on_payslip=True.
  Titles/details: plain language, white-label, translatable.
- **Sidebar presentation spec (the wow)**: Payroll lens → after the 4 payroll groups, render ONE
  row `People & data · <n>` (muted ink, count chip) that expands/collapses in place (own state,
  default collapsed, NOT persisted). Everything lens → "People & Data" renders as a normal expanded
  group; each row gets a 14-16px inline SVG role icon (id-card identity / user profile / briefcase
  contract / landmark bank / file-text reference; payroll rows undecorated) + the existing type
  badge. Lens switcher: two-segment control at the top of the outline head (style: existing
  .pbfs-seg / soft-button idiom, studio.xml:85-100 precedent), label "Payroll | Everything".
- **Command palette**: `paletteCommands` (formula_studio.js:1070-1102) — add "Toggle lens" and
  (design-lane copy tweak only if trivial) leave commandLanes otherwise for Phase 3.
- **Design system**: indigo tokens (--i #5A4BB0 family), no gradients/emoji, Lucide-style inline
  SVGs, muted grays for the tucked-away section. i18n: pb_formula_studio/i18n/vi_VN.po exists —
  add msgids for every new user-visible string (labels can ship EN with .po entries added; exact
  vi translations: use sensible Vietnamese, e.g. "Nhân sự & dữ liệu" for People & Data).
- **Versions**: bump pb_formula_studio manifest (Phase 1 set it to 19.0.1.108.0 → this phase
  19.0.1.109.0; verify actual current value first). pb_hr_payroll_formula only if touched (hint
  logic lives in pb_formula_studio — likely untouched; don't bump what you don't touch).

## Numbered test cases

1. Serializer: get_studio_data on a fixture config emits column_role/…/is_visible_in_grid per rule
   (Odoo test or post-deploy RPC probe).
2. `_group_for`: each non-payroll role → "People & Data"; payroll rules → unchanged buckets
   (regression: same fixture pre/post).
3. save_component with a role change flips column_role_source to 'user' (server-side).
4. bulk_update_components accepts column_role and rejects unknown keys (existing UserError path).
5. Each of the 5 hints fires on a crafted config and is absent on a clean one (Odoo tests coded;
   live-verified on abm where noident/idunmapped will naturally fire).
6. Grid: Payroll lens hides non-payroll columns; Everything shows them; is_visible_in_grid=false
   hides in BOTH lenses (hoot/QUnit if the suite exists — else scripted Chrome-MCP DOM assertions).
7. Lens persists across reload (Chrome-MCP: set Everything, reload, still Everything; clear key,
   reload, Payroll default).
8. Sidebar: Payroll lens shows collapsed "People & data · N" row matching the true count; expand
   shows rows with role icons; Everything lens renders the expanded group.
9. Cell Editor: role picker renders in full scope; payroll→profile change surfaces "Apply role
   defaults" chip; clicking sets both draft flags; save persists all three.
10. 250-column config (payobook "Payobook Scale Demo — 250 Columns"): get_studio_data wall time
    within existing budget (no visible regression opening the studio).
11. White-label + i18n: grep new strings for "Odoo" (must be none); vi_VN.po parses.

## Deploy + live verification

1. Local: JS parse (node --check via .mjs copy), XML parse, SCSS compile (npx sass), python compile.
2. Deploy per ledger ritual, `-u pb_formula_studio` (add pb_hr_payroll_formula ONLY if touched),
   all 4 DBs, EXIT=0 ×4, restart, port up.
3. Chrome-MCP on payobook (action-1160): screenshot Payroll lens (decluttered sidebar + collapsed
   People & data row), Everything lens (icons visible), grid both lenses, problems rail showing new
   hint kinds on a config that has them, Cell Editor role picker. Assert no console errors, no
   "style compilation failed" toast (asset-cache gotcha).
4. abm (action-742; owner session may be live — if not, psql-only): verify ABM config renders ~41
   payroll components + People & data row with the remainder.
5. Self-review diff vs spec; commit (feature-scoped, no push).

## Report back

Test results (incl. screenshots taken), per-DB deploy EXITs, hint counts observed on abm/payobook,
perf number for the 250-column config, deviations, gotchas appended to ledger, files touched,
manifest versions, commit hash.
