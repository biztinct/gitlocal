# TIERS T4 — switch-over plan (Fable runs it; nothing here runs before the owner's go-ahead)

State on 2026-10-15 evening: T1, T2 live on all five databases; T3a live on payobook only; T3b built and tested,
not deployed (owner freeze 20:32 Sydney, memory `deploy-freeze-payobook`). T3c (buddy stand-in guard, training
claim links) coded by Fable, clone tests pending/green — see `TIERS_PROGRAM.md` status.

## What T4 does, in the owner's words
Turn the plain employees' full accounts into employee logins, one database at a time, with a way back; give every
joiner whose automatic account was never linked a working login; ship T3a/T3b/T3c to the other databases.

## Steps (each needs its own go-ahead from the owner; nothing is irreversible)
1. **Deploy T3b + T3c to payobook** (recipe in `docs/deploy/PENDING.md`), live walk: clock in/out as ess2, the notice
   board (needs one sent announcement on payobook — HR → Announce; or seed one post + delivery row under sudo and
   say so), colleague photos on the org chart, a training claim link.
2. **Batch T3a/T3b/T3c to rize, payobook_template, abm (+ p0clone)**: `-i pb_ask_hr,pb_me_portal_comm -u
   pb_me_portal,pb_ess_workforce,pb_onboarding,pb_rnr,pb_pay,pb_timeoff,pb_training` per DB, asset purge + version
   bump each, `python3 tools/deploy_status.py` clean, abm jobs back off (memory `abm-tenant-retired`).
3. **Backfill joiners' logins** (T-R10): `tools/tiers_switchover.py --backfill` (dry-run) per DB, then `--backfill
   --apply`. Rollback list = employee ids (set `user_id` back to empty).
4. **Convert plain employees** per DB: `tools/tiers_switchover.py` (dry-run prints CONVERT / skip with the reason),
   owner reads the list, then `--apply`. The script refuses anyone with a hand-given permission, a role, a direct
   report, an open approval seat, admins, the recovery login and the skip list (manager.demo). Rollback:
   `--rollback tiers_rollback_<db>_<stamp>.json` restores staff + the exact groups.
   - payobook (demo): ess3, ess4, ess6–ess10, minor.demo, chi.ta, kiet.lam, demo.joiner, demo.joiner2 are the
     expected candidates (query of 2026-10-15); ess1/ess5 (reports), employee.demo (driver group), diep.thai
     (budget viewer), tuan.quach (HR groups), demo.hr, drivers, demo.recruiter are expected skips.
   - rize is a real customer: the owner decides whether and when; show them the dry-run list first.
5. **Close-out**: `TIERS_CLOSEOUT.md` (what shipped, decisions, leftovers), memory update, findings page
   `docs/design/employee-access-strategy.html` gets a "What shipped" footer.

## Leftovers after T4 (small follow-ups, not blocking)
- pb_hiring recruiter-side download links without tokens (backend users, fine today).
- The Access screen's switch does not yet refuse a person with a hand-given permission (the T2b fence exclusion
  lives in pb_me_portal); the script refuses them, the screen would strip the permission silently. Add the same
  check to `_switch_refusal` (biz_access) in a later pass — ledger T22 mentions it.
- HR answer e-mails on payobook (no alias domain) — a payobook mail-setup gap, not TIERS.
