# WDGAP S5-F — report (follow-ups to Step 5 + back pay)

## PAUSED (owner pause, 2026-11-16)

**Where I stopped:** set-up done, no module code edited yet.

- Branch `wdgap-s5f` from `origin/19.1` (this commit is the only one on it).
- Local test database **`wdgap_s5f_t`** (copy of `upd_p6_t_tpl`; `-u all` plus
  `-i pb_loans,pb_fund_payments,pb_retro,pb_leave_setup,pb_time_pay,pb_shift_patterns`;
  exit 0, no errors). **Kept on purpose**, filestore `~/odoo19/data/filestore/wdgap_s5f_t`.
- Scratch folder (not in git):
  `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/684f830c-6ed1-451c-a2de-0875eedd2479/scratchpad/s5f/`
  holds `odoo.conf` (port 8841/8842, the worktree on the path, jobs off), `odoo_base.conf` (port 8843, with
  pristine `origin/19.1` copies of the five touched modules in `base/` FIRST on the path, for the
  baseline), `run.sh` / `runc.sh` (run odoo, write `<log>.done`), `fails.sh` (list failures).
- No server or test run is running.

**Exact next step on resume:**
1. Baseline, before any edit (PRD-2):
   `bash runc.sh odoo_base.conf base1 wdgap_s5f_t -u pb_leave_setup,pb_time_pay,pb_retro,pb_hub,biz_debrand --test-enable --test-tags /pb_leave_setup,/pb_time_pay,/pb_retro,/pb_hub,/biz_debrand`
   (in the background, bounded wait on `base1.done`), then `bash fails.sh base1`. Expected known failure:
   `pb_hub TestPaletteRowsFollowTheirTabs.test_every_tab_row_carries_its_tabs_gate` (ledger S8M-5).
2. Then build items 1–5 below, one commit each.

## Design decided so far (to build on resume)

1. **LV1 (`pb_leave_setup`)**: `pb.leave.setup._home_countries()` = countries of every company in
   the database, plus the countries people actually work in (payroll country / leave policy), so a
   kind in use is never hidden. A kind belongs to "home" when its country (`pb_policy_country_id`,
   else `country_id`) is in that set or empty. Applied in `_pbf_base_domain` (via the filter kit's
   `ctx` → `pbf_ctx.other`) and in `get_board(other=False)` counts (list, steps, glance, "Pay to
   decide", set-up check chips); board returns `other_count` and per-country `home` flags. JS: kit
   `ctx: {other: false}`, `get_kinds_page` called with `kit.kw(...)`, quiet toggle "Show kinds for
   other countries (N)" / "Hide kinds for other countries" (toggle → `kit.ctx = …; kit.load()` +
   `load()`); ready-made dialog shows home countries first, the rest behind "Other countries";
   applying or saving a kind of another country turns the toggle on so it is not lost. If no company
   has a country, nothing is hidden. Hide only; nothing written.
2. **LV2**: the exact line does not exist yet (only "placeholder" in the India sources). Add
   "Figures differ by state — check yours before switching on" (en/vi/id via `.po`) as a banner on
   the India ready-made dialog and in the drawer of every kind whose ready-made key starts with `IN.`.
3. **TP3 (`pb_time_pay`)**: own route `/my/work/late` (auth user, `_require_own_employee`, sudo read
   of `pb.time.late` filtered on that employee; confirmed = counted, excused shown "Excused"; no
   notes shown), grouped by month, last 12 months; a quiet link card on My Overtime (xpath after
   `work_flash` in pb_time_pay's existing inheriting template) shown only when the person has
   decided minutes (`get_my_overtime` adds a `late` key). No `pb_me_portal` edit. HTTP test as a real
   portal user: own rows only.
4. **BP1 (`pb_retro`)**: in `_pb_pay_check`, a leaver (archived or leaving date passed) is payable
   (`why='final'`) when `_pb_final_payslip_to_come(emp)` holds: (a) an unfinished regular-run
   payslip of the same scheme and company starting after the re-worked months exists, or (b) the
   person is still active, the leaving date is after the re-worked months, their own finished
   regular payslips of this scheme end before it, and no finished regular payslip of the scheme
   covering that date exists for anyone else. Otherwise `left` as today. The taking side is
   unchanged (same reservation, paid once, BP2 floor). The words: approval cell "Final payslip",
   strip "Will be paid in their final payslip", leftovers "The final payslip does not take all of it
   — cancel the rest here and settle it by hand", pay run note for a final payslip that cannot fit a
   month. Tests under `freeze_time` (leaving date 15 Nov 2026): positive, negative fits, negative does
   not fit, none to come (scheme's November run finished without them; left inside the re-worked
   months; own final already finished), re-check at approval, recompute/reset/reopen/finish/cancel/
   delete matrix, second payslip takes nothing, Extra/top-up never, golden.
5. **(a)** `pb_hub/tests/test_palette_lens_gates.py` `_NARROWER` (line ~47): add `wf_patterns_make`
   (only managers make drafts; ledger S8M-5) — test file only; plan: no `pb_hub` version raise (no
   `-u` needed), to be stated as a deviation. **(b)** "Odoo Report" comes from
   `web/views/report_templates.xml` lines 16 and 50 (`title or 'Odoo Report'` in `web.report_layout`
   and `web.report_preview_layout`). Fix in `biz_debrand`: inherit both, title = `title` → the
   report's own name (`biz_report_title`, set in an `ir.actions.report._get_rendering_context`
   override; the printed name for one record when it can be worked out) → "Report"; new
   `biz_debrand/i18n` vi/id for "Report"; also fixes the PDF document title. Version raise
   `biz_debrand` 19.0.2.10.0 → 19.0.2.11.0.

Versions to raise: `pb_leave_setup` 19.0.1.0.0 → 19.0.1.1.0, `pb_time_pay` 19.0.1.0.0 → 19.0.1.1.0,
`pb_retro` 19.0.1.1.0 → 19.0.1.2.0, `biz_debrand` as above.
