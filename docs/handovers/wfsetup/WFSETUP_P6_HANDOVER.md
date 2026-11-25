# WFSETUP P6 — honest clocks, Undo refresh, then a small deploy (sudima + payobook)

Read first: `WFSETUP_LEDGER.md` (rules + gotchas WS1–WS46), `WFSETUP_P5B_REPORT.md` (what the go-live found),
`WFSETUP_FACTS.md` sections on clocks (step 6) and go-live (step 7) — do not re-derive. Worktree
`/Users/adity/Documents/GitHub/gitlocal-worktrees/wfsetup`, branch `wfsetup-p6` (from `origin/19.1` @ 36dd3afcf).
Never edit the shared checkout. Only `pb_workforce_setup` changes (bump to 19.0.1.5.0).

## 1. Scope (three fixes found by the go-live)
1. **Step 6 "Time clocks" must tell the truth about clock-ins reaching pay.** On live sudima all six
   `pb.clock.connector` rows are connected but have the "send clock-ins" switch off, and there are 0 clock-ins and
   0 attendance rows; four of the six PCs have been silent since 23–24 Nov. Today the step can read as fine.
   - Per clock, show three plain states: "Sending clock-ins" / "Connected, but clock-ins are switched off" /
     "Not heard from since <date>". Find the real field names in `pb_clock` (the send switch, last-seen stamp); the
     exact threshold for "not heard from" is whatever `pb_clock` already uses for its own health chip — reuse it.
   - The step is green only when at least one clock is sending, OR the manager has ticked the existing
     "we do not use time clocks" / acknowledgement (`res.company.pb_wfs_clocks_ok`) — keep that escape as is.
   - A manager with rights on `pb.clock.connector` gets a button on the row, "Switch clock-ins on", behind an inline
     confirm panel (no browser `confirm()`), sentence: "Clock-ins from this clock will start arriving and will be
     turned into paid hours by the rules in step 4." It writes the same field the clock screen writes, through the
     same method that screen uses (no sudo beyond what the existing studio clock code already does). Others see the
     state read-only with "Ask a manager to switch clock-ins on."
   - Do NOT switch anything on yourself on any live database. This is the customer's decision.
2. **Step 7 and the "Workforce is live" card**: the line "Clock-ins now turn into paid hours" appears only when at
   least one clock is sending. Otherwise: "No clock is sending clock-ins yet — paid hours will start once one is
   switched on in step 6." with a link to step 6. The readiness check in step 7 lists the same as an amber item
   (not a blocker — a company may publish a roster before its clocks are on).
3. **Undo on a late-rule change (step 3 bulk "set the late rule" → Undo)**: the table keeps showing the new rule
   until reload (saved data is correct). Reload the affected rows / the person panel after every Undo, for every
   bulk action, not only this one — find the common undo path and fix it there.

### Binding non-goals
No calculation changes. No change to `pb_clock`, `pb_attendance_policy`, `pb_hr_workforce`, `pb_workforce_workspace`.
No new steps. No data changes on live databases.

## 2. Standing rules (binding)
- White-label: the word "Odoo" must never appear in anything a user can see (labels, help, errors, msgstr).
  Technical identifiers untouched.
- Design bar, verbatim: "extreme WOW, intuitive, out-of-this-world experience, best in class." Lucide via `ic()`,
  never emoji; no gradients; one solid primary per bar; plain words.
- Every new sentence gets vi_VN and id_ID msgstr (three loading rules, parse gate, the exact `_t` import spelling
  — WS40); numbers through the locale formatter (WS41/42).
- Commits: explicit paths, no client folders, no passwords, message ends
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.

## 3. Tests
1. Python: step 6 payload gives the three states for (sending / connected-off / silent) connectors; step status is
   not green with only connected-off clocks and no acknowledgement; green with one sending; green with acknowledgement.
2. Python: "switch on" refused for a user without clock rights; allowed for a manager; writes only that connector.
3. Python: the finish payload carries the "no clock sending" variant when none is sending.
4. Static: every new msgid has vi + id msgstr; no "Odoo".
5. Full `pb_workforce_setup` suite green (89 before this phase) + `pb_workforce_workspace` (12).
Browser (local): B1 the three states render; B2 switch-on confirm panel, Esc cancels, focus returns; B3 finish card
both variants; B4 bulk late rule → Undo → table shows the old rule without reload; same for "Give a working week";
B5 Vietnamese + Indonesian for the new sentences; console clean.

## 4. Deploy (tier: NORMAL — one module, JS/XML/Python, one small version bump, no new stored fields unless you
needed one; if you add a stored field say so and treat as normal anyway)
Follow the repo `CLAUDE.md` deploy contract and reuse the scripts in `docs/handovers/wfsetup/p5b/` trimmed to one
module: merge to `origin/19.1` and push; read `/opt/deploy-notes.md` (another deployer's START without DONE → stop);
START line; lock; quiet check; backups of sudima + payobook; clean staging; per-module scoped rsync of
`pb_workforce_setup` only; `-u pb_workforce_setup` on **sudima and payobook only** (it is not installed elsewhere);
asset purge + `web.assets.version` on those two; restart; hashes; versions on all five (the other three must show the
module absent); cron counts unchanged; HTTP 200 ×5; DONE line. Never abm. No rehearsal copy needed.
Live look: payobook with the QA login — step 6 states, the bulk late rule + Undo refresh; sudima look-only — step 6
shows six clocks as "Connected, but clock-ins are switched off" / "Not heard from…", step 7 shows the amber item.
Nothing switched on, confirmed or published on live. If you enable a login for the walk, disable it and rotate after.

## 5. Report back (`WFSETUP_P6_REPORT.md`, committed + pushed)
What changed, test counts, deploy timeline + downtime, versions table, live look results, anything unsure. Update
the ledger with any new gotcha. On a usage limit: leave the server running and consistent, "Where I stopped", PAUSED.
