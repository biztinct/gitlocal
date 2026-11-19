# FS-2 — Employee record (`pb_form_studio_people`) — report

**PAUSED (owner pause, 2026-11-19)** — done / next:

- DONE: branch `fs-2` from `origin/fs-1`; new module `pb_form_studio_people` 19.0.1.0.0
  (host `employee_detail` on `hr.employee`; side panel "Company details" tab with one Save,
  wand in the panel header, Studio overlay mounted through the overlay service; full page
  look-only section; Full details page registered just in time for the engine's native sync;
  People list filters for choice / yes-no / link / date custom fields; publish-sheet line
  "A field's type cannot be changed after it is published."; non-stored
  `pbfs_country_of_work_id` = Country of Work as a country record). Installs cleanly on local
  `fs_2_t` (kept for the resume; port 8741). Baseline touched suites (pb_form_studio,
  pb_people, pb_employee_vault, pb_scheme_map, pb_workseg): 125 tests, 0 failed.
- Test file written (numbered 1–6, 8, 8b, 10, 11); last run: 6 of 10 passing, the rest were
  fixture issues now fixed (HR = payroll officer role; look-only reader via an access rule)
  plus FS2-1 below; not re-run yet.
- NEXT: build `i18n/pb_form_studio_people.pot` + `vi_VN.po` + `id_ID.po` (pot exported to the
  scratchpad, 57 entries); re-run the suite; test 7 (`-u` keeps everything, script); touched
  suites vs baseline; browser walk desktop + phone; full report; drop `fs_2_t`.

## New gotcha found (for the ledger)
- **FS2-1 (engine bug, merge task M1):** `pb.form.studio._pbfs_busy` signal 1 reads `pg_locks`
  for the WHOLE Postgres server. Databases copied from one template share table ids (OIDs), so
  a pay run computing in one tenant makes the Form builder refuse to add/delete fields in every
  other tenant on the box ("A pay run is being worked out right now"). Seen locally: another
  builder's database `tidy_e_bl` held the lock on the same OID (1078675). Fix in
  `pb_form_studio/models/form_studio.py` `_pbfs_busy` query, add after the `WHERE c.relname …`
  line: `AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database())`.
