# WFSETUP P7 — install the Workforce setup studio on rize, payobook_template, p0clone

Owner instruction 2026-11-25: "roll out the changes you have done in Sudima to all other databases as well."
Read first: repo `CLAUDE.md` deploy contract (binding), `WFSETUP_LEDGER.md` (WS1–WS50), `WFSETUP_P5B_REPORT.md` and
`WFSETUP_P6_REPORT.md`, the WFSETUP row in `docs/deploy/PENDING.md` (it is your work order), scripts in `p5b/` and `p6/`
(clone them; do not invent new ones). Tier: **RISKY** (new module + first install of `pb_attendance_policy` on three
databases, one of them a real tenant).

## What ships
Code on disk is already current (one addons dir; `pb_workforce_setup` 19.0.1.5.0 is live for sudima + payobook). No
file changes unless the server trees differ from `origin/19.1` — verify hashes first; if they differ, stop and report.
`-i pb_workforce_setup` on **rize, payobook_template, p0clone**, one at a time. Nothing for sudima/payobook. Never abm.

## Rules
- `/opt/deploy-notes.md` first (another deployer's START without DONE → stop); START/DONE lines; lock
  `/tmp/payobook-studio-deploy.lock`; 15 quiet minutes on rize, sudima, payobook before the stop.
- A PEER agent (WFSETUP P8) is working at the same time on a hidden copy of sudima named `zz_wfs_p8_*` — that copy is
  not yours: do not touch, count or drop it. The peer will not act on live sudima until your DONE line is in the notes.
- Backups ×3 (`pg_dump -Fc`, keep rize's permanently per precedent) right before the stop.
- Rehearsal first on a hidden copy of **rize** (jobs + mail servers off the instant the copy exists; separate addons
  path / port as the p5b scripts do; drop copy, filestore and any login afterwards): install; data counts before/after
  identical (rosters, shifts, patterns, overtime rates and requests, leaves, payslips); studio opens with rize's people;
  rize has NOT opted into the grouped Workforce menu, so its menu must look unchanged; the old "Set up Workforce" doors
  open the studio. Rize uses no late/overtime rules — confirm the install creates no active rule set and attaches none
  to anyone, and that the new 15-minute calculation job does nothing there. Any failure → stop, report.
- Cron counts before/after per database. Expected new: the rules module's 15-minute calculation job (+ whatever
  `pb_workforce_setup` adds). On **payobook_template** all jobs are intentionally off: switch the new one(s) off again,
  and add the calculation job to `pb_tenants.template_active_crons` (as the PENDING row describes) so NEW tenants get
  it active — tenants receive every master module. Report exactly what you set.
- Stop the service once; install per database with exit sentinels; first failure → restore that database, start, report.
  Asset purge + `web.assets.version` on the three; start; warm; verify hashes, versions ×5 (now installed on all five),
  HTTP 200 ×5, log clean (precedent allow-list).
- Live look: rize look-only with a login enabled for the walk then disabled + rotated (precedent), steps 1–7 render,
  menu unchanged, console clean. p0clone the same, brief. No writes, no Confirm, no publish.
- Mark the PENDING row done; `WFSETUP_P7_REPORT.md` committed + pushed to 19.1; ledger gotchas if any.
- White-label: no "Odoo" in anything a user can see. No credentials in any committed file. Commit messages end
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`. Usage limit: server consistent first, then PAUSED.
