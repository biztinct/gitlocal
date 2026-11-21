# WDGAP S2-F — two small fixes after the Step 2 go-live (build, test, go live ×5)

Read: `WDGAP_S2_DEPLOY_REPORT.md` on `origin/19.1` (the command sequence you repeat,
and its findings), `WDGAP_S2_DEPLOY_HANDOVER.md` (main checkout — ALL its
non-negotiables apply unchanged), `WDGAP_IDB1F_REPORT.md` on `origin/19.1` (precedent
for a small fix + go-live by one agent), `WDGAP_OWNER_RULINGS_2026-11-15.md` (TD4),
`WDGAP_S2D_REPORT.md` and `WDGAP_S2A_REPORT.md` / `WDGAP_S2B2_REPORT.md` on 19.1.
Branch `wdgap-s2f` from `origin/19.1`; own database; drop it after.

## Fix 1 (TD4) — dependants-mismatch note, `pb_me_tax`
An empty / missing / zero-because-unset dependants figure on the contract = nothing to
compare → no note. Note only when the contract carries a real figure that differs from
the confirmed dependant records. Distinguish "not set" from a real 0 the way the
component stores it (verify in code; if it cannot be told apart, treat 0 with no
confirmed dependants as equal, and 0 with confirmed dependants as "not set" → no
note; say which in the report). Tests: empty → none; equal → none; differs → note;
contract never written. After go-live count the notes per live database (read-only)
and report: payobook should fall from ~2,450 to near 0.

## Fix 2 — "Suggest" on Form lines for Indonesian schemes, `pb_form_lines`
The deploy report says Suggest found nothing for the two BPJS fund sheets and missed
the monthly tax item on Rize's Indonesian scheme. Look read-only at that scheme's pay
item NAMES and codes on a rize COPY or via read-only SQL on live (names of pay items
are configuration, fine to read; print no employee data) and widen the Suggest words /
roles of the affected lines so they are proposed. Catalogue data is `noupdate="1"`:
ship the wording change so EXISTING databases get it too (precedent in the ledger for
noupdate data; a guarded post-migrate that touches only the Suggest-word fields of
lines whose words still equal the shipped old value). Suggest still never saves.
Tests: a scheme with those names → proposals for BPJS JHT/JP/JKK/JKM/Kesehatan
employee + employer lines and the monthly tax line; nothing auto-saved; other
countries' suggestions unchanged. If the names are too customer-specific to match
safely, do NOT force it — report the names (they are config, not personal data) and
leave Suggest alone.

## Go live
LOOKS/NORMAL tier but touching `pb_form_lines` data: backups ×5, deploy notes
START/DONE, activity check before stopping the service, `-u` the two modules ×5,
hashes + `latest_version` ×5, asset purge only if JS/SCSS changed, cron counts equal
the snapshot, nothing mapped/filed/mailed by the upgrade, Sudima's waiting bank batch
untouched. Report `WDGAP_S2F_REPORT.md` (commit + push to 19.1). Final message under
150 words, plain simple English, screen words only.
