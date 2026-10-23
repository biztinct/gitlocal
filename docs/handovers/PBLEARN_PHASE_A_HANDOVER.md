# pb_learn Phase A — Implementation Handover (Run A1 + Run A2)

**Read first:** `docs/handovers/PBLEARN_LEDGER.md` (conventions + verified plumbing —
do not re-derive anything listed there), then skim `docs/tutorial_poc/design_v2.html`
§2–§7 for intent.

**Mission:** create the `pb_learn` module at repo root by porting
`/Users/adity/Documents/GitHub/health19/addons/health_learn` (v19.0.5.0.0) to Payobook,
scoped to the **Pay Run** section: 7 sidebar leaves + the import-wizard sub-screen.
Always-on Coach on those screens, Journey client action with 4 full lessons + 3 outlines,
2 full fixture missions + 1 outline, ~14 intents, columns, glossary, tenant slots,
server-side progress/events/confidence, generated data + `i18n/vi_VN.po`, tests, and the
authoring pipeline under `docs/tutorial_poc/author/`.

## Binding non-goals (Phase A)

- NO live missions runtime (`kind='live'` exists in the selection, the runner refuses it).
- NO LLM anywhere: port `_resolve_hook` as the no-op it is; **do not port `_compose`,
  `_provider`, `_corpus`, `_scrub` or any `hr.ai`/provider import** — replace the
  compose path with the deterministic fallback. (health_learn's `_capability`, scoring,
  suggestions, columns etc. all stay.)
- NO changes to pb_coach, pb_payroll_ai_insights, pb_demo, or any existing module's
  Python/JS. The ONLY edits outside `pb_learn/` and `docs/` are **additive
  `data-coach` attributes + one class hook** in the six templates listed in §A1-3.
- NO live-value resolver (Phase B). Lesson/coach numbers are static authored content.
- Do not modify the v1 prototype files (`docs/tutorial_poc/index.html, app.js, data.js,
  styles.css`) — the new authoring source lives in `docs/tutorial_poc/author/`.

---

# Run A1 — module port + anchors + wiring

## A1-1 · Copy and re-point the module

Copy `health19/addons/health_learn` → `gitlocal/pb_learn`, then apply this re-point map
(grep for every left-hand term; the port is mechanical, keep diffs minimal):

| health_learn | pb_learn |
|---|---|
| module name `health_learn`, "CareJioX Learn" | `pb_learn`, "Payobook Learn" |
| manifest depends `health_cms_sidebar, health_care_command, health_care_command_channels, health_web_leads, health_theme, health_user_admin` | `pb_sidebar, pb_theme, pb_hr_payroll_base, pb_payrun_wizard, pb_payruns, pb_payslip_review, pb_import, pb_import_wizard, pb_payrun_ledgers` |
| `cms.sidebar.item` | `pb.sidebar.item` (same `get_sidebar_data()` API — ledger) |
| anchor attribute `data-a` | `data-coach` (single constant in spotlight.js + anywhere hardcoded; also update anchors.json tooling + tests) |
| capability groups (their crm/nurse/om/owner logic in `learn_intent._capability`) | `operator` → `pb_hr_payroll_base.group_payroll_base_officer`; `manager` → `group_payroll_base_manager` OR `group_payroll_final_approver`; `owner` → `group_payroll_super_admin`; `no_access` → none of these |
| `_CLINICAL_MARKERS` deny list + `clinical` intent | `_ADVICE_MARKERS` (tax/legal-advice): "trốn thuế", "khai thấp", "giảm đóng bhxh", "lách", "under-declare", "avoid tax", "evade", "reduce bhxh legally" → fixed `compliance` intent (teach where rates live + who owns policy; never advise minimising obligations) |
| author group privilege `health_base.res_groups_privilege_healthcare` | attach `group_learn_author` to category `base.module_category_human_resources` (simple `category_id`) |
| `learn.station.line` selection (daily/reach/ops_*/fin_*) | `payrun` (Phase A; keep the selection extensible) |
| `learn.station.section` selection (crm/ops/clinical/finance) | `payroll` (Phase A) |
| `learn.mission.kind` selection full/outline | full/outline/**live** (add now; `openMission`/runner raises a friendly "not available yet" for live) |
| tenant-override note examples | Payobook slots (§A2-2) |
| sidebar leaf `data/learn_sidebar_item.xml` (cms item, fa icon) | `pb.sidebar.item`: section `ref="pb_sidebar.sec_payrun"` (use full xmlid ref), `sequence=90`, `icon` **compass** (fixed icon set — ledger), `action_tag='learn_journey'`, name "Learn" / to be translated "Học cùng Payobook" via record translation in .po |
| scss token usage | keep `--vuf-*` (emitted by biz_theme here too); visually check against `#5A4BB0` system, adjust only if a token is missing |

Manifest data order (keep health_learn's): security → strings → glossary →
tenant_slots → stations → lessons → intents → screens → columns → missions →
learn_actions → learn_sidebar_item → content views → override views → menus.
Assets: `web.assets_backend` only, same file order as health_learn.

**Data files in A1 are placeholders** — minimal valid records so the module structure is
complete (`-u` would load). Run A2 regenerates them from the authoring source. Keep the
`GENERATED FILE` banner discipline from day one: banner reads
`Source: docs/tutorial_poc/author/`.

## A1-2 · Engine specifics

- `engine/spotlight.js`: change the anchor lookup constant to `data-coach`. Everything
  else (hole + card placement right→left→below→above, playbar reservation, Trace,
  flashRing returning false for the Coach's honest "not on this screen") ports as-is.
- `engine/screens.js`: replace health19's 31 practice renderers with **Payobook Pay Run
  replicas**. Port them from the v1 prototype (`docs/tutorial_poc/app.js`, `SCREENS`
  object) — dashboard, runpayroll, payruns, payslips, import — and add thin replicas for
  importwizard, fullfinal, proration, retro (KPI strip + table, one screen each; the
  three ledgers may share one renderer parameterised by screen key, mirroring the real
  shared template). Match health_learn's `shellHTML(screen, opts)` / `blockedHTML()`
  contract so journey.js works unmodified. Every referenced control carries
  `data-coach="<anchor>"` with anchors named in anchors.json as kind `practice`.
- `engine/fixture.js`: placeholder in A1 (regenerated in A2).
- `coach/`: port as-is (bodyHTML shared between dock and drawer — do not fork), launcher
  label "Stuck?" / "Cần trợ giúp?", `?` toggle, Esc, no backdrop. The Payobook honesty
  banner text (design_v2 §2): "I guide — you act. I never compute a run, approve a
  payslip or change a record for you." / "Tôi hướng dẫn — bạn thao tác. Tôi không bao
  giờ tự tính lương, phê duyệt phiếu lương hay sửa dữ liệu thay bạn."
- Launcher placement: bottom-right stack ABOVE the PayAI pill (`.payai-pill` is fixed
  bottom-right). Give the FAB a bottom offset that clears the pill (~84px) and verify
  the demo pb_coach FAB (`.pbc-fab`) doesn't collide — if pb_coach's FAB is present
  (demo users), OUR launcher hides via a body-class check `pb-demo-user`… **no** — demo
  users must get the Coach too (design: coexist). Instead offset ours higher (stack:
  PayAI pill, pb_coach FAB, Learn FAB) using CSS only. Do not modify pb_coach.

## A1-3 · Anchors on the real templates (additive only)

Add `data-coach` attributes (names exact; ■ = already exists, leave untouched):

| Template | Anchors |
|---|---|
| `pb_payrun_wizard/static/src/xml/payrun_wizard.xml` | ■pw-division ■pw-compute · `pw-rail` (.pw-rail :17) · `pw-scope` (.pw-grid2 :48) · `pw-summary` (.pw-sec :66) · `pw-result` (.pw-result :79) · `pw-pills` (.pw-statpills :83) · `pw-exceptions` (.pw-list :96) |
| `pb_payruns/static/src/xml/payruns_kanban.xml` | `pk-kpis` (.pbk-kpis :8) · `pk-run` (:16) · `pk-tabs` (.pbk-tabs :23) · `pk-datechips` (:31) · `pk-divchips` (:44) |
| `pb_payruns/views/hr_payslip_run_kanban.xml` (arch = DATA, note in report that `-u pb_payruns` is needed) | `pk-card` on the card root (pattern kind via t-attf if a record id is available, else static on the card container) · `pk-card-actions` on the action footer (:33-64 region) |
| `pb_payslip_review/static/src/xml/payslip_review.xml` | `ps-runsel` (.psr-runsel :14) · `ps-kpis` (:23) · `ps-chips` (:32) · `ps-list` (:42) · `ps-detail` (:61) · `ps-status` (:75) · `ps-breakdown` (.psr-bk :82) |
| `pb_import/static/src/xml/import.xml` | `im-kpis` (:17) · `im-cta` (.pbm-cta :26) · `im-launches` (:41) · `im-pipe` (:56) · `im-batches` (:68) |
| `pb_import_wizard/static/src/xml/import_wizard.xml` | `iw-steps` (:17) · `iw-source` (:36) · `iw-review` (:82) · `iw-fixrows` (:117) · `iw-outcome` (:156) · `iw-commit` (footer primary :163-170) |
| `pb_payrun_ledgers/static/src/xml/ledger.xml` (SHARED by 3 screens) | `lg-kpis` (.ppl-kpis :18) · `lg-facets` (:36) · `lg-rows` (:97 table) · `lg-openfull` (:107) |

Register every product anchor in `pb_learn/static/src/anchors.json` with
`{screen, file, desc, kind:"product"}`; ledger anchors get kind `"pattern"` with a note
that three screens share them. Port `tests/test_anchor_registry.py` to enforce
registry↔template↔content in both directions **plus** a whitelist for the pre-existing
`data-coach` anchors that belong to pb_coach (fs-*, dash-*, imp-*, map-*, grid-*,
find-panel, palette, payai-pill, pw-division, pw-compute — the last two are BOTH
pb_coach's and ours; registry owns them, whitelist covers the rest).

## A1-4 · Screens + resolution records (real content, not placeholder)

`data/learn_screens.xml` (these 8 are worth writing correctly already in A1):
keys `runpayroll, payruns, payslips, import, importwizard, fullfinal, proration, retro`;
`sidebar_key` = the `pb_sidebar.item_*` xmlids (ledger); `importwizard` has NO
sidebar_key and instead `action_tags='pb_import_wizard'`. Suggest_ids wired in A2.

## A1-5 · Self-check & report (Run A1)

- `python3 -m py_compile` every .py; `python3 -c "import xml.dom.minidom, glob; ..."`
  well-formedness on every .xml; no references to `health_`/`cms.`/`carejiox`/`data-a`
  remain (`grep -rn` proof in report).
- Report back: file tree created, the re-point diffs of the 5 trickiest files
  (learn_intent.py capability/deny-list, learn_station.py sidebar call, spotlight.js,
  coach_patch, manifest), anchors added per template, anything you could not verify
  without a server, gotchas → append to the ledger.
- Commit: `feat(pb_learn): port health_learn skeleton — engine, coach, journey, models (Phase A1)`
  and a second commit for the anchor additions to the six modules.

---

# Run A2 — authoring source, content, generator, fixture

## A2-1 · Authoring source at `docs/tutorial_poc/author/`

Copy from `health19/docs/tutorial_crm/`: `tools/dump_content.js`,
`tools/gen_learn_data.py`, `tools/check_contract.py` → `docs/tutorial_poc/author/tools/`.
Re-point the generator: module path `pb_learn`, banner
`Source: docs/tutorial_poc/author/`, `SIDEBAR_KEYS` map = our stations→`pb_sidebar.item_*`,
model prefixes unchanged (`learn.*`), .po path `pb_learn/i18n/vi_VN.po`, attribute
`data-coach` in the anchor-lint config.

Create `author/practice-data.js` + `author/data.js` in **schema 1.1** (header block
identical in shape to health19's data.js:1-28) + `author/contract.json`.

## A2-2 · Content (the heart of A2) — from design_v2.html §5

Migrate the v1 content (`docs/tutorial_poc/data.js` — L1 steps, quiz, mission m1/m2
material, QA answers, glossary, EMP/RUN numbers) into schema 1.1, then complete it:

- **Stations (7)** line `payrun`: runpayroll (lesson L1) · payruns (lesson L2) ·
  payslips (lesson L3) · import (lesson L4) · fullfinal/proration/retro (outlines —
  v1 already has their bilingual outline copy; reuse it).
- **Lessons:** L1 8 steps (port from v1, re-anchor to the replica anchors); L2 "The
  board and the gates" ~7 steps with a `pipeline` moment using the REAL state chain
  draft→level0→level1→level2→done + rejection-testimony step; L3 "Read a payslip like an
  auditor" ~6 steps with a `calc` visual over Mai's numbers; L4 "Import with confidence"
  ~6 steps incl. consequence card on Commit. One quiz each (scenario judgement, all
  options with feedback; L1's quiz exists in v1).
- **Worked example** in practice-data.js: the v1 numbers verbatim (Mai: 12,000,000 base /
  780,000 allowance / 1,500,000 OT / gross 14,280,000 / BHXH 960,000 / BHYT 180,000 /
  BHTN 120,000 / taxable 2,020,000 / PIT 101,000 / net 12,919,000; June net 12,064,000;
  Hùng OT 4,200,000 vs June 1,100,000; run: 48 employees, net 612,480,000, config
  HOASEN_RETAIL_END v12). Every calc block reuses these — never invent new numbers.
- **Missions:** m1 + m2 full (v1 flows, expressed as schema-1.1 step machines — one
  decision per step; m1's consequence card + Hùng anomaly + recovery; m2 adds the
  written-reason reject branch and an undo step), m3 outline. `confidence_key`:
  run/approve/import.
- **Intents (14)** exactly the design_v2 §5 table: whatpage (dynamic screen_blurb),
  whatnext (dynamic next_step), needreview (calc), whydiff (calc), approve
  (capability-gated: any + no_access refusal/who/how), reject, checkfinal, fixerror
  (show_me across screens), affectrun, confidence, bhxh (+simpler), prorata, retroq,
  practice. Phrases EN+VI mixed. `screens` scoped per table; suggest_ids per screen
  (3–5 chips each).
- **Columns (~30):** every KPI tile/chip on the 8 replicas (e.g. payruns: "In pipeline",
  "Awaiting your approval", "Net paid"; payslips chips; import score…).
- **Glossary (9):** from v1 + cycle/proration/retro.
- **Tenant slots (8):** payDay, hrTierName ("HR review"/"HR soát xét"), gmTierName,
  importCutoff, bankFileFormat, companyDisplayName, payrollSupportContact,
  standardWorkingDays — defaults bilingual; overrides fill slots only.
- **contract.json (~12 checks)** per design_v2 §7: state selection keys + level0
  ordering (kind `contains` on pb_payruns/models/hr_payslip_run.py), reject fields,
  4 group xmlids + demo group (kind `xmlids`), 7 sidebar leaf xmlids, ledger action tags
  in pb_payrun_ledgers/views/ledger_actions.xml, PayAI `_KNOWN_TOURS` tuple unchanged,
  VI .po spot-checks ("Chạy bảng lương"). Every entry: id/why/kind/file/expect/taughtIn.

## A2-3 · Generate + verify

`node author/tools/dump_content.js` → JSON; `python3 author/tools/gen_learn_data.py` →
pb_learn/data/*.xml + i18n/vi_VN.po + engine/fixture.js + practice anchors merged into
anchors.json; then `--check` clean; `python3 author/tools/check_contract.py` all green;
py_compile + XML well-formedness again. The A1 placeholder data files must be fully
replaced by generated ones.

## A2-4 · Self-review before reporting (both runs)

Walk design_v2.html §11 acceptance and mark each line done / not-verifiable-locally /
missed. Re-grep for banned leftovers (`health_`, `data-a`, `_compose`, `clinical`).
Confirm mission steps each carry exactly one decision. Confirm every quiz option has
feedback. Confirm VI exists for every translatable (generator enforces; state it).

Report back (single message): what was built per section above, deviations + why,
the §11 acceptance walk, untested-locally list, ledger additions.
Commits: `feat(pb_learn): Phase A2 authoring source + generated Pay Run content`
(+ separate commit if fixture/screens changed materially).
