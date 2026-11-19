# PAUSED — FS-4 Lists and columns (owner pause, 2026-11-19)

**Done (WIP, committed, untested):**
- `pb_filter_kit` 1.5.0: `pb.filter.view.columns` (Json, nullable) + per-person
  `<screen>::columns` row; new `pb.list.layout` (company default, admin-only ACL,
  company rule); API `pbf_columns_read / pbf_columns_save / pbf_columns_reset` on
  `pb.filter.view`; mixin hooks `_pbf_columns`, `_pbf_table_rows`, `_pbf_export_name`,
  RPC `pbf_columns`, `pbf_export_table` (openpyxl, formula-safe text cells, 10,000 cap);
  JS `list_table.js` (ListColumns model, useListColumns, PbListTable, PbColumnsButton,
  PbTableTools) + xml + scss.
- `pb_form_studio_lists` 1.0.0: server `_inherit` of `pb.people` / `pb.contracts`
  (columns, `pbfl_table` context → custom cells via engine `_pbfs_values_for`, Excel rows);
  JS patches + t-inherit for People and Contracts (table, tools in the filter-bar slot).

**Next (in order):**
1. `pb_form_studio_lists/static/src/js/records_columns.js` (Records Desk: patch
   `loadFields` / `restorePicked` / `restoreOrder` / `rememberPicked` → store screen
   `records.<configId>`, one-time read of the old browser keys) and `scss/lists.scss`
   (both named in the manifest, not yet written → module will not load until they exist).
2. Tests `pb_form_studio_lists/tests/test_lists.py` (numbered 1–10; hosts patched in via
   `_pbfs_hosts`, `_pbfs_busy` patched — see gotcha below); kit tests.
3. vi/id PO for both modules (kit has no id_ID.po yet; add `.pot` entries too).
4. Baseline suites: DB `fs_4_bl` (copy of `fs_4_base` = template + engine, from a clean
   `git archive origin/fs-1` tree) — run was STOPPED mid-way by the pause; rerun.
   Suites: /pb_contracts,/pb_records,/pb_people_hub,/pb_hiring,/pb_timeoff,/pb_lifecycle,
   /pb_expenses_hub,/pb_learn,/pb_hub,/pb_settings,/biz_debrand,/pb_form_studio.
5. Install on `fs_4_t`, browser walk (needs a scratch, uncommitted host-registering module),
   report, drop `fs_4_base`, `fs_4_bl`, `fs_4_t`.

**Gotcha found (engine, merge-time task for pb_form_studio):** `_pbfs_busy` joins
`pg_locks` to `pg_class` without `l.database = (SELECT oid FROM pg_database WHERE
datname = current_database())`. DB copies share table OIDs, so a pay run computing in one
tenant database can block the Form builder in another on the same server.

**Host note:** FS-4 registers no host; custom columns appear once FS-2/FS-3 register
`hr.employee` / `hr.contract` (the engine's `fields_for` only answers host models).
