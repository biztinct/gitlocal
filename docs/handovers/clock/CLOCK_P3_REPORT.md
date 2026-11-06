# CLOCK-3 report — trust: alerts, re-check, backfill progress, Learn, demo world

Delivered 2026-11-05 (UTC). Live on payobook, payobook_template, p0clone, rize.
`sudima` exists on the box (made by another session at 13:21 UTC) and was
**not** upgraded — it still runs pb_clock 19.0.1.1.0; the coordinator upgrades
it separately.

## In plain words (for the owner)

- **Time › Time clocks now tells you when something needs a person.** Right
  under the live sentence there is a short note, like a colleague's: grey
  "Nothing needs attention." most of the time; otherwise one plain sentence per
  problem — "Factory 2 has not called in since 14:02." — with a button that
  takes you to the right place, and (for a manager) "Mute for a week".
- **It watches every 15 minutes** for: a machine that stopped calling in, no
  punches for 6 hours on a working day, a machine clock that is off and could
  not be set, a machine asking to connect for more than a day, a day missing
  its check-out for more than two days, two failed requests to a machine, an
  old machine on a plain connection, punches on hold for more than a day, a
  big pile waiting to be paired, and a night re-check that had to fix days.
  Each problem clears by itself once it is gone.
- **You see it in four other places too:** the line above the Time tabs
  ("1 time-clock alert · Open time clocks →") and the tab's number; a "Time
  clocks" row on the Integrations page (Connected / Needs attention / No
  machine yet, with chips like "1 machine needs attention"); a chip on Home
  ("1 time-clock alert", hidden when there is nothing); and email.
- **Email**: attendance managers get a summary at 08:00 when something is
  open, in their own language, and a short note when a machine stops calling
  in on a working day (at most once every 6 hours per machine). Never to
  employees. Each company has a switch "Email the attendance managers" in the
  settings card. **It is switched off on the demo company on payobook.com**
  (prospects log in there).
- **Every night at 02:30** Payobook rebuilds the last 35 days of machine days
  from the punches and says what it found: "Last full re-check: today 02:31 ·
  0 days changed". Days a person decided about (closed, approved, corrected,
  typed in) are never touched.
- **A machine sending months of history** shows a progress bar: "Receiving
  history: 42,300 punches so far · 18,900 waiting to pair · about 25 minutes
  left", and pairing keeps running until it is done instead of every 5 minutes.
- **Learn** knows the new tab: Time's lesson has a Time clocks step, the guide
  lists "Time clocks" and the "Time-clock punches" import card, and there is a
  walkthrough "A machine stops sending".
- **payobook.com demo**: a "DEMO Factory gate" with two weeks of punches for
  24 demo people — 535 punches, 214 work days, a night shift, a double tap, a
  forgotten check-out and one unknown number. The screen opens on "Last punch
  18 min ago, DEMO Factory gate · 22 people punched today".

## 1. Commits (branch 19.1, pushed)

| Hash | What |
|---|---|
| 57174a3e1 | Step 1 + 3 + 4 server side — `pb.clock.alert` + watcher job, the two emails, nightly re-check job, pairing re-trigger + throughput, lens facade (attention, mute/unmute, re-watch, backfill, re-check line), door action, tests 1–15, 19 |
| 6647f41f2 | Step 2 screens — Attention strip, Time hub ribbon hook, Integrations row, Home chip, backfill bar, settings line + email switch |
| db9addd15 | Step 5 — Learn: `wfclocks` screen + manifest, `sc_wfclocks`, L21 step, wftime column + Import card, anchors |
| 5ab4d2494 | Step 6 — demo seed in pb_demo + test 16 |
| 16b6791a1 | Vietnamese (pb_clock from the export, 116 new; pb_time_hub 2; pb_integrations 11; pb_dashboard 2 + pot) |
| af483e94d | pb_clock version bump missed in the first deploy (G16) |
| a1bfa3742 | browser fix — seed never starts a still-open day for someone with an older open row (G17) |
| aa62ee501 | browser polish — "noticed 01:42" on the strip; a by-file machine says so with its people count |
| (this) | report, closeout, ledger, shots |

Versions: pb_clock 19.0.1.2.1, pb_time_hub 19.0.1.5.0, pb_integrations
19.0.1.16.0, pb_dashboard 19.0.2.2.8, pb_learn 19.0.20.8.8, pb_demo 19.0.1.14.1.

## 2. Tests 1–19

Throwaway copy `clk3test` (pg_dump p0clone; jobs, mail servers and logins off;
scratch addons; ports 8193/8192), dropped at the end. **pb_clock: 84 of 84 pass**
(CLOCK-1 30 + CLOCK-2 34 + CLOCK-3 20), last run after the final commit.

| # | Case | Test | Result |
|---|---|---|---|
| 1 | silent: seen 16 min ago → one open row; twice → still one; calls in → resolved; quiet again → the same row re-opens | test_01_silent | PASS |
| 2 | no punches 6 h inside 06–22 on a working day → alert; punch → resolved; Saturday → none; 05:00 → none | test_02_no_punches | PASS |
| 3 | skew 90 s ×3, no set_time → alert; set_time done + skew 10 s → resolved; a queued correction → no alert; 3 future punches ignored today → alert | test_03_clock, test_03b | PASS |
| 4 | pending > 24 h → alert (2 h → none); Allow → resolved; Ignore → resolved | test_04_pending | PASS |
| 5 | auto-closed 3+ days, no correction → alert; under 2 days → none; correction → resolved; refused → open again; week approved → none | test_05, test_05b | PASS |
| 6 | two failed commands → alert; a success → resolved; one failure → none | test_06 | PASS |
| 7 | plain connection → alert; HTTPS contact → resolved | test_07 | PASS |
| 8 | held < 24 h → none; > 24 h → alert "2 punches of …"; paired → resolved | test_08 | PASS |
| 9 | backlog (thresholds patched to 20 / 5): not before 30 min; then alert; drained → resolved, memory cleared | test_09 | PASS |
| 10 | Mute → not in the strip, listed as muted, not mailed, back after `muted_until`; officer may not mute; Bring back | test_10 | PASS |
| 11 | 07:00 → no summary; 08:05 → one EN email (EN manager only) and one VI email (VI manager only), no employee address, no brand word; same morning → none; next day → one more | test_11 | PASS |
| 12 | immediate silent note once; not again within 6 h; Saturday → none | test_12 | PASS |
| 13 | ribbon `extra` + text, lens badge = open items, ribbon lens `clocks`; Integrations disconnected → error ("1 machine needs attention") → connected; Home chip n → 0; plain user sees none | test_13, test_13b (people's days group into one strip row) | PASS |
| 14 | hand-edited time-clock day restored, `fixed = 1`, alert `recheck_changed`, closed day untouched, once a night, next night 0 → resolved, idempotent; a deleted day is rebuilt | test_14, test_14b | PASS |
| 15 | 12 000 new punches → job asks to run again 3 runs (5 000 + 5 000 + 2 000), card shows received / waiting / 41 % / minutes left half-way, block gone after, idle run does not re-trigger | test_15 | PASS |
| 16 | seed: 23 empty codes filled (a set one kept), DEMO machine by file, emails off, run twice → 0 added, pairs with nothing waiting or held, night shift crosses midnight, 1 double tap, 1 forgotten check-out, DEMO-999 unknown, lunch taps as breaks, a busy day untouched, an old open row untouched | pb_demo test_16_seed | PASS |
| 17 | Learn truth gate: no finding on `wftime` / `wfclocks` (the 14 findings are the known pay-run / employee / treatment ones); generator clean; `pb_learn/i18n/vi_VN.po` untouched; contract check: only the known `pe-filters` | pb_learn suite + authoring tools | PASS |
| 18 | CLOCK-1 + CLOCK-2 suites (64) | /pb_clock | PASS |
| 19 | no brand word in new strings, mail template, Learn content, msgstr of the 5 modules | test_19_no_brand_name_in_new_strings | PASS |

Other suites on the same copy: pb_time_hub 31/31; pb_dashboard 77, 1 fail
(`TestHomeData.test_05` — **same failure on the untouched module**, baseline run);
pb_integrations 71, 1 fail (`test_the_ledgers_never_sudo` — the file had 7
`sudo(` before this phase); pb_learn 494: 3 failures + 3 errors, all
pre-existing (truth gate on pay-run screens, two stray anchors in
pb_payrun_wizard / pb_contracts, `test_03b` composer, Statutory/Import "right
now" ×2). This phase fixed one pre-existing Learn failure (screen count 54→56)
and the Learn tests that it broke on the way (screen detection, practice copy,
phrases, icon) are green.

## 3. Browser validation

**rize.payobook.com** (open session), emulator run from the box (`TST-0003`,
Sydney zone). Time-clock emails were switched off on rize for the check so no
rize.farm address got a test note, and back on afterwards.

| Shot | What it proves |
|---|---|
| p3-01-rize-calm-strip-asking | the door action lands on Workforce › Time › Time clocks; ATTENTION grey "Nothing needs attention." while a machine asks to connect |
| p3-02-rize-silent-strip-ribbon-badge | machine silent (last call backdated 20 min, watcher run by its own job): "Test gate CLOCK-3 has not called in since 01:16." with its door; ribbon "1 time-clock alert · Open time clocks →"; tab badge 1 |
| (no file) | "Show the machine" scrolls to the card and lights it |
| p3-03-rize-integrations-row | Integrations: "Time clocks · 1 machine · last punch 2 min ago", chip "1 machine needs attention", badge Needs attention; the row opens the lens |
| p3-04-rize-home-chip | Home Needs you: "1 time-clock alert" (tooltip = the sentence); the chip opens the lens |
| p3-05-rize-muted | Mute: toast "Muted for a week…", strip grey, "1 muted for a week", ribbon and badge gone; Bring back restores all three |
| p3-06-rize-resolved | emulator calls again → watcher resolves it, "Connected · heard 1 min ago"; no email sent |
| p3-07-rize-settings-recheck-email | settings: "The first full re-check runs tonight at 02:30.", the email switch |
| p3-08 / p3-09 | Learn guide on Time: "Fields on this screen 6" incl. "Time clocks" and "Time-clock punches" |
| p3-10-payobook-demo-lens-top | payobook.com after the seed: "Last punch 18 min ago, DEMO Factory gate · 22 people punched today", one attention line (a forgotten check-out, "noticed 01:42", "Show the days"), DEMO-999, the missing check-out row |
| p3-11-payobook-demo-machine-feed | the machine card "Its punches arrive by file · 25 people on the machine", 229 punches this week |

Console: no errors on either site. Clean-up: rize's test machine, its 2 punches,
2 days and 1 alert removed through the model layer; rize holds no time-clock
data. payobook keeps the demo data.

Found and fixed in the browser: three demo people have open attendance rows
from 18 August (existing demo data, untouched), so their still-running day
today waited on hold — the seed now skips such a day (a1bfa3742) and the three
punches it had added were removed; the strip's second time now reads
"noticed …"; the by-file machine's card got its line.

## 4. Deploy

| Commit | Module → version | Window (UTC) | EXIT per DB | Jobs on before → after | Evidence |
|---|---|---|---|---|---|
| 16b6791a1 | pb_clock (files + data; manifest still 1.1.0), pb_time_hub 1.5.0, pb_integrations 1.16.0, pb_dashboard 2.2.8, pb_learn 20.8.8, pb_demo 1.14.0 | 14:22:21–14:27:13 | p0clone 0 · template 0 · rize 0 · payobook 0 (errors 0) | 33/29/76/44 → same (2 new jobs per DB created off) | `/tmp/clock3-run-20261105142221`, backups `/odoo/backups/clock3-run-20261105142221` |
| af483e94d | pb_clock 19.0.1.2.0 | 14:28:18–14:30:26 | 0 ×4 | 33/29/76/44 → same, then jobs switched on by hand → 35/29/78/46 | `/tmp/clock3b-run-…` |
| a1bfa3742 | pb_demo 19.0.1.14.1 (payobook only) | 14:43:27–14:44:46 | payobook 0 | 46 → 46 | `/tmp/clock3c-run-…` |
| aa62ee501 | pb_clock 19.0.1.2.1 | 14:48:35–14:51:08 | 0 ×4 | 35/29/78/46 → same | `/tmp/clock3d-run-…` |

New jobs (ids): payobook 149 watcher, 150 re-check (ON); p0clone 85, 86 (ON);
rize 85, 86 (ON); payobook_template 85, 86 OFF and appended to
`pb_tenants.template_active_crons` (so a new tenant gets them on).

Before the first deploy the live trees of all six modules equalled the
pre-change commit 5851960ff (nothing of another session's overwritten). Gates:
libsass OK (pb_clock, pb_integrations); PO gate 0 code rows without a value
(pb_clock 554, pb_time_hub 33, pb_integrations 421, pb_dashboard 267). After:
tree hash live = stage for all six; `latest_version` = manifest on all four;
sites 200; assets purged by the script. `ListAgents` is not available in this
session, so no heads-up could be sent; every START/DONE/DATA line is in
`/opt/deploy-notes.md` and the lock was free each time.

## 5. Design bar — self-score 8.5/10

- **Hero:** the Attention strip reads like a colleague's note — a small
  ATTENTION kicker, grey and dashed at zero with "Checked 3 min ago", amber
  rule and bell (one gentle ring) when something is open, one sentence per
  problem, "noticed 01:42", a door that scrolls and lights the right block,
  Mute for a week. Same sentence on Home's chip and in the email.
- **States:** zero, one, many (people's days group into one row: "3 days are
  missing a check-out…"), muted list with Bring back, backfill running (bar +
  quiet strip line), empty (strip hidden until something is connected),
  ribbon alone or added to exceptions, Integrations connected / needs
  attention / no machine yet.
- **Plain language:** every line in words, EN + VI, times in the machine's
  zone and the zone named when it differs from the company's.
- **Motion:** rows rise in a short stagger, the bell rings once, a door's
  target glows for two seconds, the backfill bar eases; nothing moves at rest.
- **Keyboard:** ↑/↓ and Enter in the strip; the Integrations row takes Enter.
- **Gaps:** the doors from Home and Integrations open the lens, not the exact
  block; the muted list has no "mute for a day" choice; the strip has no
  bulk "fix all"; the Home item is a chip (with the sentence as a tooltip), not
  a card of its own.

## 6. Deviations

1. **Commits**: steps 1, 3 and 4 share the facade and the job files, so the
   server side went in one commit and the screens in the next (CLOCK-2 did
   the same); Learn, demo and Vietnamese are their own commits.
2. **One email per company per language**, not one per company: test 11 asks
   for an English email to the English manager and a Vietnamese one to the
   Vietnamese manager, which cannot be a single email.
3. **Email switch per company** ("Email the attendance managers", default on)
   — not in the handover; needed because payobook.com's attendance managers
   include sign-up accounts, and to test on rize without mailing the client.
4. **Strip rows**: machine problems one row each; people's days (missing
   check-out, on hold) one row per kind with the count. The badge, ribbon,
   Home chip and email count these rows.
5. **The demo machine is a "punches by file" machine** (no live connection),
   so it never reads as a silent machine on the sales screen; the strip shows
   the forgotten check-out instead.
6. **The demo seed fills the empty clock number of 24 demo people** (1001–1024)
   — the only write to existing demo records; nothing else is changed.
7. **Doors open the lens, not the block**: Mission Control forwards only
   `pb_lens`/`pb_focus`; the strip at the top has the per-block doors.
8. **Learn**: Time clocks has no station/lesson of its own (listed as such);
   its step is in Time's lesson, plus the walkthrough. "Mission step" was read
   as the step in the attendance lesson.
9. **Ledger G14 / P2 §11.2 (IP-only machines)** — not built (non-goal); options
   in the closeout.
10. **pb_clock's version bump** was missed in the first deploy and shipped two
    minutes later (G16).

## 7. Gotchas

Appended to `CLOCK_LEDGER.md` §3: G16–G23.
