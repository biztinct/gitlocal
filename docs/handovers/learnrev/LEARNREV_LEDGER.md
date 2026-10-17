# LEARNREV — conventions & gotcha ledger

Every LEARNREV handover and phase agent references this file. Add an LR row for every new gotcha. Inherits
`docs/handovers/onechat/ONECHAT_LEDGER.md`, `docs/handovers/payai/PAYAI_LEDGER.md`, `docs/handovers/LEARNOS_LEDGER.md`
and `docs/handovers/PBLEARN_LEDGER.md` — their standing rules bind this program.

## Standing rules
| # | Fact | Apply |
|---|---|---|
| LR-R1 | One sentence per screen (`SCREEN_CTX.<key>.next` → `screens[].next_step`) feeds Explain, the first-visit nudge AND the whatnext intent. | From P2 the "Right now" list is computed from screen state; `next_step` becomes a fallback only. |
| LR-R2 | Station keys equal screen keys for content screens (hubs excepted). | A door from a screen targets `station:<screenKey>`; never pass an empty focus. |
| LR-R3 | The chat remounts on every drawer open; only a pushed message scrolls it. | Scroll to the latest on mount (P0); never rely on `_noteScreen` to do it. |
| LR-R4 | Three vocabularies exist today for the treatment columns (board / lesson / anchors). | From P1 labels come from the field definition once; the truth gate fails a build on any other name. |
| LR-R5 | A screen's own explainer (expander, `title=` tooltips, Python `help=`) is the seed of its field cards. | Never author a second text for a field that has `help=`; extend `help=` instead. |
| LR-R6 | Only the ACTIVE browser tab renders OWL (rAF suspended when hidden). | Browser checks: one visible tab; `/json/activate/<id>` before reading a screen. |
| LR-R7 | Other sessions deploy to the same server; payobook.com went 502 twice on 2026-10-17 during another session's test+upgrade. | Before any stop/`-u`: ListAgents + message, and `pgrep -af "odoo-bin.*stop-after-init"` on the server; wait, never kill. |

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| LR1 | 2026-10-17 | `learn_palette.js:96` registers ⌘K rows at module load; `_t("Learn")` inside throws "translations have not been loaded" on every page load. `coach.js:314` registers them again later, which works. | Register after translations are ready (P0). |
| LR2 | 2026-10-17 | `component_treatment.js` LANE_LABELS has `formula` but the server lane for formula rows is `calculated` (`formula_config.py:_value_kind_lane`), so the board prints the raw key. | Keys in LANE_LABELS must match `_value_kind_lane` exactly; add a test that every lane the server can emit has a label. |
| LR3 | 2026-10-17 | `net_role_reason` sentences embed the NET component's own name (`%(net)s`), which on a Vietnamese scheme yields "Never reaches Số tiền thực nhận …" inside an English sentence; the reason is STORED at classify time. | Say "net pay" (translated) in the sentence; substitute at read time for stored reasons (P0). |
| LR4 | 2026-10-17 | `resolve_door` answers "I cannot see your list of screens yet. Close and reopen this panel" when the client sent no doors. | Server-side fallback catalogue; never ask the person to repair the panel (P0). |
| LR5 | 2026-10-17 | On payobook (assistant ON) a typed "What should I do next here?" reached the model path and returned a generic run-payroll answer that ignored the screen. | P2: whatnext is answered from screen state before any model call; add a router test for the exact label on every screen. |
