# LEARNREV P3 — the Library: a calm Learning page (handover for Opus)

Program: `docs/handovers/learnrev/LEARNREV_PROGRAM.md` (standing rules verbatim there). Ledger: `LEARNREV_LEDGER.md`
(all rows). Design page: `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html`, Option C tab, second mock-up "Learn ›
Library (the new Learning page)" — that is the target: **Continue card · path strip · screens listed like the
sidebar with Guide / Watch / Try chips · one search over everything · no badges, streaks or overall ring (owner
decision 2026-10-17)**. Gaps closed here: G7, G8, G9, G10, G11, G12, G13, G14, G15, G28, G29 (see the design page's
gap table). P2 (`P2_REPORT.md`) built the Guide panel the Library's rows open into.

Work in the git worktree you are given (branch `learnrev-p3` from the 19.1 tip). No deploy in this phase.

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Measured against Linear's docs index and
Duolingo's one-Continue-button calm, never stock back-office. **Hero moment:** the page opens on one card that says
exactly what to do next and why ("Continue · your path as Approver · 2 of 7 done · Approvals: one inbox, every
route · 9 steps, plays on the real screen"), a path strip of your required lessons, and below it every screen in the
product in the same order as the left menu, each with a quiet progress ring and three small chips. The page is one
screen and a half tall, not eight. **Zero dead ends:** a search with no hit says so and offers "Ask PayAI"; a screen
you cannot open says "Not in your menu" once, in grey, and still lets you read its Guide; an empty path (no role) shows
"Pick what you do" chips in the Continue card. Plain screen words; never the word "Odoo". Payobook design system,
Lucide icons via `ic()`, no emoji, no gradients, motion with purpose (`prefers-reduced-motion` respected; the
"Reduce motion" header button is REMOVED — the system setting decides, and a switch lives in Learn › Settings).
Score every bullet 1–5 in the report.

## 1. Scope
- **S1 Replace the map body** of the Journey (`journey.js _mapBody` :637-757 and its helpers `_continueHTML`,
  `_roleBarHTML`, `_monthEndHTML`, `_practiceCardHTML`, chapter/line/card/scenario-row renderers, the Lifecycle road
  `:885-928`) with the Library layout (§3). The OTHER views stay as they are: lesson player, mission, scenario (Try),
  practice, missions list, outline (`body` :607-634; `_applyDeepLink` :2082-2161 keeps every arrival key —
  `station:`, `lesson:`, `scenario:`, `suggest:`, `practice` — because ⌘K rows, P0's lesson door and the Guide's doors
  use them).
- **S2 Continue card** (one, top): title = next lesson from `runtime.next_best` when present, else the first
  undone required station of the role; the reason line in plain words ("Required for Approvers because you hold the
  Payroll approval seat" when `path.roles[].why` exists, else "Required for <role>"), progress "N of M done", steps
  count (`lesson.steps.length`, not minutes — G29), and the role control inline: "your path as <Role> · Change"
  (opens the role chips in place; `res.users.learn_role` as today, `learn_path.py:53-68`). Month-end
  (`path.month_end`, within 7 days) becomes ONE line inside the card with its Watch door; no separate card.
- **S3 Path strip**: horizontal stepper of the role's required stations (done tick / current / todo), ending in a
  dashed "Change role" chip. Click = open that station's outline. Hidden when the role has no required stations.
- **S4 Browse by screen**: every content screen that has a station, grouped and ordered EXACTLY like the left menu
  (Home, Pay Run, People, Lifecycle, Workforce, Insights, Compliance, Settings; "Setup" screens such as Formula
  Engine, Mapping, Component treatment, Approval Matrix, Statutory, Integrations, New configuration, Schemes and
  currencies, Access live under **Settings**). Group = the hub of the station's screen (`screens[].places` tag →
  hub screen name; `sidebar_key` as the fallback; a test proves no station is orphaned). Row = progress ring (done /
  started / none, from `runtime.progress`), title, one-line purpose (`station.summary`), then chips: **Guide**
  (always; opens the screen with the Guide panel docked and This screen expanded — §4), **Watch** / **Try** (only
  the modes the station's scenarios have; `startScenario` as today), and at most ONE status chip: "Required" (role
  path) or "Not in your menu" (`visible_stations`), never "Not on your path" (G9), never "About N min" (G11). Rows are
  keyboard-focusable; Enter = Guide.
- **S5 One search** (replaces "Search the journey"): a page-level search box with a results list over FIVE kinds —
  screens (station name + summary), **fields** (manifest column + first sentence of help, from a new light index,
  §4), terms (glossary term + definition), tasks (scenario names), lessons (lesson step titles). Each row has a kind
  chip and opens its target: screen → outline; field → the screen with the Guide's Fields row expanded; term → the
  glossary card inline; task → Watch; lesson → the player at that step. Empty result: "Nothing matches '<q>'" +
  "Ask PayAI" (`openHelper({text: q, send: false})`). ⌘K rows (`learn_palette.js`) also get the FIELD rows ("Pay
  role · Field on Component treatment").
- **S6 Removed from the page**: overall ring, "Pay Run badge", streak chip, tier chips (Gold/Silver/Bronze), "Start
  here" chip, "Find it in …" chip (the Guide chip replaces it), "Show me how" scenario rows per chapter (walkthroughs
  are chips on the screen row), the "Take the tour" card (the tour becomes the Continue card's suggestion for a
  user with 0 progress: "New here? Take the 8-minute tour" line with Watch), the Lifecycle road, "Reduce motion"
  header button (switch moved to Learn › Settings; honour `prefers-reduced-motion`), "Practice missions" button
  (missions stay reachable from the Practice entry). The `skill_tree`/streak bootstrap keys stay served (other
  tenants may read them) but nothing on the page draws them.
- **S7 Practice entry**: one row at the end of Browse, "Practice company — open it and click around; nothing reaches
  a real record", opening practice mode as today (`_practiceCardHTML` door). On the demo database it says "Practice
  on the demo company"; elsewhere "Practice on a copy" (P4 generates the replicas; P3 keeps today's practice view).
- **S8 P2 polish (small, in scope because they are on the same surfaces):** (a) the drawer header reads
  "Guide · <screen>" while the Guide shows (today "PayAI / On: …" truncated; chrome keys EN+VI); (b) when the person
  sends a chat message, the Guide sections fold to their titles so the conversation gets the height (a "Show the
  Guide" link re-expands; remembered per screen); (c) the Runs board month summary clips its button at the docked
  width — fix the board's responsive rule (`pb_payruns` scss; the panel is 420 px, the content width is viewport −
  256 − 420); (d) truth-gate rule from LR30: a manifest column found in a template only as text split by `<br/>`
  fails the gate.
- **S9 Lessons follow the screen** (standing rule): the Learn hub lesson that describes the Learning page itself
  (`hub_learn`, and any station/lesson step whose text names "Your journey", "Overall", "badge", "Not on your path",
  "Show me how", "Practice missions", "Reduce motion") is reworded EN+VI; the `welcome`/first-login copy that points
  at the map; the Team lens readiness copy if it names the ring. Regenerate content; vi_VN.po restore dance (LR28).

## 2. Binding non-goals
No change to lesson/walkthrough CONTENT or the scenario engine beyond the wording in S9 (P4); no change to the lesson
player (G17/G18 are P4); no PayAI/router change; no manifest content changes except the LR30 gate; no new stored
fields (per-user role stays `res.users.learn_role`; nothing else is written); no sudo; no deploy. The Team and
Settings lenses stay (Settings gains the two switches named above).

## 3. Layout (one column, max-width 1180 px, in order)
1. Header row: "Learn" + the language toggle (kept) — nothing else.
2. Search box (full width, ⌘K hint).
3. Continue card (S2).
4. Path strip (S3).
5. Browse by screen (S4): eight group headers in menu order, rows beneath; groups with 0 reachable screens still
   list their rows (with "Not in your menu" once per row).
6. Practice row (S7) and, for managers (Team lens gate `learn.path.readiness`), one "Team readiness" link row.
Page height target at 1440 × 900 with 42 stations: ≤ 2,600 px (today 8,044). Rows are 52 px; groups collapse on
phone width.

## 4. New seams (verified plumbing — do not re-derive)
- **Field index for search:** add `learn.guide.rpc_index()` (pb_learn/models/learn_guide.py; same access pattern as
  `rpc_guide`, no sudo) returning, in the user's language, `[{screen, screen_name, key, column, line}]` for every
  manifest field where `line` is the first sentence of `help`/`how` (≤ 120 chars). Cached client-side with the
  content bundle for the drawer's life. Test: index covers all 8 manifests, every row has both languages when asked
  in vi_VN.
- **Open the Guide on a screen from the Library:** `openScreen(screen)` (`engine/places.js:213-236`) then, once
  the place is published (`waitForPlace`, `places.js:242-256` — the walkthrough's seam), `openHelper({guide:
  {section: "this"|"fields", field: key}})`. Add the `guide` option to `openHelper` (`coach.js:678-700`) → the drawer
  opens docked (if ≥ 1280) with that section expanded and, for a field, the Fields row scrolled into view and opened.
  Fallback when the screen cannot be opened (`reachable()` false): open the outline view instead with a grey note
  "Not in your menu — here is what it does".
- **Group order:** the sidebar order is the pb.sidebar.item sequence; mirror it as a constant `MENU_ORDER` in
  journey.js with a comment, and a Python test that compares it to `pb.sidebar.item` names/sequence on a database
  (ordering drift fails the test, not the page).
- **Progress:** `runtime.progress` as today (`journey.js:~285-345` bootstrap read); "started" = any step done.
- **Role control:** `_roleBarHTML` logic reused inside the Continue card; `learn.path` methods unchanged.
- Drawer header + fold (S8 a/b): `coach.xml:49-91` header; the sections render in `coach.js` (P2's `_guideHTML`
  or equivalent — read `coach/` after P2); a chat send is observable from `helper.onGuideAnswer`/the chat's `sendText`
  path (`ai_insight_chat.js:~924`) — fold on the first send of a drawer session.

## 5. Tests
- **T1 node** (`pb_learn/tests/js/library.test.mjs` via `test_guide_client.py`'s runner pattern): render the Library
  from a fixture bootstrap (42 stations, 3 roles, progress for 5): Continue card text, path strip count = required
  stations, 8 groups in MENU_ORDER, every station appears exactly once, no row carries more than 3 chips, the
  strings "Not on your path", "badge", "streak", "About … min", "Show me how", "Reduce motion" are absent from the
  HTML; search for "pay role" returns a field row first; empty search state has the Ask door.
- **T2 Python** `pb_learn/tests/test_learnrev_p3.py`: (a) `rpc_index` covers all 8 manifests EN+VI; (b) every station
  maps to one menu group (no orphan); (c) MENU_ORDER equals `pb.sidebar.item` order on the DB; (d) `bootstrap` still
  serves `skill_tree`/`streak`/`next_best` (contract kept); (e) the Learn hub station/lesson texts no longer contain
  the retired page words (EN+VI) — add them to a `retired_labels`-style list for `hub_learn`; (f) LR30 gate rule
  fails a synthetic manifest whose column exists only as `<br/>`-split text.
- **T3 truth gate + anchors** still 0 errors; `test_anchor_registry` green; P2's node suite 117/117 still green;
  PayAI node suites green; `gen_learn_data.py --check` up to date; `check_contract.py` only the known `grid-hint`.
- Existing pb_learn suite on a dump clone (AI off, LR17/LR26); known baselines test_07b, TestCoach.test_11 with AI on.

## 6. Browser checks (clone on 8095 with the staged addons, Guide switch ON on the clone; headless Chrome 9559)
B1 Learning page at 1440×900: Continue card + path strip + 8 groups; `document.querySelector('.o_action_manager')
.scrollHeight ≤ 2600`; no "Not on your path"; B2 press Guide on "Component treatment" → the board opens with the
docked Guide and This screen expanded; B3 search "pay role" → field row → opens treatment with the Fields row "Pay
role" expanded; B4 search "xyzzy" → empty state with Ask PayAI; B5 Change role → Owner → Continue card and path strip
update; B6 Vietnamese: whole page in Vietnamese, search works on Vietnamese labels ("vai trò"); B7 ⌘K "pay role"
shows the field row; B8 deep links: `/bizapp/action-learn_hub` with focus `station:treatment` opens the outline;
P0's "Open the lesson" door still lands on the outline; B9 phone width 400 px: one column, groups collapsed, no
horizontal scroll; B10 the Runs board docked: month summary button no longer clipped; B11 drawer header reads "Guide ·
Component treatment", folds on a sent message, "Show the Guide" re-expands; B12 console clean throughout.
Screenshots `p3_b*.png`.

## 7. Commits, report
Worktree branch `learnrev-p3`. Commits: (1) index + openHelper guide seam, (2) Library body (S1–S4, S6, S7),
(3) search (S5) + ⌘K field rows, (4) P2 polish (S8), (5) content wording (S9) + regeneration, (6) tests. Explicit
paths; `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; no version bumps; no push. `P3_REPORT.md` as the
earlier reports: scope table, T1–T3, B1–B12 with screenshot paths, page height before/after, design-bar score, LR
rows, open items.
