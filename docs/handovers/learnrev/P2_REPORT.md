# LEARNREV P2 — report (the Guide panel and field cards)

Implementer: Opus, 2026-10-17. Worktree `.claude/worktrees/agent-a513d2e60ef6d1a78`, branch `learnrev-p2`
(fast-forwarded to 19.1 `f61f2de32` before the first edit, so the P1 deploy fixes — one-text "Included in another
total" header, renamed labels, LR29–LR33 — are underneath). **Not pushed, not deployed.** Handover: `P2_HANDOVER.md`.

## Scope
| Item | Result | Notes |
|---|---|---|
| S1 Docked panel | **Done** | ≥ 1280 px: `body.lrn-docked`, page padded 420 px on `.o_action_manager`, panel full height under the top bar (`--lrn-dock-top` measured from the navbar), corner button hidden; dock / float toggle in the header (`pbLearnDock`, default dock). < 1280 px: the floating card as before. Scenario overlay subtracts the dock. |
| S2 Six sections | **Done** | This screen · Right now · Fields on this screen · Tasks · Understand above the one chat; Ask is the chat (labelled row, composer always visible). One `rpc_guide` per screen + args + language, cached; Right now re-read on every open and 400 ms after a filter. Renderer is pure (`coach/guide_panel.js`). With the Guide showing, the chat's opening card keeps only the questions (its story / walkthrough / tab rows duplicated the panel). |
| S3 (i) field cards | **Done** | `coach/field_info.js`: header finder (truth gate's `norm()`, either spelling, form controls ignored), idempotent, re-laid by a 120 ms observer, press never reaches a sortable header; inside a clickable tile the (i) is `span role=button` (Tab, Enter/Space). One floating card (below → above → beside, clamped clear of the dock), Esc rung with `stopImmediatePropagation`, never with a glossary card, 160 ms fade-up, reduced motion respected. Footer: Open in the Guide, Watch this field (only when a walkthrough step points at the field's anchor), thumbs → `learn.guide.rpc_feedback` → one `learn.event` `guide_feedback` row (`<field>:up|down`, no text). |
| S4 Right-now actions | **Done** | `filter` → `env.bus` `pb-learn:act` (board SETS the chip); `open` → `openHub({xmlid, lens, lensKey, focus, context})`; `open_record` → the record's form. Providers now emit `focus` / `context.pb_config` / `res_model` / `res_id` (never `ids` / `config_id`). MappingStudio publishes `extra: {config_id}`; `hub_place` carries `extra`. |
| S5 Explain / nudge / whatnext | **Done** | Explain (switch on + manifest): purpose, "You are here: …" / "Next: …" steps, ≤ 3 "Column — help", source; no next sentence where a live list exists; "Open the Guide" door. Switch off: byte-for-byte the old floor. whatnext answers from Right now (bilingual, one provider call). Router step 5b: the whatnext label (EN/VI) + the intent's phrases go to the guide before any command / PayAI / model step; the Mapping scheme rides in `context.pb_guide_args` (route signature unchanged, OC-R1). Nudge: purpose + Open the Guide (+ Watch only when offered). whatnext chip leaves the opening card where Right now is live; two generated questions join it. |
| S6 Mapping › Connections + anchors | **Done** (deviation) | `mapping` places start with `pb_mapping_studio:desk`, blurb/next describe Connections, Journey still resolves here. New anchors `md-list`, `md-inspector`, `sx-table`, `dash-needs` (registered, `reserved`). `fs-views` / `fs-command` **retired by flag, not deleted** (LR34: L5 and sc_formula still name them; deleting fails the registry test and changes lesson content, a P4 non-goal). Formula manifest moved to the Table view; its Cards-only fields keep no anchor. |
| S7 Switch | **Done** | `pb_learn.guide_enabled` (default OFF), `bootstrap['guide']`, Learn › Settings card "Guide panel and field cards" (EN+VI). Off = no Guide call, no (i), no dock. |
| S8 Eight screens | **Done** | Treatment end to end first, then the other seven verified in the browser (table below). Screens without a provider show "Nothing live for this screen yet." + the static sentence as a grey fallback, never both. |

Coordinator rulings applied: treatment expander "What do these settings mean?" removed (the (i) cards replace it) with
its dead style; Re-classify tooltip and toast reworded to the column's words ("…report groups and the Included in
another total ticks…") with their Vietnamese; header kept as one text.

## Tests
| Test | Result |
|---|---|
| T1 node (`pb_learn/tests/js/guide_panel.test.mjs`, via `test_guide_client.py`) | **117/117** locally (node 24) and inside the clone run (node 18). Fixture `tests/data/guide_treatment_en.json` = `p1guide.json` `en_US`, verbatim. |
| T2 header finder + injection (same suite) | pass: `Included in<br/>another total`, `Figures don’t add up`, a label wrapping its select, idempotent second run adds 0 |
| T3 `test_learnrev_p2.py` (a)–(g) + feedback, spellings, brand | **10/10** on the clone |
| T4 truth gate | **0 errors**, 8 manifests (offline gate and `TestGuideTruth` on the clone); `TestAnchorRegistry` 10/10 with the new anchors and the retired fs-* |
| Full clone run (`/pb_learn`, PayAI `TestOneChatClient`, `TestLaneLabels`, `TestStudioExperience`) | **361 tests, 1 failure: `test_07b`** — known baseline (asserts the question-mining job is active; the clone prep switches all jobs off). Same result re-run on the final code. |
| PayAI node suites (oc2, oc3, rich, client_fix, gaps_doors) | all pass (167 / 266 / 90 / 82 / 10) |
| Offline router corpus `test_onechat_oc1.py` | 39/40 — the 1 is the known `grid-hint` contract check; no corpus row moved |
| `gen_learn_data.py --check` | up to date; vi_VN.po untouched by the generator (LR28 confirmed) |
| `check_contract.py` | 1 known failure (`grid-hint`); retired fs-* reported as warnings |
| `replay_tests.py` | 238 pass / 3 fail — identical to HEAD before P2 (baseline) |

Clone: `pg_dump payobook --exclude-table-data=hr_payslip_line | psql lrp2clone` (LR16/LR26), AI connection off and
every `*api_key*` blanked (LR17), PayAI user implied by internal user on the clone only (LR18), jobs and mail servers
off; staged from `git archive HEAD` (PA60); `--addons-path=/tmp/p2stage,/odoo/odoo-server/addons`, ports 8097/8096;
**dropped with `dropdb --force`, filestore and staging removed.**

## Browser checks (clone on 127.0.0.1:8097 over an ssh tunnel; own headless Chrome on 9557; QA login by `fetch('/web/session/authenticate')`; Guide switch ON on the clone only)
Screenshots: `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/p2/walk/`.
| # | Result | Evidence |
|---|---|---|
| B1 docked, six sections, path chips | **pass** — panel 420 × full height, page padded 420 px, corner button hidden, "Mapping › Component treatment", before Formula Engine, next Run / Runs | `p2_b1_docked.png` |
| B2 Right now + Show | **pass** — "3 rows still need your answer on Pay role: Loan Installment (in), KPI Bonus (in), Incentive / award" + Show, type conflict + Fix, recompute + Open run; Show → chip "Needs your answer 3" on, board shows exactly those three rows. *Data staged on the clone* (no scheme had a type conflict). | `p2_b2_show.png` |
| B3 Pay role (i) card, Esc ladder | **pass** — six choices with when, How it is filled + set-by chips, Used by 6 + "and 8 more" (expands to 14), If you change it, Open in the Guide / Watch this field / thumbs (row logged); Esc closes the card and returns focus to its (i), Esc again closes and undocks | `p2_b3_card.png`, `p2_b3_card_bottom.png` |
| B4 1100 px | **pass** — floating 480 px card, no page padding, same sections | `p2_b4_float.png` |
| B5 Vietnamese | **pass** — all titles, chips, Right now, "Vai trò trong lương", "Cộng vào thực nhận", "và 8 chỗ khác"; all six (i) found on the VI headers; switched back | `p2_b5_vi.png` |
| B6 Explain | **pass** — purpose, "You are here: Mapping › Component treatment", "Next: Pay Run › Run", three column lines, source, Open the Guide; no repeated next sentence | `p2_b6_explain.png` |
| B7 typed whatnext | **pass** — the live steps from Right now (with the scheme), "From the guide", Open the Guide | `p2_b7_whatnext.png` |
| B8 Runs | **pass** — Right now names the 17 drafts; Open lands on Pay Run › Runs with the first run's card highlighted. No run is "unbalanced" on this clone (payslip lines not dumped), so that row could not show. | `p2_b8_runs.png`, `p2_b8_open.png` |
| B9 first visit | **pass** — "First time on Component treatment?" + the Guide's purpose + Open the Guide / Watch / Not now; Open the Guide → docked, This screen open | `p2_b9_nudge.png` |
| B10 switch off | **pass** — no Guide, no (i), no dock, the old floating drawer and context card | `p2_b10_off.png` |
| Console | **clean** on every step (error + rejection collector installed after each load) | |
Also: Learn › Settings card (`p2_s7_settings.png`), a Fields row expanding to the card (`p2_fields_row.png`), Open in
the Guide from a floating card opens that Fields row, and the seven-screen sweep (`p2_s8_*.png`).

## Fields with no (i), per screen (they are in the Fields section)
| Screen | (i) on | No (i) — why |
|---|---|---|
| treatment | all 6 | — |
| mapping (Connections) | Component / read order, Sample value | Source order (a button, not a header); Contract storage, Value type, Pay role are on the panel's Storage / Use in payroll tabs (the observer lays them when those tabs open — **not browser-verified**) |
| formula | Component, Source / calculation, Value type, Preview value | Formula, Feeds from, Appears on payslip — Cards view only |
| runpayroll | Payroll scheme, Batch name, From, To | What should these values do?, Coverage, Need review — later wizard steps |
| payruns | Net pay | Gross, People (inside a sentence); Figures don't add up, payslips have no source data, Waiting on you (drawn only on runs in that state); Where it is (no header on the card view) |
| payslips | all 5 | — (after moving Need review to `ps-kpis`) |
| approvals | none on an empty My turn | every field sits on a request card; Waiting for a decision (state) is not a header (handover §5) |
| dashboard | all 7 | — |

## Design bar (1–5)
| Bullet | Score | Why not 5 |
|---|---|---|
| Hero moment (Pay role card; Right now + Show) | 5 | — |
| Zero dead ends (loading, failed + Retry, no scheme, nothing live + fallback, no walkthrough → lesson map) | 5 | — |
| Plain screen words, EN + VI, never the brand word | 4 | the board's own English bits on VI (LR32) are outside P2 |
| Motion with purpose (160 ms, reduced motion) | 5 | — |
| Keyboard (real buttons, Esc ladder, focus return, span role=button in tiles) | 4 | (i) inside KPI tiles is a span role=button — keyboard-complete, but nested in an interactive tile |
| Design system (palette, Lucide via `ic()`, no emoji, no gradients) | 5 | — |
| vs Xero / Gusto / Stripe | 4 | with all sections open the chat gets ~40 % of the panel; a Guide that folds while chatting would be better |

## Commits (branch `learnrev-p2`, not pushed)
`61e2dd1ac` Guide panel, dock, (i) cards · `48e467cdb` Right now actions, provider shape, Mapping place, board bus ·
`1592ddc7b` Explain / whatnext / router · `66c7fcc2a` anchors, retired fs-*, treatment board words · `5fb684460`
tests · `c35e0fbd2` layout fixes from the walk · `47bb1c4b5` the other seven screens · (this report + ledger rows).
Deviation from §12's eight commits: `coach.js` carries the drawer wiring for S1–S5, so it landed in the first
commit rather than split by hunk; the data.js Mapping text and regenerated content landed there too.

## Ledger rows added
LR34 retire a render-dead anchor by flag + the replacing file · LR35 "and N more" from the card, not the handover ·
LR36 the chat redraws its opening card only on a prop change (`chatPlace`) · LR37 the Guide follows the drawer's
language via `context.lang` · LR38 labels wrapping their own control · LR39 expander removed: switch the Guide on
where this build ships · LR40 a `"` written through the authoring tool landed as a bare quote.

## Deploy notes (for Fable; tier: normal — JS/SCSS + Python, one new selection value, no stored field)
`-u pb_learn` (new asset files in the manifest, `guide_feedback` event label + its VI), `pb_formula_studio` (templates,
two new VI msgids — new, no overwrite needed), `pb_payruns`, `pb_hub`, `pb_dashboard`, `pb_payslip_review` (manifest
anchor), `pb_payroll_ai_insights` (chat `_route` context) — then asset purge + `web.assets.version` bump +
`orm_signaling_assets` per DB, and switch "Guide panel and field cards" ON in Learn › Settings on payobook (LR39 for
other databases: the treatment expander is gone).

## Open items
1. Connections' Storage / Use in payroll tabs and an Approvals request card with items were not walked (no (i)
   evidence there).
2. With every section open the chat area is small (Guide capped at 58 %); consider folding the Guide while a
   conversation is under way (P3/P5).
3. Docked, the Runs board's month hero clips its button at ~880 px of content (the board's own layout at that
   width).
4. LR30's suggested gate (fail a manifest column whose template text holds an inline tag) is not added.
5. Pay role card height: on a 813 px viewport the card scrolls to show Used by / If you change it.
