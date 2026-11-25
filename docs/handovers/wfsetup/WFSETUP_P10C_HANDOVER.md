# WFSETUP P10c — two "From the clocks" labels (backlog B5 + B6), then deploy ×5

Read first: `WFSETUP_LEDGER.md` (gotchas, incl. WS60+ from P10b), `WFSETUP_P10B_REPORT.md` (§1 what was built, §8 "left
undone"), `WFSETUP_BACKLOG.md` B5/B6, repo `CLAUDE.md` deploy contract. Do not re-derive P10b: the clock source
(`pb_hr_payroll_formula/models/clock_source.py`), the scheme's "Hours from the clocks from" date and the Connect card
are live. Work in a NEW worktree from `origin/19.1` (pull first — a peer session shipped
`pb_hr_payroll_formula` 19.0.1.171.0 at `9b0e4dbea`; bump from whatever origin has). Never the shared checkout.

## 1. Scope
1. **B5 — pay data template.** When the template/sample file is generated for a scheme period ON or AFTER the scheme's
   clock date, every column whose input is answered by the clocks says so in its header (or header note/comment —
   follow how the template already annotates columns): "From the clocks — leave blank". Columns for periods before the
   clock date, and schemes with no clock date, are byte-identical to today (prove with a test). If the template is
   period-less, use the scheme's clock date being set as the trigger and word it "From the clocks from <date> — leave
   blank for those months".
2. **B6 — component editor source card.** For an input whose source is the clocks, show a chip
   "From the clocks — from <date>" (date in the user's locale format) next to the existing source wording, same chip
   style the card already uses for other sources. Read-only; no new actions.

### Binding non-goals
No calculation change, no change to which inputs come from the clocks, no stored-field changes unless unavoidable
(say so). No data changes on live. No changes to `pb_clock`, `pb_attendance_policy`, `pb_workforce_setup`.

## 2. Standing rules (binding)
- White-label: the word "Odoo" must never appear in anything a user can see or receive (labels, file headers, help,
  errors, msgstr). Technical identifiers untouched.
- Design bar, verbatim: "extreme WOW, intuitive, out-of-this-world experience, best in class." Lucide icons, never
  emoji; no gradients; plain words.
- Every new sentence gets vi_VN and id_ID msgstr (three PO loading rules + parse gate; exact `_t` import spelling, WS40).
- Lessons follow screen changes: check whether any lesson/tour/replica shows the template header or the source card;
  update if so, else say "checked, nothing to change".
- Commits: explicit paths, no client folders (RIZE/, SUDIMA/, outputs/), no passwords; end with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push to `origin/19.1`.

## 3. Tests
1. Template for a clock-dated period: the clock-answered columns carry the label; others unchanged.
2. Template for a pre-clock-date period / scheme without a clock date: identical to before (compare bytes/headers).
3. Source card payload/render carries the chip with the date for clock inputs, nothing for others.
4. Static: new msgids have vi + id msgstr; no "Odoo".
5. Affected module suites: baseline failures only (compare against origin before your change).
Browser (local): the chip renders in English, Vietnamese, Indonesian; console clean.

## 4. Deploy (tier NORMAL — labels only)
Repo `CLAUDE.md` contract word for word; reuse `p10b/` scripts trimmed to the changed module(s):
read `/opt/deploy-notes.md` (another deployer's START without DONE → wait/stop); START line; `flock
/tmp/payobook-studio-deploy.lock`; 15 quiet minutes on sudima/rize/payobook; backups ×5 (`/odoo/backups/wfsetup-p10c-…`);
clean staging; per-module scoped `rsync -a --delete`; `-u` on all five where installed (payobook, payobook_template,
p0clone, rize, sudima); asset purge + `web.assets.version` if JS/SCSS/XML assets changed; restart; hashes; versions ×5;
cron counts unchanged (payobook_template jobs re-activated by `-u` → switch back off, as P10b did); HTTP 200 ×5; DONE
line. **Never abm.** No rehearsal copy needed. Live look: sudima look-only (scheme 7844 source card shows the chip with
1 Dec 2026), payobook with the QA login. If you enable any login for the look, disable it and rotate after.
Nothing confirmed, published, switched on, approved or run.

## 5. Report back (`WFSETUP_P10C_REPORT.md`, committed + pushed)
What changed, tests, deploy timeline + downtime, versions, live look, anything unsure; ledger gotchas if any. Mark B5/B6
done in `WFSETUP_BACKLOG.md`. On a usage limit: leave the server consistent, "Where I stopped", PAUSED.
