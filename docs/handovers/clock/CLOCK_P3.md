# CLOCK-3 — Trust: alerts, re-check, backfill progress, lessons, demo world

Read first: `CLOCK_LEDGER.md` (§0 rules bind verbatim; §2 D1–D13; §3 G1–G15),
`CLOCK_P2_REPORT.md` §10 (what to alert on) and §11 (open questions),
`CLOCK_P1_REPORT.md` §8 (lessons to update), then
`docs/design/biometric/BIOMETRIC_DESIGN.md` §3.5.

## 1. Scope (one commit each, in this order)

1. **Alerts model + 15-minute watcher** (`pb.clock.alert`, cron).
2. **Where alerts show**: the lens "Attention" strip, the Time hub ribbon
   count, an Integrations board card, the Home inbox card, and a daily
   email digest to attendance managers.
3. **Nightly re-check** (35 days) + "Last full re-check" on the lens.
4. **Backfill progress** for a big first upload / resend.
5. **Lessons, tours, screen manifest** for Time clocks + Import mode cards
   (EN + VI).
6. **Demo world seed** on payobook.com: a demo machine with two weeks of
   punches for the demo cohort (adds only, never deletes — memory
   `keep-demo-data-payobook`).
7. Tests, Vietnamese, deploy ×4, browser validation, report, programme
   closeout (`CLOCK_CLOSEOUT.md`).

### Binding non-goals

- No change to the receiver protocol, the pairing rules D1–D11, or nginx.
- No IP-only machine route (P2 §11.2) — waits for the client's photo; put
  the two options in the closeout.
- No `.mdb` reader; no Bridge; no late-minutes payroll input.
- No SMS / push; email only, and only to attendance managers of the company.
- No new rail item; everything lives in the existing Time clocks lens,
  Integrations board, Home inbox.

## 2. Verified facts for this phase

- Lens facade `pb.clock.lens` (`pb_clock/models/clock_lens.py`), devices
  `pb.clock.device` with `state`, `last_seen_at`, `last_punch_at`,
  `clock_skew_s`, `plain_connection`, `first_seen_at`, `history_from`;
  commands `pb.clock.command` (`state`, `return_code`); punches
  `pb.clock.punch` (`state` incl. `held`, `ignored_before_start`);
  `hr.attendance.pb_clock_auto_closed`. Pairing cron
  `pb_clock.cron_pair_punches` (5 min, `limit=5000` per run — read
  `clock_pairing.py run()` for the real signature).
- Time hub ribbon + per-lens counts: `pb.time.hub.get_hub_summary`
  (`pb_time_hub/models/time_hub.py:117-177`); pb_clock already extends
  `_extra_lens_counts` (`pb_clock/models/time_hub.py`).
- Integrations board: `pb.integrations.get_board`
  (`pb_integrations/models/pb_integrations.py:116-186`) returns `kpis`,
  `connectors` rows and `hints` (`_sourcing_hints`, "a COUNT plus the
  drill-down"); the JS renders hints as actionable chips. Extend with
  `_inherit = 'pb.integrations'` and add a **hint** per open alert kind plus
  one "Time clocks" pseudo-connector row — read `_connector_row` (:186-209)
  for the row shape and how `connection_status` colours it.
- Home inbox cards: `pb.dashboard.get_home_data`
  (`pb_dashboard/models/home_data.py:124-…`, inbox `cards` counted at
  :704). Find how other modules add a card (grep `_inherit = 'pb.dashboard'`
  across `pb_*`) and clone that; if there is no hook, add one
  (`_extra_inbox_cards()`) in pb_dashboard and bump it.
- Email: `pb_comp_ben/data/mail_template_data.xml` +
  `pb_comp_ben/models/payroll_calendar.py` and
  `pb_contract_lifecycle/data/conversion_mail_data.xml` are the templates
  precedent (white-label footer comes from `biz_mail_debrand`; never write a
  brand name yourself). Attendance managers =
  `hr_attendance.group_hr_attendance_manager` users of the company with an
  email.
- Learn: `pb_time_hub/learn_manifest.py` (screen `wftime`, EN+VI, `derived`
  fields with `from`/`how`/`if_changed`/`anchor`);
  `pb_learn/static/content/learn_content.json` keys `screens`, `scenarios`,
  `missions`, `stations`, `intents`; entries `sc_wftime`, `wftime`,
  `approveot`, `L21`, `wfclose`; anchors `wf-time`, `wf-exceptions`;
  `docs/tutorial_poc/author/data.js` scenes on `wftime`. Memory rule: the
  generator wipes `pb_learn/i18n/vi_VN.po` — restore it if you run it.
- Demo world: `pb_demo/models/demo_workforce.py:93 _seed_attendance_shifts`
  (cohort, company, tz, today, monday) is the shape to clone;
  `pb_demo/models/demo_generator.py` is the entry; demo records are
  prefixed `DEMO` (memory `demo-data-naming-rule`), never "RIZE".
- Standing: `filter_deploy.sh full` resets crons to the pre-deploy set (G3)
  — switch the two new crons on by hand per DB after the deploy, off on
  `payobook_template` with their ids appended to
  `pb_tenants.template_active_crons`.

## 3. Alerts (`pb.clock.alert`)

Fields: `company_id`, `kind` (Selection below), `device_id`, `employee_id`,
`day` (Date), `state` (`open`, `resolved`, `muted`), `first_seen_at`,
`last_seen_at`, `resolved_at`, `muted_until`, `detail` (Char, plain
English, computed at raise time, e.g. "Factory 2 has not called in since
14:02"), `key` (Char, unique per company: `kind|device|employee|day` — the
watcher upserts on it, so one condition is one row that updates, never a
pile).

| kind | Raised when | Resolves itself when |
|---|---|---|
| `silent` | allowed terminal, `last_seen_at` > 15 min ago | it calls in |
| `no_punches` | allowed terminal, a working day (company calendar), no punch for 6 h between 06:00 and 22:00 local | a punch arrives |
| `clock` | `clock_skew_s` beyond 60 s with ≥ 3 samples and no successful `set_time` in 6 h, **or** ≥ 3 punches in the future ignored today | skew back under 60 s |
| `pending` | `state = pending` for > 24 h | allowed or blocked |
| `auto_closed` | `pb_clock_auto_closed` day older than 2 days with no correction (`hr.attendance.correction` not refused) **and** the day's week not yet approved | a correction exists or the day is edited |
| `command_failed` | two consecutive failed commands on a device | a later command succeeds |
| `plain` | `plain_connection` is True | the device last spoke over HTTPS |
| `held` | ≥ 1 `held` punch older than 24 h for an employee-day | the punch leaves `held` |
| `backlog` | pending-to-pair punches > 20 000 for > 30 min | backlog < 1 000 |

Watcher cron "Time clocks: watch machines and days", every 15 min,
`numbercall=-1`, one pass per company, sudo, wrapped per company in
try/except (one company's error never blocks another's alerts). `muted`
alerts (lens "Mute for a week") do not re-open until `muted_until`.

## 4. Where alerts show

1. **Lens "Attention" strip** at the very top (above "Machines asking to
   connect"): grey at zero ("Nothing needs attention."), otherwise one row
   per open alert: icon · the `detail` sentence · "since 14:02" · a door
   (machine card, the held table, the auto-closed table, the pending strip)
   · Mute for a week (manager). Keyboard: ↑↓, Enter opens the door.
2. **Time hub ribbon**: when any clock alert is open, the ribbon sentence
   gains " · 2 time-clock alerts" and the lens badge counts open alerts
   instead of unknown numbers when alerts > 0 (unknown numbers still
   count when there are no alerts). Read `get_hub_summary` before changing
   the sentence; keep its tone rules.
3. **Integrations board**: a "Time clocks" row (name, `connected` when all
   terminals are fine, `error` when any alert of kind silent/clock/
   command_failed, `disconnected` when no terminal yet) + hints
   "3 machines need attention", "12 days missing a check-out", each
   opening the lens on the right block (`doAction` with `pb_lens: 'clocks'`
   — the arrival protocol in `time_hub.js _arrival()`; include `views` in
   any act_window dict).
4. **Home inbox card** "Time clocks" with the open-alert count and the top
   sentence, same door; hidden at zero.
5. **Daily digest email** at 08:00 company-local, only when ≥ 1 alert is
   open: subject "Time clocks: 3 things need attention", body = one line per
   alert in plain words + one link to the lens; to attendance managers of
   the company; one email per company per day; template in XML with EN + VI
   (`lang` of the recipient). **Immediate** email (max one per device per 6
   h) only for `silent` and `no_punches` on a working day. Record sends on
   the alert (`last_mailed_at`). Nothing about machines is ever mailed to an
   employee.

## 5. Nightly re-check

Cron "Time clocks: nightly re-check" at 02:30 company-local (one cron,
loops companies, checks the hour in each tz — the same pattern the digest
uses): for every employee with ledger activity in the last 35 days, run
`repair_employee` for days NOT locked / frozen / approved / corrected (the
existing D4 guards do the skipping), then compare: device attendances
whose punches are no longer present or whose recomputed `(check_in,
check_out)` differ → fix them (that is what the re-pair does) and count
the fixes. Store on the company: `pb_clock_last_recheck_at`,
`pb_clock_last_recheck_fixed`. Lens settings card shows "Last full re-check:
today 02:31 · 0 days changed". If > 0 days changed, raise an alert kind
`recheck_changed` with the count (resolves on the next clean run) — add it
to §3's table.

## 6. Backfill progress

When a device uploads history (stamp 0 → thousands of lines) or a resend
runs, the machine card shows a progress block: "Receiving history: 42 300
punches so far · 18 900 waiting to pair · about 25 minutes left" (rate =
pairing throughput over the last 5 runs). Mechanics: the pairing cron
re-triggers itself (`_trigger()`) at the end of a run while `new`/`matched`
punches remain, so a 100 000-line backfill finishes in minutes, not 100
runs × 5 min; the lens refresh (30 s) redraws the block; the block
disappears when nothing waits. Also a quiet line on the Attention strip
while a backfill runs ("Factory 1 is sending its history — 62%").

## 7. Lessons, tours, manifest

- `pb_time_hub/learn_manifest.py`: add the Time clocks lens column and the
  Import mode cards (EN + VI, `derived`, `anchor: 'wf-clocks'` — add the
  `data-coach` anchor to the lens root).
- `pb_learn` content: a new screen entry `wfclocks` (purpose, before/after,
  fields), a scenario "A machine stops sending" (silent alert → machine
  card → what to check), a mission step in the attendance path; update
  `sc_wftime`, `wftime`, `approveot`, `L21`, `wfclose`, the `time`
  tutorial nodes and `docs/tutorial_poc/author/data.js` scenes that list the
  Time lenses. Every sentence EN + VI, plain words, no "Odoo".
- Run the Learn truth gate the way LEARN REFRESH did (see
  `docs/handovers/learning/L7_REPORT.md` for the command) and restore
  `pb_learn/i18n/vi_VN.po` if the generator wiped it.

## 8. Demo world seed (payobook.com only)

In `pb_demo`: `_seed_time_clocks(cohort, company, tz, today, monday)` —
one allowed terminal "DEMO Factory gate" (serial `DEMO-0001`, Asia/Ho_Chi_Minh),
`history_from` = monday − 7, punches for the demo cohort for the last two
weeks that MATCH the shifts `_seed_attendance_shifts` already made (so
pairing reproduces the same days; where a grid row already exists the punch
goes `held` — avoid that: seed punches only for cohort members and days
with no attendance yet), plus one unknown number `DEMO-999`, one night
shift, one double tap, one forgotten check-out. Idempotent (dedup) and
additive only. Wire it into the generator after attendance; run it on
payobook.com once and report the counts. Never on rize or the template.

## 9. Tests (`pb_clock/tests/test_alerts.py`, `test_recheck.py`, `test_backfill.py`, `pb_demo/tests/`)

1. `silent`: device last seen 16 min ago → one open alert; seen again → resolved; watcher twice → still one row.
2. `no_punches`: working day, 6 h without punches inside 06–22 local → alert; weekend → none.
3. `clock`: skew 90 s, 3 samples, no set_time in 6 h → alert; set_time done + skew 10 s → resolved.
4. `pending` after 24 h → alert; Allow → resolved; Block → resolved.
5. `auto_closed`: 3-day-old auto-closed day, no correction → alert; correction created → resolved; week approved → no alert.
6. `command_failed` on two failures → alert; a success → resolved.
7. `plain` while plain_connection → alert; HTTPS contact → resolved.
8. `held` > 24 h → alert; punch paired → resolved.
9. `backlog` > 20 000 for 30 min → alert; drained → resolved.
10. Mute for a week → not shown, not mailed, re-opens after `muted_until`.
11. Digest: two open alerts at 08:00 local → exactly one `mail.mail` per company to managers only (no employee address), EN for an `en_US` manager, VI for a `vi_VN` one, no "Odoo" in subject/body; 07:00 → none; next day → one more.
12. Immediate `silent` mail: once, then not again within 6 h.
13. Ribbon + lens badge count open alerts; Integrations row status per rule; Home inbox card hidden at zero.
14. Nightly re-check: a device attendance edited by hand (sudo write check_out −1 h) is restored, `pb_clock_last_recheck_fixed = 1`, alert `recheck_changed`; a locked day is untouched.
15. Backfill: 12 000 `new` punches → the pairing cron re-triggers itself until none remain; the lens payload carries the progress block; it disappears after.
16. Demo seed: idempotent (run twice → same counts), adds only, DEMO prefix, pairs into the expected days, nothing `held`.
17. Learn truth gate passes; manifest EN/VI complete.
18. CLOCK-1 + CLOCK-2 suites still green (run all 64).
19. No "Odoo" in any new string (grep gate incl. mail templates and learn content).

Throwaway copy of p0clone (G7/G8), SCHEMECTX recipe; `freeze_time` for the clock-based cases.

## 10. Browser validation

rize.payobook.com with the emulator from the box: make a machine silent
(stop the emulator) and watch the Attention strip, ribbon, Integrations row
and Home card appear within 15 min (trigger the watcher cron by hand to
avoid waiting); mute, unmute; resume the emulator → resolved. Open the
Learn lesson for Time clocks. payobook.com: run the demo seed, open Time ›
Time clocks and screenshot the populated lens (this is the sales demo
screen — make it look its best; fix what you see). Console clean; shots to
`docs/handovers/clock/shots/p3-*.png`. Remove the rize test data; keep the
payobook demo data.

## 11. Deploy

Normal tier ×4 (`pb_clock pb_integrations pb_dashboard pb_time_hub
pb_learn pb_demo` — only those changed; `pb_demo` is installed on
payobook only), G3 cron handling for the two new crons, PO + SCSS gates,
`/opt/deploy-notes.md`, heads-up to sessions, lock check, asset purge +
version bump, hashes + versions ×4.

## 12. Report + closeout

`CLOCK_P3_REPORT.md` (format of P1 §10) and `CLOCK_CLOSEOUT.md`: what the
programme delivers (plain English, for the owner), the setup-day checklist
link, known limits (IP-only machines, `.mdb`, Bridge, late minutes), the
owner questions still open (certificate renewal day; the client's
follow-ups), and the CLOCK-4/5 backlog with sizes.
