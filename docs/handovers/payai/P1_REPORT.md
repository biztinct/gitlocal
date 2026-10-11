# PAYAI P1 — report (Foundation + Green tier)

Implemented by Opus, 2026-10-12, against `P1_HANDOVER.md`. Nothing deployed to any live database.

## Tests (clone `p0clone`, staged `/tmp/p1stage`, `-i pb_payai_actions -u pb_payroll_ai_insights,pb_hub,pb_audit`)
Final run (run #3, server time 2026-10-11 16:50):
```
odoo.tests.stats: pb_audit: 12 tests 1.53s 1268 queries
odoo.tests.stats: pb_payai_actions: 15 tests 2.07s 1946 queries
odoo.tests.stats: pb_payroll_ai_insights: 128 tests 2.11s 1541 queries
odoo.tests.result: 3 failed, 0 error(s) of 135 tests
FAIL: TestDataQueryAccess.test_06_every_sentence_a_refusal_can_print_ships_in_vietnamese   (PA11, pre-existing)
FAIL: TestEgressSeams.test_04d_the_voice_copy_ships_in_vietnamese_too                       (PA11, pre-existing)
FAIL: TestEgressSeams.test_04e_the_consent_copy_names_what_actually_leaves                   (PA11, pre-existing)
```
No PayAI translation warnings in the log (PA17 fix). Earlier runs: #1 install failed on the ACL CSV (PA15); #2 had
2 own failures (test_02 fixture assumption — PA16; test_13 asserted on `json.dumps` with escaped `›`) — both fixed.

| # | Test (`pb_payai_actions/tests/test_payai_p1.py`) | Result |
|---|---|---|
| 1 | `test_01_registry_and_tools_schema` — keys/tiers/titles/screens, JSON-schema tools, strings only, stubs never offered, phrase table never reads "How do I…" as an order | pass |
| 2 | `test_02_gate_both_halves` — officer passes; plain → no_right with Access-home text; portal refused; ACL-yes/screen-no (role taken off Pay Run) → screen_off; `visibility_for` patched to `locked` for a full-rights officer → refused; refusal arrives as a card + task row | pass |
| 3 | `test_03_switch_off_falls_back` — look off: super() answer, no chip, no tools call, no task | pass |
| 4 | `test_04_open_screen_and_clarify` — "Open the runs board" → done card door `payhub_runs` (auto), history keeps the card; "Open runs" → clarify 2–6 chips; chip `resolve` pins origin `chose` → done on the same task; un-offered value → AccessError | pass |
| 5 | `test_05_door_not_held_refused` — client-sent door whose groups the user lacks → refused, no Access door offered | pass |
| 6 | `test_06_run_status` — "Show the June 2031 run": month resolved, run found as the user, tiles people/net pay/stage, door focus = run id; plain user → refused, run name not leaked | pass |
| 7 | `test_07_download_excel` — draft → refused ("available once approved"); done → download action with `/web/content/` url | pass |
| 8 | `test_08_expiry_and_owner` — clarify older than 10 min → "That question has expired, ask me again", task → expired; another user answering → AccessError | pass |
| 9 | `test_09_audit_rows` — refused + done rows; utterance stored as `[person-n]`; other user cannot read; payroll manager can; RPC create refused; Audit console `_fetch_payai` lists "Asked PayAI: …" | pass |
| 10 | `test_10_phrase_table_without_provider` — `get_active_config()` empty → "open the runs board" still a done card | pass |
| 11 | `test_11_tools_call_is_redacted` — employee name reaches `generate_tools` as `[person-n]`; only Green tools offered | pass |
| 12 | `test_12_question_unchanged_plus_chip` — "what is gross pay": unchanged knowledge answer + "What can you do?" chip; no tools call | pass |
| 13 | `test_13_stub_and_never_cards` (extra) — stub refusal with door, no-right text for plain user, `never` card for "Delete the May run", grouped "What can you do?", prepare switch off → "Settings › PayAI can act" | pass |

## Browser walk — NOT DONE
Skipped. The handover requires ≥ 700 MB available for a temporary server on the clone; the box showed 580–670 MB
(450 MB per the coordinator at the end) with the live server warm (PA21). Also no admin login for `p0clone` is
known (`admin` is inactive on the template); I did not guess one. Not walked, therefore not verified in a browser:
card rendering in the pill and the Coach Ask tab, door auto-open, chip round-trip in the UI, ⌘K "Ask PayAI to…" row,
Settings hub "PayAI can act" card + form, Audit console "PayAI" chip, phone width (400 px), console cleanliness,
asset compilation of the new SCSS/XML/JS. **The walk is mandatory before any deploy** (memory rule
browser-validation-mandatory): on the clone it needs (a) ≥ 700 MB free, (b) a throwaway walk user created via
`odoo-bin shell` on `p0clone`, (c) "PayAI may look" switched on (clone default is off, PA20), (d) a June 2026 run
fixture (the clone has no pay runs), (e) `/web/assets/%` purge.

## Design-bar self-score (1–5, code-level only — not seen in a browser)
- Extreme WOW / best in class: **3** — clean card language (tier-coloured head, badge pop, tiles, origin pills), but unverified on screen and the hero (plan card) is P2.
- Hero moment = plan card: **2** — the plan-card anatomy (slots + origin pills) is built into the contract and template, but no P1 Action produces a plan card yet.
- Zero dead-ends: **4** — every outcome is a card with a reason and a next step (door, Access home, settings path, "What can you do?" chip, expiry note); a missing door list says to reopen the panel.
- Plain language: **4** — every string is plain and through `_lt`/`_t`; no "Odoo"; no model names on cards. Run stage words come from the board.
- Motion with purpose: **3** — card enter + badge pop, reduced-motion honoured; progress/undo countdown are P2.
- Lucide icons, locked palette, no gradients, no emoji: **5** — inline Lucide paths, design-page tokens with `--vuf-*` fallbacks, flat fills only.

## Ledger rows added (PAYAI_LEDGER.md)
PA15 ACL CSV comma; PA16 role lane on sidebar items / Pay Run screen key; PA17 lazy-translation language (`payai.i18n.T`);
PA18 `payai.task` written by the server only; PA19 doors are client-supplied, navigation only; PA20 clone switches off;
PA21 server memory floor.

## Deviations from the handover (with reasons)
1. **Phrase table first, model second** (not "model, then phrase table when the provider is down"): no egress or
   latency for the common phrasings, deterministic, and how/why/what-is questions skip the tools call entirely (one
   fewer LLM round-trip per question). Model still used for anything the table does not match.
2. **`payai.task` ACL is read-only for everyone**; the runner writes with `sudo()` (bookkeeping only) — so the audit
   cannot be forged or edited over RPC (PA18). Actions themselves never sudo.
3. **Run screen key** = `pb_payhub.item_pay_run` (first active of `pb_payhub.item_pay_run`, `pb_sidebar.item_pay_runs`);
   the latter is inactive (PA16).
4. **Settings hub card**: the hub's soft registry adds categories, not cards to `company`; added a one-card category
   "PayAI can act" (opens a small `res.config.settings` form `pb_payai_actions.action_payai_can_act`, system admins
   only) + the `<setting>` block in the general Settings page as the handover asked.
5. **Card contract additions**: `groups` ("What can you do?"), `chip_slot` / `chip_action`, action ids `ask`,
   `followup` (server-offered follow-up, e.g. "Download Excel" on a status card; value validated against
   `result_json.offer`), `download` (url must start `/web/content/`), `auto` on the action to run on arrival.
   `resolve` accepts an optional `action` for follow-ups.
6. **`never` tier Action declared** (`never_destructive`: delete/remove/purge runs, payslips, records) → "Not through
   PayAI" card with the Runs board door (design page's delete scenario).
7. **`run_status` with several runs and no narrowing words** answers the month (tiles + one chip per run) instead
   of asking; download still asks.
8. **Name redaction is stronger than the conversation mapping**: the command path also scans the public employee
   directory (as the asker) for full names in the message, extends and stores the mapping, then redacts — so a
   name reaches `generate_tools` as `[person-n]` even on the first turn (test 11). Given names alone are not caught.
9. **Core chat JS edits** limited to: push `card`/`fresh`, and `kwargs: this._extraSendKwargs()` (hook). Rendering is
   a template extension + prototype patch in `pb_payai_actions`; the full-page variant is untouched.
10. ⌘K row shows only when text is typed, and is drawn after the matches (Enter on "pay runs" still opens Pay Runs).
11. Debug-mode "Coming soon" title for stubs; normal mode "I cannot do that for you yet" + door (as specified).

## Open questions / notes for P2
- **Shared `run_driver` extraction** (`pb_payrun_wizard/static/src/js/payrun_wizard.js` `_compute` :897–1066). Plan:
  new `pb_payrun_wizard/static/src/js/run_driver.js` exporting `async runPayroll(orm, payload, {onStep, onProgress,
  sheet})` that does exactly: `sync_plan` → `sync_step`×n (onStep label) → `prepare_run` (returns early with
  `{blocked}` / `{needs_confirmation}` — caller decides) → optional `attach_spreadsheet` (+ `discard_empty_run` on
  failure, `{pending}` branch) → `compute_batch` in CHUNK=40 (onProgress done/total) → `get_summary` → the
  `splitExceptions` / computed / adopted / fresh arithmetic, returning `{summary}`. The wizard's `_compute` becomes a
  thin caller mapping callbacks to `state.busyMsg/progress` and the two early returns to `gotoKey`/dialogs; the chat
  calls the same function and posts progress into the card (`progress:{done,total,label}`). Keep the driver free of
  component state and notifications; keep P0's server gates as the only gates. Needs a byte-for-byte regression test
  of the wizard flow (Learn `sc_payrun` replica too).
- Where should P2 write progress/confirm/undo stamps? Proposal: new runner RPCs `rpc_confirm_task(task_id, kind)` /
  `rpc_task_progress(task_id, done, total)` that validate state transitions server-side (PA18).
- Tools-call latency: every non-question message that the table does not match costs one extra model call before
  the normal answer. Acceptable for P1; P2 could add a cheap "imperative?" pre-check or merge routing into the
  classifier call.
- `scheme` resolver uses `get_defaults()` (runner-gated); `division` uses `pb.group.visibility.visible_division_ids()`
  — both untested in P1 (no Action uses them yet).
- The ⌘K door list is registered once per mount; a role change mid-session needs a panel reopen.
- Settings card is admin-only (`base.group_system`, because `res.config.settings` is). Owner may want payroll
  managers to switch tiers too — scope decision.

## Modules touched (manifest versions)
| module | version |
|---|---|
| pb_payai_actions (new) | 19.0.1.0.0 |
| pb_payroll_ai_insights | 19.0.3.11.0 → 19.0.3.12.0 |
| pb_hub | 19.0.1.10.1 → 19.0.1.11.0 |
| pb_audit | 19.0.1.3.2 → 19.0.1.4.0 |

Deploy note (Fable): payobook only; `-i pb_payai_actions -u pb_payroll_ai_insights,pb_hub,pb_audit`; asset purge;
the post_init_hook turns all tiers ON only when the db name is `payobook`.

## Commits (branch 19.1, not pushed)
- `300eeaeb4` feat(payai): messages carry a command card; send takes a chip's resolve; providers gain tool calling
- `76ba6b116` feat(hub): palette service exposes entries() and run(id); rows may answer any typed text
- `509d1110b` feat(audit): PayAI requests are an Audit console source
- `ced3e2060` feat(payai): PayAI does it — P1 foundation and the Green tier
- (this report) docs(payai): P1 report
