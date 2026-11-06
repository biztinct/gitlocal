# LEARNREV P2 — the Guide panel and field cards on the screen (handover for Opus)

Program: `docs/handovers/learnrev/LEARNREV_PROGRAM.md` (standing rules verbatim there — design bar, white-label,
plain English, lessons-follow-screens, commits, deploy). Ledger: `LEARNREV_LEDGER.md` (all rows; LR-R1, LR-R3, LR5,
LR13, LR19, LR23–LR25, LR27 matter most here). Design page: `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html`,
section "Option C" — the Component treatment mock-up with the Guide panel open IS the target look (six sections,
(i) on each column, "Right now" with buttons). P1 built the data (`learn.guide`, `P1_REPORT.md`); P2 draws it.

Work in the git worktree you are given (branch `learnrev-p2` from the 19.1 tip). **No deploy in this phase** (Fable
merges after the P1 deploy lands, then deploys). Tests on a clone of payobook on the server (clone by dump, AI
connection OFF, drop with `--force` — LR16/LR17/LR26).

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Measured against Xero's help panel, Gusto's
field "?" and Stripe's reference, never stock back-office. **Hero moment:** on Component treatment, press the (i)
beside "Pay role" and a card appears beside the real row: what it is, the six choices each with when to pick it, how
it is filled, where it is used (33 places, folded to the top six with "and 27 more"), what changes if you change it.
Second hero: "Right now" lists "3 rows still need your answer on Pay role: Loan Installment, KPI Bonus, Incentive"
with a **Show** button that filters the board. **Zero dead ends:** every section has a designed empty state ("Nothing
needs you here", "No lesson for this screen yet, here is the map", "Loading the board…", "No scheme selected: pick one
above"); a failed call shows its reason and a Retry. Plain screen words everywhere; never the word "Odoo". Payobook
design system (indigo `#5A4BB0`, soft `#EDEAF8`, ok `#2E7D4F`, warn `#D97706`, bad `#DC2668`, white cards, Lucide
icons only via the existing `ic()` sprite, no emoji, no gradients). Motion: 160 ms fade-up on a card, respect
`prefers-reduced-motion`. Keyboard: (i) buttons are real `<button>`s, Esc closes a card then the panel (the existing
Escape ladder, coach.js:461-500), `?` still toggles the panel. Score every bullet 1–5 in the report.

## 1. Scope
- **S1 Docked Guide panel.** The existing drawer (`.lrn-drawer`, host `.lrn-coachhost`) gains a docked mode: on
  viewports ≥ 1280 px (biz `lg`, `biz_breakpoints.scss:14-17`) an open drawer becomes a full-height right column of
  420 px that the page flexes around; below 1280 px the floating card stays as today. One drawer, one host, one chat —
  **no tabs** (ONECHAT ruling). Mechanics in §3.
- **S2 Six sections** drawn ABOVE the chat inside the drawer, each a collapsible card, in this fixed order:
  **This screen · Right now · Fields on this screen · Tasks · Understand · Ask** (Ask = the existing one chat, which
  stays at the bottom with its composer always visible). Content comes from one call,
  `learn.guide.rpc_guide(screen_key, args)` (shape: `learn_guide.py:192-207`). Section rules in §4.
- **S3 (i) field cards.** A small (i) button beside every column header / label a manifest names, injected by pb_learn
  at runtime (no product template imports pb_learn), opening a card (clone of the glossary hovercard mechanism,
  `engine/glossary.js:189-255`) with the field's card from the Guide JSON. §5.
- **S4 Right-now actions wired** end to end: `filter` (board chips), `open` (hub + focus), `open_record`. Close the
  three client/provider gaps P1 left (§6).
- **S5 Explain / nudge / whatnext re-pointed** to the Guide so the three surfaces stop showing one sentence
  (LR-R1, G1, G25, LR5). §7.
- **S6 Screen resolution for Mapping › Connections** (LR24): the `mapping` learn screen gets
  `pb_mapping_studio:desk` as its first place and its blurb/next describe Connections (the default tab); Journey keeps
  resolving to `mapping` too. Anchors laid where P1 found none (LR23): Connections desk, Studio Table view, the
  Pulse "Needs you" line (manifest says `dash-hero` but the glance sits outside it — fix the anchor to a new
  `dash-needs`). Dead `fs-*` anchors that render nowhere are retired from `anchors.json` and the formula manifest.
- **S7 Feature switch** `pb_learn.guide_enabled` (learn.settings SWITCHES + `bootstrap` key `guide`), default OFF;
  the Learn › Settings lens shows it; when OFF the drawer behaves exactly as today. Fable turns it ON for payobook at
  deploy. §8.
- **S8 Eight screens**, treatment first end to end (S1–S7 on treatment, committed), then mapping (Connections),
  payruns, runpayroll, payslips, approvals, dashboard, formula. Where a screen has no provider, "Right now" shows the
  designed empty state and the static `next_step` sentence as a fallback line (never both the sentence and a live
  list).

## 2. Binding non-goals
No change to the Journey/Library page (P3), lesson or walkthrough content and the scenario engine (P4), PayAI tiers,
gates, runner, catalogue (Access ruling stands: the Guide never links to Access and delegations — any manifest door or
`path` into `pb_settings_hub` access/nav tabs is dropped client-side too, add a test), the router's command/data
paths (only the whatnext/explain branches named in §7), no new stored fields, no sudo, no deploy. Do not touch the
five `body:has(.lrn-coachhost)` bottom-padding rules in other modules (A3 list in §3; P5 cleans them).

## 3. Docked panel — mechanics (verified facts)
- Host: `coach_patch.xml:11-16` inserts `<CoachHost/>` after `MainComponentsContainer`; host CSS `.lrn-coachhost {
  position: fixed; inset: auto 0 0 auto; z-index: 1040; pointer-events: none }` (coach.scss:10-21); drawer
  `.lrn-drawer` fixed, `--lrn-dw: min(480px, …)` with chat (coach.scss:92-114, 573-587).
- Page body: `pb_sidebar` wraps the action manager: `.pb-layout-wrapper { display:flex } > .o_action_manager
  { flex:1 1 auto; min-width:0 }` (pb_sidebar.scss:13-24); the left rail reserves width by being a flex child; biz
  rail mode reserves by `padding-left` on the wrapper (biz_breakpoints.scss:40-54) — **clone that**: when docked,
  add `body.lrn-docked` and in pb_learn's scss `body.lrn-docked .pb-layout-wrapper > .o_action_manager { padding-right:
  var(--lrn-dock-w, 420px) }` plus `.lrn-drawer { position: fixed; top: <navbar height>; right: 0; bottom: 0; height:
  auto; width: var(--lrn-dock-w); border-radius: 0; border-left: 1px solid … }`. Use `@media (min-width: 1280px)`
  only; below it nothing changes. The FAB (`.lrn-fab`) is hidden while docked-open (the panel header has Close).
- Collisions (all fixed elements listed in the P2 facts): PayAI pill stands down when pb_learn is present
  (ai_insight_chat.js:676-683); the scenario overlay card placement reads `window.innerWidth` (scenario_overlay.js:
  458-490) — subtract the dock width when `body.lrn-docked` (one-line change there); `.lrn-glosscard` z 1080 sits above
  the drawer (fine); `.pbdc-disclaimer` (demo, bottom-left) does not collide; the Mapping Studio FAB offset rule
  `.o_web_client:has(.pbim.pbms .pbms-wrap) .lrn-fab { right: calc(var(--mc-col-w) + 26px) }`
  (mapping_studio.scss:83-87) stays for the floating mode.
- Not HubShell: Mapping Studio (`.pbim.pbms`, flex column), Formula Studio (`.pbfs`), Settings — the padding-right on
  `.o_action_manager` covers them all, which is why the dock is NOT the HubShell `dock` slot (hub_shell.scss:426-436,
  268 px, per hub, hidden < 1099 px).
- Remember the user's choice: docked vs floating toggle in the panel header (`localStorage pbLearnDock`), default
  docked on ≥ 1280.

## 4. The six sections (data → UI)
Fetch once per screen change (`_ground`, coach.js:439-450) when the flag is on and the screen has a manifest:
`orm.call("learn.guide", "rpc_guide", [screenKey, args])` where `args` = `{config_id}` on Mapping Studio tabs
(see §6.1), `{}` elsewhere. Cache per screen key + args for the drawer's life; "Right now" refreshes on every open
and after any action the panel itself triggered. Render with the same string helpers the drawer uses (`T()`, `tx()`,
`ic()`); all new chrome strings are content-plane `chrome` keys in `docs/tutorial_poc/author/data.js` (LR13 rule),
regenerated with the pb_learn vi_VN.po restore dance (LR28).
1. **This screen** (open by default on first visit of a screen, then remembered per screen in localStorage):
   `screen.purpose`; "You are here" strip from `screen.path` (each chip opens via `openHub(action, path.open)`),
   then `before` (grey, "came from") and `after` (indigo outline, "next") chips with their `why` as title.
2. **Right now** (always open when it has items): numbered rows `text` + severity dot + one button per `action`
   (§6). Empty state: the `ok` item the provider returns, or "Nothing live for this screen yet" + the static
   `next_step` sentence (fallback line, grey). `missing` reasons render as a quiet note with Retry.
3. **Fields on this screen** (collapsed by default, count badge): one row per `fields[]` entry: `column` (bold),
   one-line `help` (or `how` for derived), expand → the full card (same renderer as the (i) card). A search box
   filters rows when > 6 fields.
4. **Tasks**: `doors.tasks[]` → name + Watch / Try chips (modes), each calling the existing `startScenario(key,
   mode)` (coach.js:1538-1561). Empty: "No walkthrough for this screen yet" + "Open the lesson map" door.
5. **Understand**: station outline summary (`doors.station_name`, duration from the station) + "Open the lesson"
   (openLesson, P0) + `doors.terms[]` as glossary chips (click → the glossary card, `glossaryEntry(key)`), +
   "Mistakes this prevents" from the station outline (bundle `stations[].outline.mistakes`).
6. **Ask**: the existing chat, unchanged, but its suggestion chips now come from the screen's `suggest` AND two
   generated questions ("What reads the pay role?", "Why does <first needs-answer row> need my answer?") built from the
   Guide — authored as chrome templates with `%s`.

## 5. (i) field cards — mechanics
- **Finding the header.** For each `fields[]` entry with an `anchor`, find the anchor element
  (`[data-coach="<anchor>"]`), then the first descendant `th, label, .pbd-fig-l, .pbim-gl-l, .pbr-lbl, h2, h3, h4,
  span` whose normalised text (tags stripped, `’`→`'`, whitespace collapsed; same `norm()` as
  `pb_learn/tests/guide_truth.py:25-29`) equals `column` (EN or VI). Append `<button class="lrn-i" type="button"
  data-learn-field="<key>" aria-label="<T('explainField')> <column>">i</button>` (16 px round, Lucide "info" from
  `ic()`). Idempotent: skip when the header already holds `.lrn-i[data-learn-field=key]`. Re-run after OWL
  re-renders: a `MutationObserver` on `.o_action_manager` debounced to 120 ms, scoped to the matched anchor elements.
  Stop propagation on the button's click so sortable headers (payruns.xml:192-195 `t-on-click="sortBy"`) do not sort.
- **Fields without a visible header** (approvals `state` inside the hub, formula Cards-only fields) get no (i) and
  are listed in the Fields section only; the report lists them per screen.
- **The card.** One `div.lrn-fieldcard` appended to `document.body` (clone `glossary.js:189-205` placement, z 1080,
  width 360 px, above or below the button, clamped to the viewport minus the dock). Contents: title `column`;
  `help`/`how`; **Choices** (`choices[].label` bold + `when`; or `values[]` for derived); **How it is filled**
  (`filled_by` + `source_values` chips); **Used by** (first 6 `used_by[].label` as chips + "and N more" expanding);
  **If you change it** (`if_changed`); footer: "Open in the Guide" (expands the Fields row and scrolls to it), "Watch
  this field" only when a scenario step's `anchor` equals the field's anchor (else hidden), and a thumbs pair
  (`lrn-fb`, Lucide thumbs-up/down) that calls `learn.guide.rpc_feedback(screen, field, up)` — a new method that
  writes an aggregate counter only (`ir.config_parameter`-free: a small `learn.feedback` model is NOT allowed —
  content never in DB — so log through the existing `learn.event`/`coach_*` logging seam the drawer uses for
  `coach_open` (`_log`, coach.js) with no free text; P5 reads it).
- Opens on click (not hover); Esc closes (hook into the Escape ladder before the drawer); clicking outside closes;
  only one card open at a time; a glossary card and a field card never show together.

## 6. Right-now actions — close P1's gaps
6.1 **`config_id` for Mapping Studio tabs:** MappingStudio publishes its place at `mapping_studio.js:310-325`
    without the scheme. Add `extra: { config_id: this.state.configId }` to `publishPlace(...)` and read it in the
    drawer (`this.place.extra?.config_id`). `hubPlace` (`pb_hub/static/src/js/hub_place.js:30-51`) must carry an
    optional `extra` through unchanged (add the key; no other hub sets it).
6.2 **`filter` action:** the board has `setFilter(which)` toggling (`component_treatment.js:149-151`) and no prop
    or bus. Add `useBus(this.env.bus, "pb-learn:act", ({detail}) => …)` in `ComponentTreatmentBoard` that SETS
    (not toggles) `state.filter = detail.value` when `detail.kind === "filter"`; the panel triggers
    `env.bus.trigger("pb-learn:act", {kind:"filter", value})`. Precedent for `useBus`: any pb_hub lens.
6.3 **`open` action:** providers emit `ids` and `config_id` (pb_payruns_learn.py:45-47,104-106,152-154;
    learn_right_now.py:129-133) but `openHub` takes `focus` and `context` (hub_nav.js:52-83) and Mapping reads
    `pb_config`/`pb_mode` (mapping_studio.js:176-193). Change the providers: `{'kind':'open','xmlid','lens',
    'lens_key','focus': str(first id) or None, 'context': {'pb_config': config_id} when present}`; the client calls
    `openHub(this.action, {xmlid, lens, lensKey: lens_key, focus, context})`. Runs lands with the card highlighted
    (payruns.xml:292 `focus`); good enough for P2 (opening the peek is P3's call).
6.4 **`open_record`:** `doAction({type:"ir.actions.act_window", res_model, res_id, views:[[false,"form"]],
    target:"current"})` (precedent `payruns.js:709-720`).
6.5 After a `filter` action the panel scrolls the board's chip row into view and re-fetches "Right now" 400 ms later.

## 7. Explain / nudge / whatnext (one sentence, three surfaces — ends here)
- **Explain this screen** (`c-explain`, `explainScreen()` coach.js:1386-1401 → `learn.intent.explain_screen`):
  when the flag is on and a manifest exists, `explain_blocks` (learn_intent.py:611-644) builds: `p` = `purpose`;
  `steps` = the path labels ("You are here: Mapping › Component treatment · next: Pay Run › Run"); up to 3 `p`
  blocks = the first three field cards as "Column: help" lines; `source`. The `ok` block with `next_step` is dropped
  when a provider exists (the live list is in the panel). The chat card gains a door "Open the Guide" that expands the
  panel's This screen section.
- **whatnext intent** (`dynamic: next_step`, `learn_intent._blocks_for` :1188-1195 → `learn_runtime.next_step_live`):
  when the screen has a provider, answer with the right-now items as a `steps` block (text only; the buttons are in
  the panel) + "Open the Guide"; else the static sentence as today. **Router (LR5):** in `learn_helper.route`, the
  whatnext chip label (EN+VI, all 70 intents' labels already in `phrases`) must short-circuit to the guide BEFORE the
  PayAI/model path on a can-act DB — add the check where the command check sits (ONECHAT OC1 rule) and a test that
  "What should I do next here?" / "Tôi nên làm gì tiếp theo ở đây?" route `guide` on every content screen with
  `payai` available.
- **First-visit nudge** (`_pickMoment` coach.js:527-574, `momentHTML` :576-622): title "First time on <screen>?",
  body = `purpose` (not the blurb), buttons **Open the Guide** (opens the drawer docked with This screen expanded) and
  **Not now**; Watch stays only when `doors.tasks` has a watch mode.
- The suggestion chip "What should I do next here?" is removed from the context card when a provider exists (the
  panel already shows it); kept otherwise.

## 8. Flag and bootstrap
`learn.settings.SWITCHES` += `('guide', GUIDE_FLAG)` with `pb_learn.guide_enabled`; `bootstrap` returns `'guide':
_flag_on(...)`; the client stores `bundle.guide`. Settings lens copy keys for the switch (EN+VI). When OFF: no fetch,
no (i), no dock, drawer as today. When ON but no manifest for the screen: no (i), panel shows This screen from the
content blurb + Tasks/Understand from doors + Ask (the Guide call still returns `doors` for manifest-less screens —
`learn_guide.py:175-190`).

## 9. Tests (numbered; all green before the report)
- **T1 node harness** (`pb_payai_actions/tests/js/` pattern, `harness.mjs`; add `pb_learn/tests/js/guide_panel.test.mjs`
  run by a new `pb_learn/tests/test_guide_client.py` via subprocess like `test_onechat_client.py:18-63`): render
  the six sections from a fixture Guide JSON (take `scratchpad p1guide.json`'s `en_US` — copy it into
  `pb_learn/tests/data/guide_treatment_en.json`); assert section order, Right now rows + button kinds, Fields count,
  Tasks chips, empty states for a manifest-less screen and for `missing: ["right_now: no scheme selected"]`;
  `runAction` builds the right `openHub`/bus/doAction calls (stubbed); card HTML for `pay_role` contains the six
  choices and "and 27 more".
- **T2 header finder** (pure function, same suite): `findHeader(root, column)` with the normalisation rules matches
  `Included in<br/>another total` and `Figures don’t add up`; injection is idempotent (second run adds 0 buttons).
- **T3 Python** `pb_learn/tests/test_learnrev_p2.py`: (a) `explain_blocks` on treatment with the flag on yields
  purpose + steps + ≤3 column lines + source and NO `ok` block; with the flag off, unchanged from today;
  (b) whatnext on treatment with a `config_id` returns a `steps` block from the provider; (c) router: the whatnext
  label EN/VI routes `guide` on every content screen with payai available (LR5); (d) `bootstrap()` has `guide` False by
  default and True after `learn.settings.set_switch('guide', True)`; (e) `mapping` screen places start with
  `pb_mapping_studio:desk`; (f) every provider action is one of `filter|open|open_record` with the §6 keys
  (`focus`/`context`, never `ids`/`config_id`); (g) no manifest `path`/door targets `pb_settings_hub` access/nav
  (Access ruling) and the client filter function drops one if fed.
- **T4 truth gate** still 0 errors after the anchor changes (`guide_truth.py`), `test_anchor_registry` green with the
  new anchors and without the retired `fs-*`.
- Existing: pb_learn all, pb_payai_actions node suites (they load the real CoachHost — must still pass with the new
  sections), pb_formula_studio TestLaneLabels/studio_experience, `gen_learn_data.py --check`, `check_contract.py`
  (1 known `grid-hint` failure). Known baselines: test_07b, TestCoach.test_11 only with AI on.

## 10. Browser checks (payobook.com, QA login; headless Chrome on port 9557 with the walk driver; sign in via
`fetch('/web/session/authenticate')`, never a typed password; set `pb_learn.guide_enabled` ON on the CLONE you test
against — never on live in this phase; so run B1–B10 against the clone served on port 8099 with `--http-port` and
the staged addons path, like P1's test run)
B1 Component treatment, ≥1280 px: open the helper → docked column, board narrows, six sections in order, This screen
open with path chips "Mapping › Component treatment" and next "Pay Run › Run"; B2 Right now lists needs-answer /
type-conflict rows with Show/Fix; press Show → the board's "Needs your answer" chip is active and rows filtered;
B3 press (i) on Pay role → card with six choices, "Used by" six chips + "and N more", "If you change it"; Esc closes
the card, Esc again closes the panel; B4 1100 px viewport → floating card, same sections; B5 Vietnamese: switch the
QA user (RPC) → all six section titles, chips and the Pay role card in Vietnamese ("Vai trò trong lương", "Cộng vào
thực nhận"), switch back; B6 Explain this screen → chat card with purpose + path + 3 column lines + "Open the Guide",
no duplicated next sentence; B7 type "What should I do next here?" → the live steps, not the canned sentence (and
not a model answer); B8 Runs board: Right now names an unbalanced/awaiting run, Open lands on Runs with the card
highlighted; B9 first visit of a screen (clear `pbLearnSeenScreens`) → nudge shows purpose + Open the Guide; B10 flag
OFF → no (i), no dock, drawer as before; console clean of errors on every step. Screenshots `p2_b*.png`.

## 11. Precedents (verified)
Drawer render + state: coach.js:210-234 (state), coach.xml:46-120 (drawer/header/body), `_contextHTML` :1721-1740,
`_notSureHTML` :1764-1786, doors `openSuggested` :1791, `openLesson` :1479, `startScenario` :1538, `showMe` :1452,
`COACH_ACTIONS` :73-123 + `onClick` :2111-2191 (every new `data-act` must be listed there). Glossary card: engine/
glossary.js:189-255 (placement), 282-331 (listeners), `glossaryOpen()` :269 for the Escape ladder. Chat api:
ai_insight_chat.js:2567-2612 (`pushGuide`, `sendText`); guide card renderer coach.js:1939-2017, blocks :2061-2108.
Place store: hub_place.js:30-51; openHub: hub_nav.js:52-83; switchLens: hub_place.js:140-151. Settings: learn_settings.py
:55-61 SWITCHES, :104-153; bootstrap learn_runtime.py:677-763. Board: component_treatment.js:42-60 props, :135-151
filter; xml :42-61 chips, :105-114 headers. Templates and anchors per screen: the P2 facts table (Component
treatment th :109-114 under `tr-table`; connection_desk.xml no anchors; studio_experience.xml table :44-53;
payrun_wizard.xml pw-* ; payruns.xml pk-* ; payslip_review.xml ps-* ; inbox.xml ai-* ; pb_dashboard.xml dash-*).
Node harness: pb_payai_actions/tests/js/harness.mjs + onechat_oc2.test.mjs (loads the real CoachHost).

## 12. Commits, report
Worktree branch `learnrev-p2`. Commits: (1) flag + bootstrap + Guide fetch + six sections (treatment), (2) dock,
(3) (i) cards, (4) right-now actions + provider shape fix + MappingStudio place, (5) explain/nudge/whatnext/router,
(6) anchors + places + retired fs-* + regenerated content, (7) the other seven screens, (8) tests. Explicit paths;
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; no version bumps. `P2_REPORT.md` (write it as a file; if
the environment refuses `.md`, write `P2_REPORT.txt` and say so): per scope item, T1–T4, B1–B10 with screenshots,
per-screen list of fields that got no (i) and why, design-bar score, LR rows added, open items.
