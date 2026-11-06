# Approval Matrix · Phase 2 — Configuration workspace + the one inbox

**Handover from Fable (design) to Opus (build) · 12 Sep 2026 · read `APPROVAL_MATRIX_LEDGER.md` first (rules, deploy contract, AM entries) and append to it. Phase 1 (`biz_approval_workflow`) is installed; read its final report in the ledger (AM entries ≥ AM5) and its code before using the API.**

Visual spec = the POC: `docs/design/approval-matrix-poc.html` + `docs/design/approval-matrix-poc/*` (styles.css is the layout/spacing/colour spec; matrix.js, builder.js, scheme.js, inbox.js hold the exact copy, states and interactions). Port it 1:1 into OWL with the product's tokens. The design bar is verbatim in the ledger: "extreme WOW, intuitive, out-of-this-world, best in class".

## 1. Scope

New module **`pb_approval_config`** ("Approval Matrix"):
1. **Approval Matrix workspace** (client action `pb_approval_matrix`, opened from Settings): tabs Matrix · People & backups · History. Presets. Import-from-spreadsheet door (button that opens a stub explaining the P6 importer; no parsing yet).
2. **Workflow builder**: Purpose → People → Safeguards → Review & publish, live sentence, step cards, add-step menu (incl. Only when…, Notify only, No approval needed), route-by-amount ladder, who-decides picker drawer, safeguards cards, sticky Try an example, Check whole coverage, publish with warnings-as-confirmations, success state.
3. **People & backups**: responsibilities grid (roles × company/divisions), assign drawer with "Needs permission" state, hand-overs (delegations) list + drawer, toggle.
4. **History** tab over `biz.approval.event`.
5. **`ApprovalSchemePanel`** — a reusable OWL component (props: `processKey`, `scopeKey`, `scopeLabel`, `companyId`) rendering "Pay run approval: Inherited / Shared / Custom + Change" with division exceptions and "What will happen". P3 mounts it inside Blueprint Connect and scheme Settings; in P2 it is exercised from the Matrix (row → "Where it applies") for any process whose adapter provides scope options.
6. **The one inbox** `PbInbox` (exported): My turn / All I can see / Returned / Done; request cards across processes; request drawer with frozen facts, evidence, route timeline, joint seat progress, covering-for badges; Approve / Approve with exception (reason gate) / Send back (reason) / Reject (reason, consequence text); blocked-request repair door; "Ask for a sign-off" (creates a `biz.approval.generic.request` and submits it). Mounted as the Home hub `approvals` lens **replacing** the old pay-run board.
7. Seed data: Payobook role catalogue, the full process catalogue (40 rows, `connected` computed by the engine), per-company default workflow + binding for `generic`, and an install/migration hook that assigns the company admin as the company-level `approver` so day one works.
8. Vietnamese `.po`, static-contract test, facade tests, Chrome validation, deploy to every DB.

**Non-goals:** no pay run / Blueprint / formula / Records / delivery adapters (P3–P5); do not touch `pb_approval`, `pb_team`, `pb_mission` (P3/P5 retire them); no spreadsheet parsing (P6); no new rail item (standing rule); no changes to engine semantics — additive engine methods only (§3.4), with a version bump.

## 2. Verified plumbing (do not re-derive)

| Fact | Where |
|---|---|
| Settings tiles are a JS registry `SETTINGS_CATEGORIES = "pb_settings_category"`; a registered key equal to a shipped key replaces it; clone `pb_group/static/src/js/group_palette.js:56-84` (`categories.add("group", {...}, {sequence: 30})`, cards by `xmlid`). Sequence 20 and 30 taken → use **40**. Server gate `pb.settings.resolve_gates` fails open per group | `pb_settings/static/src/js/settings_hub.js:131-251, 255-342`; `pb_settings/models/pb_settings.py:83-106` |
| Hub shell lens contract `{key, icon, label, groups?, Component?, props?, wantsArrival?}`; lens props `{embedded:true, ...def.props}`; deep links via `openHub(action, {tag|xmlid, lens, focus, back})`, `HUB_LENS_KEY="pb_lens"` | `pb_hub/static/src/js/hub_shell.js:57-92, 309-335`; `pb_hub/static/src/js/hub_nav.js:29-117` |
| Home hub: `PbApproval` hard-imported at `home_hub.js:49`; lens registered `:121-122` `{key:"approvals", icon:"inbox", label:_t("Approvals"), Component: PbApproval, groups: APPROVAL_GATE}`; `APPROVAL_GATE` `:52-59`; `HOME_LENSES` registry appends without dedupe `:131-139` | `pb_home_hub/static/src/js/home_hub.js` |
| Palette rows: `hub_palette_entries.js:104-106` (`approvals` → `{tag:"pb_approval"}`, payroll groups) and `home_hub_palette.js:43-58` (`homehub_approvals`, imports `APPROVAL_GATE`). Shared headings `G_SURFACES`/`G_ADMIN` `:80-83`. Free ⌘K block: **3400** | `pb_hub/static/src/js/hub_palette_entries.js`, `pb_home_hub/static/src/js/home_hub_palette.js` |
| Reference cockpit to clone: `pb_group` — manifest assets order (scss, component js, palette js, xml), client action with `pb_back` context, root `class="pbim pbim-page grp"`, `setDisplayName`, `HubBackChip`, RPC facade AbstractModel with `_require_*` gates and `_safe()`, tests `test_group.py` + `test_static_contract.py` | `pb_group/__manifest__.py`, `views/pb_group_action.xml:20-24`, `static/src/js/group_room.js:85-120`, `models/pb_group_room.py:64-104`, `tests/` |
| Icons: `import { ic } from "@pb_import_kit/js/import_icons"`; keys in `IC` at `pb_import_kit/static/src/js/import_icons.js:6`; add missing keys there (needed: `workflow`, `gitBranch`, `flag`, `userX`, `repeat`, `circleDot`, `badgeCheck`, `split` if absent — check first) | — |
| Tokens: `--pbim-*` only (no hex in SCSS); `.pbim-page` shell; components `.pbim-hero/.pbim-badge/.pbim-btn/.pbim-chip/.pbim-panel/.pbim-rail/.pbim-table` | `pb_import_kit/static/src/scss/import_tokens.scss`, `import_kit.scss` |
| Divisions: `pb.division` (`name, code, company_ids, people_count`), `_links_on`, `division_for` | `pb_group/models/pb_division.py:55-214` |
| Users picker: `res.users` `[('active','=',True),('share','=',False)]` folded search, cap; avatar `/web/image/res.users/<id>/avatar_128` | `biz_access/models/pb_access_facade.py:1376-1395` |
| Company on write paths: `self.env.user.company_id`, never `self.env.company`; multi-company reads via `_with_companies()` pattern | `pb_settings/models/pb_company_profile.py:182-199`; `pb_decision_room/models/pb_decision_room.py:875-898` |
| Working calendar / tz: `res.company.resource_calendar_id.tz`, employee tz wins | `pb_close/models/wf_lock.py:247` |
| VI translation tooling and the per-module `.po` test to copy | `tools/refresh_pb_vi.py` (docstring), `pb_explorer/tests/test_p7_vietnamese.py:35-78` |
| "Odoo" gate and static contract examples | `pb_group/tests/test_static_contract.py`, `pb_blueprint/tests/test_white_label.py:45` |

## 3. Architecture

### 3.1 Module

```
pb_approval_config/
  __manifest__.py   depends: biz_approval_workflow, pb_hub, pb_settings, pb_sidebar, pb_import_kit, pb_group, hr, mail
  models/
    matrix_facade.py   pb.approval.matrix  (AbstractModel; every configuration RPC)
    inbox_facade.py    pb.approval.inbox   (AbstractModel; every runtime RPC)
    seed.py            per-company defaults (hook + migration + res.company create hook)
  data/roles.xml, processes.xml, presets.xml (presets as JSON definitions), pb_sidebar.xml (match tags only; NO new rail item)
  views/actions.xml  (ir.actions.client pb_approval_matrix with pb_back to Settings; pb_approval_inbox for direct opening)
  security/ (ACL for nothing new unless you add a model; record rules none)
  static/src/scss/approval_matrix.scss (.pbim.pbam), inbox.scss (.pbim.pbam-inbox)
  static/src/js/: matrix_room.js (root, tabs), matrix_tab.js, builder.js, step_card.js, picker_drawer.js, example_panel.js, coverage.js, publish.js, people_tab.js, history_tab.js, scheme_panel.js (exports ApprovalSchemePanel), inbox.js (exports PbInbox), request_drawer.js, decision_modals.js, ask_drawer.js, sentence.js (client mirror of the engine's summary for instant feedback; the server's is authoritative on save), palette.js (Settings category "approvals" seq 40 + ⌘K rows 3400–3440)
  static/src/xml/*.xml
  i18n/pb_approval_config.pot, vi_VN.po
  tests/test_static_contract.py, test_matrix_facade.py, test_inbox_facade.py, test_seed.py, test_vietnamese.py
```

### 3.2 Facade `pb.approval.matrix` (config; gate = `biz_approval_workflow.group_approval_config` or admin; publish methods = `group_approval_publish`)

- `get_matrix(company_id=None)` → `{areas:[{key,name,icon,rows:[{process_key,name,status:live|draft|needs|soon,route_labels,applies,sub,version,fast,money,workflow_id,needs_people:int}]}], attention:{count,rows}, presets:[…]}`. `status`: `soon` when `process.connected` false; `needs` when the published version's coverage scan has gaps; `live` when published; `draft` otherwise.
- `create_workflow(preset_key, process_key, company_id)` → workflow + draft version from `data/presets.xml`.
- `get_workflow(workflow_id)` → `{workflow, draft:{version_id, draft_revision, definition}, published:{…} or null, capabilities (from adapter, or the generic capability set for unconnected processes), scope_options (see §3.4), roles, example_defaults}`.
- `save_draft(version_id, expected_draft_revision, definition, meta)` → validates via `definition.validate`, bumps `draft_revision`, returns `{draft_revision, summary, route_labels, errors, warnings}`. Concurrent edit → error "This workflow changed while you were editing. Reload to see the latest."
- `preview(version_id, example)` → `engine.preview` result (no writes).
- `check_coverage(version_id)` → `engine.validate_for_publish` coverage part, with per-scope rows `{scope_key, label, headcount, issues:[{msg, fix:{kind:'assign', role_key, scope_key}}]}`.
- `publication_preview(version_id)` → `{diff:[{kind:added|changed|removed, title, text}], affected:[{label, follows:bool}], in_progress:int, errors, warnings}`.
- `publish(version_id, expected_draft_revision, effective_from, reason, confirmations)` → engine.publish.
- `get_people(company_id)` → roles × scopes grid, gaps, delegations. `set_responsibility(company_id, role_key, scope_key, user_id, backup_user_id, date_from, note)`, `clear_responsibility(...)`. `user_options(term, role_key)` → rows with `eligible` bool + `needs_permission` reason (user lacks read access to the process model: use `self.env['ir.model.access'].check(model, 'read', raise_exception=False)` as that user).
- `list_delegations(company_id)`, `set_delegation(vals)`, `end_delegation(id, note)` (own → self; others → admin group).
- `get_history(company_id, kind=None, cursor=None)` → events in plain words.
- `get_scheme_panel(process_key, scope_key, company_id)` / `set_scheme_binding(process_key, scope_key, selection, expected_revision)` → the Inherited/Shared/Custom data + exceptions (bindings at `scope_key` and its `|division:` children).

### 3.3 Facade `pb.approval.inbox` (runtime; gate = internal user; every method delegates to the engine which re-checks eligibility)

- `list_requests(tab, filters, cursor)` → cards `{id, process, icon, title, sub, amount, currency, count, submitted_by, submitted_at, due_at, state, mine, route:[{title,status}], waiting_for, badges}`; `mine` = an open seat whose `acting_user_id` is me. Amounts grouped by currency in the summary, never summed across.
- `get_request(id)` → drawer payload (facts, evidence, steps with seats, decisions, conflict/exception info for me, allowed actions).
- `decide(id, step_key, action, reason, expected_lock_revision, idempotency_key)`; `repair(id)`; `cancel(id, reason)`; `ask(vals)` (generic request create + submit).

### 3.4 Additive engine methods (in `biz_approval_workflow`, bump its version)

- `biz.approval.adapter.mixin._approval_scope_options(self, company)` (@api.model, default: `[]`) → `[{level:'division', label:'Division', options:[{key:'division:<id>', label}]}, {level:'scheme', …}, {level:'kind', options:[{key, label}]}]`. `pb_approval_config` always adds the division level itself from `pb.division`; adapters add more. Bindings are written with `scope_key` = joined selected levels in the engine's canonical order (scheme|division).
- `biz.approval.engine.summary(definition)` and `route_labels(definition)` exposed as `@api.model` so the client can call them if the mirror ever disagrees.

### 3.5 Seeds

- Roles (`data/roles.xml`): `hr_lead` (HR lead, division-required), `finance` (Finance approver, fallback), `payroll_mgr` (Payroll manager, fallback), `director` (Country director, fallback), `scheme_owner` (Scheme owner, fallback), `budget` (Budget holder, division-required), `signatory` (Bank signatory, pool), `access` (Access team, fallback). Descriptions in plain words as in the POC.
- Processes (`data/processes.xml`): the 40 POC rows (`P.catalogue` in data.js): key, name, area, `money`, `model_name` where known (`hr.payslip.run`, `hr.formula.config`, `pb.records.apply`, `pb.pay.delivery`, `hr.attendance.weekentry`, `pb.pay.change`, `hr.overtime.request`, `hr.leave`, …; leave blank where no model exists yet). `connected` stays false until an adapter claims the key.
- Presets (`data/presets.xml`, JSON definitions): Officer → HR → Finance; Manager, then HR; Joint sign-off; Route by amount; Four-eyes; Start blank.
- Per company (install hook + migration + `res.company.create` override): a published `generic` workflow "Other request" (one `approve` step, role `approver`, company scope) + company-default binding; responsibility `approver@company` = the company's first admin user (the user that installed, else `base.user_admin`). Idempotent.

### 3.6 Home lens replacement

Edit `pb_home_hub`: add `pb_approval_config` to `depends`; in `home_hub.js` replace the `PbApproval` import with `import { PbInbox } from "@pb_approval_config/js/inbox"`, register `{key:"approvals", icon:"inbox", label:_t("Approvals"), Component: PbInbox, groups: []}`; set `APPROVAL_GATE = []` with a comment (kept as an export because `home_hub_palette.js` imports it); update the pb_home_hub test that asserts the gate. In `pb_hub/static/src/js/hub_palette_entries.js:104-106` point `approvals` at `{xmlid: <home hub xmlid>, lens: "approvals"}` with `groups: []`, and add `approval_matrix` (label "Approval Matrix", sublabel "Settings", icon `workflow`, tag `pb_approval_matrix`, groups `[biz_approval_workflow.group_approval_config]`). Leave `wf_approvals` (P5). `pb_approval` stays installed but unreferenced from Home (P3 retires it).

## 4. UX contract (port from the POC; these are the acceptance details)

- Matrix rows: name, fast-lane chip when the published route is fast, "2 people recommended" grey chip for `money` rows, route sentence with arrows, applies-to + sub-line, status pill, version, chevron. Attention bar "N processes need people" filters to `needs`. Search + area chips + status chips. Empty state copy from the POC.
- Builder header: back chip to Matrix, editable name (blur saves), Draft/Published badges, scope chip, "Saved just now / Saving… / Couldn't save · Retry".
- Sentence panel updates on every change (client mirror), reconciled with the server's on save.
- Step card: number, title (editable), kind line, "Who decides" chip opens the picker, resolved names for the current example (with covering-for / backup), "Include this step" row with amount select (when tiers on) and condition select, move up/down/remove, joint seats with Everyone/Any one segment. Notify card dashed. Fast card teal with the explanation. Removing the last decision step switches to fast (toast).
- Add-step menu: seven items exactly as the POC (No approval needed enabled everywhere).
- Tiers panel: switch, fact select from `capabilities.facts` (decimal ones), ladder bands highlighting the example's band, currency note.
- Picker drawer: five cards; role form with scope + "currently assigned" per scope (+ Assign door); people list with Needs permission badge and Everyone/Any one; team select; manager/skip note for batch processes (from `capabilities.manager_mode`); "This step will go to" preview.
- Safeguards: four cards as POC (Who may not approve? incl. self-approval exception summary; What must be attached?; When is this due? with calendar; If it is late? with the "never approved automatically" note).
- Try an example: fields from `capabilities` (unconnected processes: division, amount, prepared-by only); result badge; via line; exsteps with due dates; issues with fix buttons that actually act (`assign` → assign drawer; `go people`; `use backup`; `turn independence off`); "Why this route?"; "Check whole coverage".
- Review & publish: What changes; Who is affected; coverage panel with re-check and inline Assign; right column with warnings as tick boxes ("Tick each one to confirm… Nothing here stops you; the business knows best."), when-it-starts, reason, in-progress count, Publish button enabled only when every warning is ticked and there are no errors; success card with three doors.
- People & backups: grid, gaps in rose with Assign, hand-over rows with switch and dates, "I'm away" primary button and drawer with the seat-clash note when relevant.
- Inbox: hero with Workflows door (config group only); tabs with counts; filters (process area, division, due); cards with `mine` ring; drawer per POC; decision modals with reason gates (exception ≥12 chars, send back/reject ≥6) and consequence copy; "Ask for a sign-off" door; blocked request shows the fix door.
- Responsive: ≤1100 px single column with example below; 390 px per the POC's phone view.
- Copy: every string through `_t`; nothing internal (no model names, state keys, "lock", "RPC"); no "Odoo".

## 5. Safety rails

1. All authority is server-side in the engine; the facades only shape data and re-check the gates.
2. `view as` from the POC does **not** exist in the product; the inbox is always the logged-in user.
3. No `sudo()` in facades except the reads the audit console pattern allows (user list, avatar).
4. Saving a draft never publishes; publishing never rewrites a published version.
5. The Home lens must never render two "Approvals" buttons (no registry double-registration).

## 6. Tests

| ID | Scenario |
|---|---|
| U01 | Static contract: assets order, every `ic()` key exists, no hex/emoji/"Odoo" in shipped JS/SCSS/XML/po msgstr, client-action records match registered tags, every palette door and Settings card xmlid resolves |
| U02 | `get_matrix` gate; rows for all 40 processes; statuses computed (generic=live, others=soon/draft) |
| U03 | `create_workflow` from each preset yields a valid draft (no errors) |
| U04 | `save_draft` stale revision refused; valid save returns summary equal to engine summary |
| U05 | `preview` returns people for role steps using seeded responsibilities; missing division person → issue with `assign` fix |
| U06 | `check_coverage` lists gaps; after `set_responsibility` the gap clears |
| U07 | `publish` refused without confirmations; succeeds with them; matrix status flips to live; History has the event |
| U08 | `set_responsibility` overlapping single holder refused; `user_options` marks a user without model access as needs_permission |
| U09 | Delegation create/end; inbox `mine` reflects covering |
| U10 | Inbox: `list_requests('mine')` shows only my seats; another user sees nothing; `decide` through facade records a decision; exception path requires reason |
| U11 | `ask` creates + submits a generic request routed by the seeded default; company admin sees it as mine |
| U12 | Seed idempotency: running the hook twice creates nothing new; a new company gets its default |
| U13 | Vietnamese `.po` complete, no "odoo" in msgstr, placeholders intact |

## 7. Test, validate, and the deferred deploy (ledger AM14: the live box is down; work locally)

1. Commit per feature (seed + facades; matrix UI; builder; people/history; inbox; home lens swap; i18n).
2. Tests: `/Users/adity/odoo19/runtests.sh pb_approval_config` (drops/creates the db, installs the module chain, runs `--test-tags /pb_approval_config`); also re-run `runtests.sh biz_approval_workflow` after your additive engine change. All U-cases and all T-cases pass; paste both summary lines.
3. Chrome MCP against the local server (`cd /Users/adity/odoo19 && venv/bin/python odoo/odoo-bin -c odoo-local.conf -d <db>` — see its README; log in as admin) — golden path: Settings → Approval Matrix opens (tile at seq 40) → row "Other request" opens the builder → add a Finance step → tiers on → example → coverage → publish with confirmations → Home → Approvals lens shows the inbox → Ask for a sign-off → request appears in My turn → approve → Done tab → History shows both events → 1024 and 390 widths. Delete screenshots.
4. Do NOT attempt the live server unless `ssh -o ConnectTimeout=8 Payobook19v2 true` succeeds at that moment. If it does, follow the ledger deploy contract for `pb_approval_config`, `biz_approval_workflow`, `pb_home_hub`, `pb_hub`, `pb_import_kit` (if icons added) on every DB with tenant backups first, asset purge + `web.assets.version` bump, and version/hash parity. Otherwise end your report with the **deploy checklist** for the wave.

## 8. Report back

Files, RPC surface, test counts + summary line, per-DB deploy results with `EXIT=` lines, Chrome golden-path result (what you saw, in words), deviations, ledger entries appended, commit hashes, and anything P3 must know (e.g. the exact `ApprovalSchemePanel` props and the `_approval_scope_options` shape you implemented).
