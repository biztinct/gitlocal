# FLEET P2B — Rings, windows, and the rollout job

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST, incl. ledger). Stands on P1
(`pb.release`, `sync_bring_in_step`, `release_state`) and P2A (`push_tenancy`, notices, `pb_tenancy`
on every tenant). Follow the ledger where a name differs from this doc.

## What this phase makes true (plain words)

1. A release reaches customers **in waves, never all at once**: a rehearsal on a restored copy,
   then the golden template, then the canary customer, then the early group, then everyone — with
   a watch period between waves and a rule that **stops the rollout on the first failure**.
2. Each customer is updated **inside their own night-time window**, in their own time zone, and
   their users are told the evening before and while it happens (P2A's bars, now automatic).
3. The person starts it; a background job does the work one customer at a time, with a lock so it
   can never run twice, a retry, and a log line per step. Pause / continue now / retry / skip /
   abort are buttons. The cockpit shows the rollout as rings lighting up — that is the hero moment.
4. A customer's record shows its ring, its window, and a timeline of every update it ever received.

## Binding NON-goals

- No alerts/emails on failure — P3 reads `pb.rollout.state == 'paused'`. P2B only records.
- No automatic rollout start. Cutting a release never starts a rollout (rail R1).
- No per-tenant code versions, no separate worker processes. Shared code; per-DB data upgrade.
- Do not change P1's unit (`sync_bring_in_step`) beyond adding a `runner` hook if you need one.

## Verified facts for this phase

- Threaded server (no `workers`): cron jobs run as threads in the same process; NO cron time
  limit applies (ledger). One task = one `sync_bring_in_step` = minutes. `ir.cron` skips a job that
  is already running (row lock) — still take your own lock on `pb.rollout` (`FOR UPDATE SKIP LOCKED`)
  so a manual "Run now" RPC and the worker cannot both act.
- Log file `/var/log/odoo/odoo-server.log` is `-rw-r--r-- odoo:odoo` — the process can read it.
  Lines look like `2026-09-02 14:11:54,601 2811793 INFO p9clone odoo.modules.loading: Modules loaded.`
  i.e. `<ts> <pid> <LEVEL> <db> <logger>: …`. The health gate greps `ERROR <db> ` since the task
  started (read the last ≤ 20 MB; do not read the whole 76 MB file).
- Tenant time zone: `res_partner.tz` of company 1 on abm = `Asia/Ho_Chi_Minh` (read via
  `_pg_cursor` — read-only). Store it on `pb.tenant.tz` at first use; default `Asia/Ho_Chi_Minh`.
- Staging restore + drop: `restore_staging` (`service.py:1509`), `drop_staging` :1535, naming
  `<slug>-staging`. P1 allowed `sync_bring_in_step` on a `-staging` name.
- Rehearsal source: the FIRST canary tenant's latest done backup (or the largest live tenant's if
  no canary). A rollout with zero live tenants still runs rehearsal + template.
- P1's result dict from the unit (installed/updated/skipped/seeded/release stamp) is what a task
  stores as `result`.

## Architecture

### Models (`pb_tenants/models/rollout.py`)

- `pb.tenant` gains: `ring` Selection `canary` / `early` / `everyone` (default `everyone`),
  `maintenance_start` Integer hour (default 22), `maintenance_hours` Integer (default 3), `tz` Char.
- `pb.rollout`: `release_id` (required), `state` (`draft`/`running`/`waiting`/`paused`/`done`/`aborted`),
  `current_ring` (`rehearsal`/`template`/`canary`/`early`/`everyone`), `watch_hours_canary` (24),
  `watch_hours_early` (48), `ring_started_at`, `ring_done_at`, `started_at`, `finished_at`,
  `reason` (why paused/aborted, plain English), `started_by`, `task_ids`, computed counts.
- `pb.rollout.task`: `rollout_id`, `ring`, `tenant_id` (nullable for rehearsal/template),
  `target_db` (Char: the DB name actually acted on — `abm-staging`, `payobook_template`, `abm`),
  `state` (`queued`/`running`/`done`/`failed`/`skipped`), `run_now` Boolean, `notified_at`,
  `scheduled_for` (next window open, computed), `started_at`, `finished_at`, `attempts`,
  `result` (Text JSON), `error` (Text), `health` (Text JSON: probe code, ms, skipped, error lines).
  ACL `base.group_system` on both.

### Pure decisions (`pb_tenants/models/rollout_rules.py`, tests T1–T6)

- `RING_ORDER = ('rehearsal', 'template', 'canary', 'early', 'everyone')`.
- `plan_tasks(release, tenants, rehearsal_source) -> list[dict]` — one rehearsal task
  (`target_db = <source>-staging`), one template task, then tenants grouped by ring in order;
  decommissioned/error tenants excluded; draft/provisioning excluded with a reason list.
- `window_open(now_utc, tz, start_hour, hours) -> bool` and `next_window(now_utc, tz, start_hour,
  hours) -> datetime_utc` (handles wrap past midnight; DST-safe via `zoneinfo`).
- `eligible(task, now_utc) -> bool` — `run_now` or (`ring in (rehearsal, template)`) or window open.
- `health_verdict(probe_code, skipped, error_lines) -> (ok: bool, reason: str)` — plain-English
  reason ("The site did not answer", "2 parts were skipped at start-up", "3 errors in the log").
- `advance(rollout_snapshot, now_utc) -> ('run', task) | ('wait', until) | ('advance_ring', ring)
  | ('done',) | ('pause', reason)` — the whole state machine as a pure function over a plain dict
  snapshot: current ring's tasks + states, ring_done_at, watch hours, the watch-period health
  re-probe results. This is the function the worker calls and the function the tests hammer.
- `notice_for(task, tenant_tz, when) -> dict` — the P2A notice payload for "tonight between
  22:00 and 01:00" (pre-notice) and "being updated right now" (in-progress).

### Facade (`service.py` or `rollout.py` service mixin)

- `rollout_plan(release_id)` (dry, returns the task list + warnings), `rollout_start(release_id,
  watch_canary, watch_early)` — refuses when the release has no notes ("Write what changed first —
  customers will read it"), when the master is behind its files (P1), when another rollout is
  running/paused, when `pb_tenancy` is missing on any target (list them — P1's screen installs it).
  Creates rollout + tasks, `state=running`, `current_ring=rehearsal`, then runs the worker ONCE
  synchronously for the rehearsal task so the person sees the first result on screen.
- `rollout_tick(rollout_id)` = one worker step (also the cron body): lock; `advance()`; on `run`:
  mark task running, `attempts += 1`; for a tenant task: push in-progress notice (P2A), run the
  unit on `target_db`, health gate (probe + skipped + log since start), clear the notice, push
  release params on success; write `result`/`health`; on failure → task `failed`, rollout `paused`
  with `reason`, in-progress notice cleared, NO release params pushed. For rehearsal: restore
  staging from the source backup, run, health, **drop staging**; failure pauses like any task. For
  template: run, verify crons re-disabled (rail R8), no notice (no users).
  On `advance_ring` → set `current_ring`, `ring_started_at`; on `wait` → state `waiting`; on
  `done` → state `done`, `finished_at`.
- Pre-notices: `_cron_rollout_notices` hourly — for queued tenant tasks whose next window opens
  within 24 h and `notified_at` is empty → push the pre-notice (P2A), set `notified_at`.
- Controls: `rollout_pause`, `rollout_resume` (clears reason; failed task stays failed until
  `task_retry` requeues it or `task_skip` skips it — skipping a CUSTOMER requires typing its slug),
  `rollout_continue_now` (ends the watch period early; records who), `task_run_now` (sets
  `run_now`; the next tick runs it regardless of window), `rollout_abort` (typed confirm; queued
  tasks → skipped; running task finishes).
- Cron `Payobook Tenants: rollout worker` every 5 min (new record in `data/cron.xml`, noupdate
  file → add, don't edit), body: tick the single running rollout. `Payobook Tenants: rollout
  notices` hourly.

### Screen

- Sync screen (P1) gains a **Rollouts** section under the release banner: the current rollout as
  five rings in a row (rehearsal · template · canary · early · everyone), each ring a card with
  its tasks as avatar chips whose dot is queued (muted) / running (pulsing indigo) / done (green)
  / failed (rose) / skipped (muted strike). The active ring is raised; a waiting ring shows a
  countdown "Watching the canary — 17 h left" with **Continue now**. Paused → a rose bar with the
  reason and Retry / Skip / Resume / Abort. Done → green summary "Release 2026.09.03 is on 1 of 1
  customers. Took 14 min." Past rollouts: a compact list below (release, when, outcome).
- "Roll out release X" button beside "Cut a release" → dialog: the plan (tasks in order, each with
  "tonight 22:00–01:00 (their time)" or "right away"), watch hours (two number inputs with
  defaults), a plain paragraph explaining what happens and that nothing starts until they press
  **Start rollout**. Refusals appear inline with their next step.
- Tenant detail → new tab **Updates**: ring (segmented, with one-line meanings), window (start
  hour + hours, tz shown), timeline of this tenant's tasks (release, when, outcome, duration,
  "show the detail" → result JSON rendered as the P1 result panel), and "Update now" (runs the P1
  unit for this tenant outside a rollout — same guards, same rehearsal advice).
- Keyboard: `Esc` closes dialogs; the rings row is focusable and arrow keys move between rings.

### Tests

- **T1** `plan_tasks` order and exclusions; **T2** `window_open`/`next_window` incl. wrap and
  DST; **T3** `eligible`; **T4** `health_verdict` reasons; **T5** `advance` — every branch: run,
  wait (watch not elapsed), advance (elapsed + healthy), pause (a failed task; a watch-period
  health re-probe failure), done; **T6** `notice_for` copy.
- **T7** Model: `rollout_start` refusals (no notes; another running; missing `pb_tenancy`), task
  creation, `rollout_tick` with a monkeypatched runner (`_run_unit = lambda db: fake_result`) —
  drives one whole rollout to `done` in a transaction; a failing fake pauses it with the reason;
  `task_retry` requeues; `rollout_abort` skips queued.
- **T8** Lock: two ticks in the same transaction with the row locked → second returns "busy".

### Live validation

- **L1** Deploy; `-u pb_tenants -d payobook`; tests green.
- **L2** Cut release (notes required) → Roll out. Watch the rehearsal run (abm-staging restored,
  updated, health ok, dropped) and the template task, live on screen.
- **L3** abm is `canary`; its window is tonight. Use **Run now** for the validation (say so).
  Confirm: pre-notice bar on abm before, in-progress bar during (Chrome on abm while the task
  runs), cleared after, release toast + What's new on abm after, rollout `waiting` with countdown,
  **Continue now** → `done`.
- **L4** Failure path: run a rollout against a deliberately broken target (e.g. rehearsal source
  backup path renamed) → task failed, rollout paused with a plain reason, notice cleared, nothing
  pushed; fix; Retry → done. Restore the backup path.
- **L5** Chrome-MCP screenshots to `docs/handovers/fleet_p2b_shots/`: plan dialog, rings in each
  state, paused bar, Updates tab, tenant timeline.
- **L6** Cron window 15 min clean on every DB; asset ritual on payobook.

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero: the rings lighting
up with live avatars (Vercel deployment timeline quality). Zero dead-ends: every refusal names its
next step; every task failure shows reason + Retry/Skip. Plain language ("wave", "watch period",
"window", "canary customer" — explain canary once in a tooltip). Motion with purpose (pulse on
running, ring raise on advance, countdown tick). No "Odoo".

## Deploy + verify — as P1/P2A. Manifest `pb_tenants` → 19.0.1.7.0.

## Report back — as P2A's list, plus: the measured duration of one tenant task, the exact
health-gate log query you used, and the DST test cases you wrote.
