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
| LR6 | 2026-10-17 | There is NO master screen registry: each hub declares its tabs in its own JS (`pay_hub.js:84-165`, `home_hub.js:118-147`, `mapping_studio.js:104-154 MODES`); the only screen→hub→tab→action map is the authored Learn content (`screens[].places`, `hubs`). | Manifests key on learn screen keys; path labels resolve through `learn_content.json hubs` (places.js precedent). |
| LR7 | 2026-10-17 | `hub_mapping.tabs` in data.js lacks `desk` (Connections), the default Mapping tab. | Add it (EN+VI) in P1 and regenerate. |
| LR8 | 2026-10-17 | Nothing ties a cockpit column to a model field; headers are `_t` literals in XML/JS (only Results and Records Desk derive columns from metadata). The board key→field map for Component treatment is the write path `set_component_setup` (`formula_config.py:2583-2652`). | Manifests declare the link; `derived` entries for non-field columns; the gate checks header text against the template. |
| LR9 | 2026-10-17 | `value_kind` has NO Vietnamese at all (label, help, 9 choices) in `pb_hr_payroll_formula/i18n/vi_VN.po`; `payroll_signal`, `*_source` labels likewise; and `_value_kind_options` reads raw `field.selection` (English) while pay roles use `_description_selection`. | P1 S6 closes the .po gaps and switches the options to `_description_selection`. |
| LR10 | 2026-10-17 | No "computed before the scheme changed" marker exists: `net_role`, `net_role_detail`, `component_type`, `payroll_signal` are not in `VERSIONED_FIELDS`, `last_evaluation_date` is never written; only `write_date` is available. `anchors.json tr-table` still says "Group, Pay role, Subtotal, Tells the run, Value type". | Right-now `recompute` compares rule `write_date` vs payslip `write_date` (P1 §5); anchor text fixed by the retired-label lint. |
| LR11 | 2026-10-17 | `translationIsReady` (`web/static/src/core/l10n/translation.js:191`, resolved in `localization_service.js:95-96`) is the seam for module-level `_t` use; `_t` throws "translations have not been loaded" when forced early. | Never stringify a `_t` result at module load; wait on `translationIsReady` or build inside `setup()`. |
| LR12 | 2026-10-17 | Two Opus phases run at once in the same repo (P0 in the main tree, P1 in a worktree `learnrev-p1`); both touch `pb_hr_payroll_formula/i18n/vi_VN.po`. | Fable merges P1 after P0 lands and resolves the .po union by hand; later phases keep one builder per tree. |
