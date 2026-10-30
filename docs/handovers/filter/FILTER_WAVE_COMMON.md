# FILTER waves — the common contract (read with FILTER_LEDGER.md)

Each wave handover (`FILTER_W<n>.md`) lists its screens and their verified
facts. Everything below applies to every wave unchanged.

## A. What "done" means for one screen

1. The screen's data model inherits `pb.filter.mixin` and declares its
   sections, built-in views, sorts and search fields (ledger §3).
2. Rows are served **paged from the server for the panel's state**; the
   client never filters a loaded array (the old 240-row caps go).
3. The template wraps the list/board in `<PbFilterLayout>`; the old chip
   rows, date chips, status buttons and department facets are removed.
   Quiet-numbers figures that used to filter call `kit.toggleFilters`.
4. Every state is designed: loading (skeleton), empty for a filter (names
   what to do: remove a filter / show all), empty for a search (names the
   term), huge (paging with "Show N more"), failure (toast that says what
   to try).
5. Bulk actions and exports that used the filtered array now use the
   server page (or the whole filtered set via one server call) — never a
   stale client array.
6. Learn: anchors, lesson text and the practice replica follow the screen
   (`pb_learn` bumped) — or the report says "nothing in Learn describes
   this filter area" with the grep that proves it.
7. Vietnamese for every new string, PO gate passed.
8. Verified in Chrome on payobook.com with the test list in §C, console
   clean, screenshots saved.
9. One commit per screen (explicit paths), message problem → fix →
   decisions, Co-Authored-By line from the session reminder.

## B. Non-goals (binding)

- Do not redesign the rows/cards/columns themselves beyond what the panel
  needs; do not touch the hero, KPIs or drawers.
- Do not change `pb_filter_kit` except through the coordinator: if the kit
  lacks something a screen needs (a new section type, a kanban column
  helper), STOP on that screen, write the need in the report under
  "Kit gaps", and continue with the other screens.
- Do not add Odoo native search views; do not use `searchModel`.
- No new stored fields; no migrations.
- No deploy to `abm`. No restart while another START has no DONE in
  `/opt/deploy-notes.md`.

## C. Test cases (run every one on payobook.com, in Chrome MCP, per screen)

T1  Open the screen: panel shows, counts beside values, the first view tab lit,
    list loaded, console has no errors (read `read_console_messages` with onlyErrors).
T2  Tick a value in a pinned section → chip appears, list and "N of total"
    update, the section's own count stays, OTHER sections' counts recompute.
T3  Tick a second value in the same section → OR within the section (count grows).
T4  Tick a value in a second section → AND across sections (count shrinks).
T5  Press "Only" on a value → only that value stays ticked.
T6  Find box: type a value that exists ("hanoi" style) → only matching sections
    show, with only the matching values; Enter ticks the first; Escape clears.
T7  Find box: type nonsense → the "Nothing matches" state with its hint.
T8  Date section: a preset → chip text is the preset; "Pick dates…" with a
    from/to → chip shows the range.
T9  Number section (if any): a minimum → chip "X or more"; values formatted
    with thousands separators.
T10 Chip click → panel opens at that section (panel scrolls, page does not);
    chip × removes it; "Clear all" removes everything incl. search.
T11 Search box: a name → list narrows; "/" focuses it; Escape clears it.
T12 Sort menu: each option changes the order (check the first row).
T13 Paging: with > page size rows, "Show N more" appends, count line updates.
T14 Views: Save view (private) → new tab, selected; View options → rename,
    Share with everyone toggle (toast), Delete with confirmation. Delete the
    test view at the end.
T15 Built-in views: each tab applies its filters and lights the right chips.
T16 Quiet numbers: pressing a figure that filters ticks the panel and lights
    the matching tab; pressing again returns to everyone.
T17 Hide filters → full-width list, chips remain, badge shows the count;
    reload → the hidden state is remembered; filters survive the reload.
T18 Reload with `?pbf=…` link copied from "Copy a link to this list" →
    same filters applied (paste the link into the address bar).
T19 Bulk action / export (if the screen has one) acts on the filtered set,
    not on a stale array: tick a filter, run the export, inspect the file.
T20 Empty: a filter combination with 0 rows → the designed empty state with
    the "show all" action; press it → everyone is back.
T21 Phone: `resize_window` to 420 px, or add class `pbf--narrow` to `.pbf`
    → panel becomes a drawer with a scrim; close it.
T22 Vietnamese: `fetch('/web/dataset/call_kw')` for `pbf_layout` with
    `context: {lang: 'vi_VN'}` → labels and view names are Vietnamese.
Finally: clear `pbf:*` keys from localStorage and sessionStorage, delete any
view you saved, close the tab.

## D. Deploy (per wave, once all its screens pass locally)

1. Local gates: `python3 -m py_compile` on every touched `.py`; `node --check`
   on every touched `.js`; `xml.dom.minidom.parse` on every touched `.xml`;
   `npx --yes sass@1.77.8` on every touched `.scss`.
2. Rehearse on a throwaway copy of `rize` (ledger §2): install/upgrade the
   wave's modules with `--addons-path=/tmp/pbf_stage,/odoo/odoo-server/addons`,
   `EXIT=0`, no ERROR lines; call each screen's `pbf_layout` and `pbf_counts`
   from `odoo-bin shell` with the stage addons path; `dropdb --force` after.
3. Read `/opt/deploy-notes.md`; announce to peer sessions (`ListAgents` →
   `SendMessage`); append the START line.
4. Stage: `rsync -az --delete --exclude=__pycache__ --exclude='*.pyc' --exclude=.DS_Store <modules> Payobook19v2:/tmp/pbf_stage/`
   then `chmod -R a+rX /tmp/pbf_stage`.
5. Run `/odoo/ops/filter_deploy.sh full /tmp/pbf_stage <sync_csv> <upgrade_csv> /tmp/pbf-<wave>-<ts>`
   detached with `sudo systemd-run --collect --unit=…`; poll `<run>/done`;
   read `<run>/result` (must be `OK`) and `<run>/run.log`.
6. Append the DONE line. Then the Chrome test list (§C) on payobook.com for
   every screen in the wave; log check:
   `sudo grep -E " (ERROR|CRITICAL) " /var/log/odoo/odoo-server.log | tail`.
7. Translations: export (`odoo-bin i18n export -d p0clone -l vi_VN …`),
   merge, PO gate, then `filter_deploy.sh looks` is NOT enough for `.po`
   (code translations load at registry start): rsync + `service odoo-server restart`
   under the lock, with START/DONE lines.

## E. Report back (one file per wave: `docs/handovers/filter/FILTER_W<n>_REPORT.md`)

1. Per screen: sections shipped (with which hide themselves on payobook),
   built-in views, sorts, page size, what was removed, Learn changes.
2. The §C test matrix as a table (screen × T1–T22, pass/fail/n.a.), with
   the console check result and screenshot paths.
3. Deploy evidence: run dir, result, cron counts before/after, hashes,
   versions per DB, warm-up codes.
4. Kit gaps (things the shared kit could not do) and design debts.
5. Self-score against the design bar (hero moment, zero dead-ends, plain
   language, motion with purpose, keyboard/bulk ergonomics) per screen.
6. Commits (hashes) and what is NOT committed.
7. New gotchas → append to FILTER_LEDGER.md §4 as F<n>.
8. If paused for a usage limit: "Where I stopped" with the exact next step.
