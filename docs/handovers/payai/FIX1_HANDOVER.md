# PAYAI FIX-1 — handover (fix every confirmed P3 + P4 review finding)

Author: Fable/Opus main loop, 2026-10-13. Read with `PAYAI_PROGRAM.md` and `PAYAI_LEDGER.md` (PA1–PA56, rules PA-R1..R5).

## Why
Two adversarial review workflows ran over P3 (`43b927ac4`'s parent chain, P3 ship) and P4 (`6327ca99b`):
- `review/P3_REVIEW.json` — 44 confirmed (12 major, 0 blocker).
- `review/P4_REVIEW.json` — 33 confirmed (1 blocker `link-1`, 11 major).
Each finding has `id, title, file, line, severity, detail, repro, fix, reasons`. **The `fix` field is a recommendation,
not a contract** — implement what makes the repro behave correctly and is consistent with the surrounding code.
"P3:xxx" / "P4:xxx" below refers to `id` in the respective file (ids collide across files: P3:crit-1 ≠ P4:crit-1).

## Live state (do not re-derive) — PA57
On 2026-10-12 20:11 UTC another session's combined deploy (`/tmp/pb-role-reason-combined-20261013-codex`) swept the
P4 versions onto ALL four DBs: payobook has `pb_payai_actions 19.0.4.0.0`; every DB has pb_approval_config 1.6.2,
pb_learn 20.5.2, pb_payrun_wizard 1.32.1, pb_audit 1.4.1, om_hr_payroll 1.8.2, pb_payroll_ai_insights 3.12.1.
abm crons still all off (0/69). payobook switches: look/prepare/decide ON, voice go-ahead OFF.
So: manifests == DB versions now. **Do not touch any `__manifest__.py` version** — the main loop bumps only in the
ship commit (PA41; a parallel session's version-diff deploy sweeps any bumped module).

## Rules for every implementer
- Edit ONLY the files your cluster owns (table below). Need a change elsewhere? Do not make it — report it.
- Do NOT `git commit`, `git add`, `git stash`, `git checkout` — other agents edit the same tree concurrently. The main
  loop commits per cluster.
- Do NOT edit `tests/__init__.py` (main loop wires your new test file) or any `.po` (cluster G owns catalogues).
- New tests go in YOUR new file `pb_payai_actions/tests/test_payai_fix_<cluster>.py` unless the table gives you an
  existing test file. Use far-future year 2031 fixtures (PA40). Call gates `with_user(...)` (PA12). Reuse other test
  modules' fixtures through the module object (PA56).
- You cannot run Odoo locally (PA10). Verify logic with stubbed python / node runs, as the reviewers did (each
  finding's `reasons` shows how). The full Odoo suite runs once on `p0clone` in the Test stage.
- White-label: no "Odoo" in any user-visible string. Plain-English, screen words. Reuse existing English wording where
  the same sentence exists (the VI catalogue keys on msgid — every changed msgid needs a new VI line, cluster G does it).
- Return: per finding id → `fixed` | `not-fixed` (+why) | `deferred` (+why); files changed; every user-visible
  English string you ADDED or CHANGED (exact msgid, file, whether `_`/`_lt`/`_t`); any cross-cluster need.

## Clusters (files are disjoint; order: A,B,C,E,F in parallel → D after C → G after all)
| cluster | owns (write) | findings |
|---|---|---|
| **A Red** | `payai/actions_red.py`, `payai/gate.py`, `tests/test_payai_p3.py` | P3: sec-1, sec-2, sec-4, corr-1, corr-2, corr-3, corr-5, corr-6, corr-7, ux-4, ux-5, ux-6, ux-7, ux-8, ux-9, ux-11, crit-1, crit-5, test-1, test-5, test-6, test-9, test-10, test-11, test-13 |
| **B Amber** | `payai/actions_amber.py` | P3: wf-1, wf-2, wf-3, wf-4, wf-5, wf-6, wf-7, wf-11, crit-3 |
| **C Runner** | `payai/runner.py`, `models/payai_task.py`, `payai/cards.py` | P3: wf-8, wf-10, ux-1, ux-3, ux-10, crit-2, crit-4 |
| **E Client + deep link** | `static/src/js/chat_patch.js`, `static/src/xml/cards.xml`, `pb_approval_config/static/src/js/inbox.js` (+ its xml if needed), `pb_approval_config/models/inbox_facade.py`, `pb_home_hub/static/src/js/home_hub.js` | P3: crit-6, crit-7; P4: link-1 (BLOCKER), link-3, link-4, vi-13, test-1, test-2 |
| **F Learn** | `pb_learn/**` content + scenario player, `docs/tutorial_poc/author/**` | P4: crit-2 (Learn half), link-6 |
| **D Vietnamese** (after C) | `payai/registry.py`, `payai/resolve.py`, `payai/phrases_vi.py`, `payai/runner.py` (only the go-ahead word list near :68), `payai/i18n.py`, `tests/test_payai_p4.py` | P4: vi-1..vi-12, crit-3, test-3, test-4, test-5, test-7; P3: wf-9 |
| **G Catalogues** (last) | every `i18n/vi_VN.po` touched, nothing else | P4: copy-1, copy-2, copy-5, copy-6, copy-7, copy-10, po-1; + Vietnamese for every msgid A–F added/changed |

Notes per cluster:
- **A**: P3:sec-1 — the decide switch must be read from the REQUEST's company (the engine request / its record's
  company), not `env.company`. P3:corr-1 — distinguish a genuine "state moved" (lock revision / fingerprint) from any
  other engine exception; show the engine's own message (plain) for the latter, never loop. P3:corr-2 — read the
  engine's result state after `decide` (blocked/pending/approved) and word the done card from it; reuse PA39
  `_route_steps` for "who comes next". P3:corr-3/ux-8/sec-2 — Remind: gate re-checked on press; "already reminded"
  only when a reminder by THIS person for THIS step exists today in the user's tz; only claim "sent" when the outbox
  accepted it. P3:crit-5 — never name a delegate/hand-over the asker cannot see on screen (check with the same
  access the Approvals inbox uses). P3:ux-4 — use the app's own "Turn it down / Turned down" wording if that is what
  the Approvals inbox shows (check pb_approval_config's strings first) — keep the typed word REJECT / TỪ CHỐI unless
  the inbox's own word differs; report the decision.
- **B**: name vs scheme vs month vs status precedence must be decided by EXACT matches against the asker's visible
  people first (accent-insensitive, not capped at 40 — query employees directly with the same domain
  `_eligible_employees` uses, as the user), then schemes, then statuses. A named leaver → say so on the card
  ("X left on <date> — include?") instead of a silent 0 of N. P3:crit-3: a sentence with a send-back/reject verb
  routes to the Red action even when it mentions payslips.
- **C**: P3:crit-2 — when a reason question is answered, keep the ALREADY-RESOLVED request id from the pending task;
  never re-resolve from the original words. P3:crit-4 — while a reason question is open, "cancel"/"hủy", a new
  command (registry match with confidence) or a question exits the reason flow instead of becoming the reason.
- **E**: P4:link-1 is the blocker — follow its `fix`: `wantsArrival: true` on the approvals lens in
  `pb_home_hub/static/src/js/home_hub.js`, `arrival` prop on PbInbox, read `props.arrival.focus`, fall back to
  `props.action.context.pb_focus`, drop the `actionService.currentAction` fallback. Check how PbDashboard consumes
  `arrival` (home_hub.js:128–135) and clone it. Add a node-run test of `focusRequest` + arrival plumbing as far as
  possible without a browser, AND describe the browser check the main loop must do.
- **F**: P4:crit-2 — the two P4 Learn steps (Runs lesson "Or ask PayAI…", Approvals lesson tip "type APPROVE") must
  not show on a database where PayAI's actions are not available. Prefer a small step-level gate in the Learn player
  (e.g. `requires: "payai"` → a cached RPC/session flag true only when `pb_payai_actions` is installed AND the
  relevant tier switch is on for the user's company); if the player cannot take one cheaply, remove those two steps
  from the shared content and report it. Content is generated (`gen_learn_data.py`, memory: the generator wipes
  `pb_learn/i18n/vi_VN.po` — back it up and restore it). P4:link-6 wording.
- **D**: P4:vi-1 — question tails must not start amber/red actions but `run_status` phrases ending "thế nào / ra sao /
  sao rồi" must still reach run_status. P4:vi-5 — the spoken go-ahead list must not accept "đã" (folds to "dạ");
  compare unfolded, or require the full phrase. P4:crit-3 — English slash dates: day-first only for a vi_VN user;
  English user keeps month-first, and an ambiguous past date is asked, not assumed.
- **G**: catalogue rules (memory `po-translation-loading-rules`, PA51): `#. module:` first, then `#. odoo-python` /
  `#. odoo-javascript`, then `#: code:addons/<module>/<path>:0`; one line per msgid/msgstr; placeholders identical;
  run `scratchpad/po_gate.py` (server copy `/tmp/p4_po_gate.py`) over every touched file. Remove VI entries whose
  English msgid no longer exists in the source. P4:po-1 is in scope (om_hr_payroll file-only change; restart serves
  it). P4:copy-1 — use the access screen's real VI title (read it from the source/catalogue, do not guess).

## Deploy (main loop only, after the owner's go-ahead)
Per P4:crit-1 — do NOT `-u` om_hr_payroll / pb_audit / pb_payrun_wizard / pb_payroll_ai_insights: their changes are
code-string `.po` lines, served from disk at restart. `-u` on payobook only for modules with model terms / data / views
changed. Shared files (inbox.js, home_hub.js, Learn content, .po) go live on EVERY DB at restart (P4:crit-2) — the PO
gate and Learn gate must pass on the staged tree BEFORE rsync.

## FIX-1b — OWNER RULING 2026-10-13 (binding): PayAI never reaches Settings → Access and delegations
Owner, verbatim: "do not allow Settings->Access and delegations to be accessible or controled by PayAI at all. This is
to safeguard anyone changing roles through backdoor."
Also settles P3:sec-4 (no longer deferred): Red actions (approve / send back / reject, and Remind) are REFUSED when the
asker's Approvals screen is hidden or locked for them in Access and delegations (`pb.sidebar.item.visibility_for` /
`pb.access.surface_access`, including lent/delegated roles) — the Access-home half of the gate must be real for Red,
not "always on". Point the Red Actions at the sidebar item that really carries the Approvals inbox; if none exists that
can be locked per person, report it with evidence instead of inventing one.

Scope of "never reach" (all must hold, server-enforced, not just hidden in the UI):
1. No door: `open_screen` must refuse/omit every door whose target is the Access home or any of its lenses/tabs
   (roles, people passports, lent roles, delegations, hand-overs, approval delegations, access requests) — whether it
   arrives via the `pb_hub_palette` rows the client registers (`rpc_register_doors`), the server door list, a Learn
   lesson door, or a `pb_focus`/deep link. Build the deny-list from the code (biz_access, pb_settings settings_palette /
   settings_hub access lens, pb_approval_config delegation screens, the `va_access` alias in `resolve.py:77,91`), and
   match on action tag/xmlid/lens, not on label text.
2. No "Open Access and delegations" button on refusal cards (`gate.ACCESS_DOOR`, `runner.py:347`): replace with plain
   words "Ask your administrator to change this under Settings › Access and delegations." — no link.
3. Asking PayAI to open/change roles, access, permissions, delegations, hand-overs, lend a role (EN + VI) → a `never`
   refusal card: "PayAI does not open or change access. Go to Settings › Access and delegations yourself." No door.
4. No PayAI Action may write to any biz_access / role / delegation / hand-over model, directly or via a called method
   (add a test that scans the catalogue's execute paths and the models written during the full test suite if feasible;
   at minimum a static scan of `payai/*.py` for those model names in write/create/unlink calls).
5. Reading the visibility rules for the gate stays (that IS the safeguard).
Tests: open_screen for each denied door → refused, no door on the card; every refusal card has no access door;
"open access and delegations" / "change Lan's role" / "mở phân quyền" → never card; Red with the Approvals screen
locked for the asker → refused, decide never called.
