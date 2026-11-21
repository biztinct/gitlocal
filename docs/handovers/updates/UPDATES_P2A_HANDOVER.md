# UPDATES — Phase 2a handover: safe name look-ups, speed, Sudima, live walk

Read first: `UPDATES_LEDGER.md` (rules, facts U1–U12, gotchas G1–G12) and
`UPDATES_P1_REPORT.md` §R3, §R4, §R6, §8. This phase closes what Phase 1 found before any new
feature is added. It is small on purpose.

## 1. Scope

1. **Name look-ups in the Records Desk stop guessing** (`pb_records`, ledger G11).
2. **Review speed on a full roster** (`pb_records` evaluation path, `pb_updates` reshaping).
3. **The stale `pb_records` test** `test_01a_get_fields_returns_mapped_and_standard_record_destinations`.
4. **Sudima gets Updates** (owner decision 2026-11-11, ledger D7): from now on the UPDATES
   deploy set is five databases — `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`.
   Never `abm`, never `pbf_preview`, never `recruit_connect_20261023`.
5. **QA login reset + the live write walk Phase 1 could not do** (owner decision, ledger D8).

Versions: `pb_records` `19.0.1.8.4` → `19.0.1.8.5`; `pb_updates` → `19.0.1.0.2` only if its
files change.

## 2. Binding non-goals

- No new feature: no dates, no scheme-aware components, no CLEAR, no one-offs, no drafts.
- No change to what a correct, unambiguous value does today. Every existing `pb_records`
  and `pb_updates` test keeps passing (after item 3 fixes the one stale expectation).
- No cross-request cache. Anything cached lives for one `_evaluate` call and dies with it.
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`, `docs/handovers/workflow2`.

## 3. Item 1 — name look-ups

Verified fact: the many2one branch of `pb.records.desk._coerce`
(`pb_records/models/pb_records_desk.py`, the block starting `if ftype == 'many2one':`, about
lines 1097–1127) resolves typed text with
`comodel.sudo().search([(key, '=ilike', text)], limit=1)` — first hit wins, no company
scope — and, when nothing matches and `m2o_creates_missing(comodel)` is true, proposes
`{'create': text}`. The `{id: …}` dict path (the on-screen picker) is exact and stays as is.

Replace the text path with this ladder, in order:

1. **It is already this.** If the record's current value for this field exists and the
   typed text equals (case-insensitive, whitespace-normalised) its `display_name`, its
   `key` value, or its `complete_name` when the comodel has that field → return the current
   id. A namesake can then never displace the value that is already there.
2. **Scoped exact match.** Search `[(key, '=ilike', text)]`, plus — when the comodel has
   `company_id` — `['|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)]`,
   `limit=3`. When the comodel has an `active` field, default active filtering applies; do
   not add `active_test=False`.
3. **Full path.** If step 2 found nothing and the comodel has a stored `complete_name`
   (e.g. `hr.department`), repeat step 2 on `complete_name`.
4. **One hit** → that id. **More than one** → refuse:
   "%(n)s %(what)s are called '%(value)s'. Pick the right one on the Records screen, or use
   a name that is unique." (`what` as the existing code derives it.) Never pick.
5. **No hit** → existing behaviour (refuse, or propose a create when the comodel allows it)
   — except: when the comodel has `complete_name` and the text contains `/`, never propose a
   create; refuse with "No %(what)s is called '%(value)s'. Check the full name, including
   the part before the slash."

Look-ups repeat heavily inside one file (4,575 rows naming 30 departments), so memoise the
ladder's steps 2–5 per `(comodel, text)` for the life of one `_evaluate` call (pass a dict
down; `_coerce` has other callers — keep its signature backward compatible with an optional
keyword).

Keep `pb.updates.desk`'s "file text equals what is on record → no change" guard (G11); it is
now a second belt, not the only one.

## 4. Item 2 — speed

Measured in Phase 1 on 4,575 people × 73 columns: building the sheet 37 s, reading columns
4.5 s, review 71–87 s. Target: **review ≤ 25 s and sheet ≤ 20 s on the same file, with
byte-identical results**.

Method, in this order: (a) profile `pb.updates.desk.review` on a local copy with a full-size
roster (cProfile; put the top 25 cumulative lines in the report); (b) remove per-cell
searches and per-cell reads by prefetching/batching inside the one call (contracts per
employee, bank accounts, advantage lines, many2one look-ups via item 1's memo); (c) re-measure.

Proof of "identical": a test that runs `preview_changes` on a fixture of ≥ 200 changes
covering every card kind (`f:` char/number/date/selection/boolean/many2one, `b:`, `c:`
amount and text) and compares the full `items` list against a golden copy captured BEFORE
the optimisation in the same test module (capture it first, commit it as a JSON fixture).

If the target cannot be reached without changing semantics, stop at what is safe, report the
numbers and what blocks the rest. Do not add background jobs or pagination of the server
call in this phase.

## 5. Item 3 — the stale test

`test_01a_get_fields_returns_mapped_and_standard_record_destinations` still expects a pay
scheme's field list to include the master fields; `pb_records/models/master_records.py`
separated them (scheme mode = mapped destinations only; `config_id = 0` = Master records).
Find the commit that made the separation (`git log -S_master_fields -- pb_records`), confirm
the separation is the intended behaviour from its message, and update the test's
expectation to assert BOTH halves: scheme mode lists only mapped destinations; Master mode
lists the master fields. If the commit message says otherwise, do not change the test —
report it.

## 6. Tests (numbered)

| # | Case | Expect |
|---|---|---|
| A1 | Two departments with the same name in one company; a person in the second; file names it | stays on the current one, status `same` |
| A2 | Same two namesakes; a person in neither; file names it | refused with the "N … are called" sentence |
| A3 | Department typed as its full path "Parent / Child" | resolves to the child; no create proposed |
| A4 | Full path that matches nothing | refused with the slash sentence; no create proposed |
| A5 | Same name in company A and company B, user working in A | resolves to A's record only |
| A6 | Unique name, different case and stray spaces | resolves (unchanged behaviour) |
| A7 | On-screen picker payload `{id: …}` | unchanged behaviour |
| A8 | Manager named by a name two employees share | refused, never picked |
| A9 | Golden comparison (§4) | identical `items` before/after |
| A10 | Memo does not leak: two `_evaluate` calls, a department renamed between them | second call sees the new name |
| A11 | Item 3's rewritten test | passes; full `pb_records` suite 81/81 |
| A12 | Full `pb_updates` suite | 27/27 (or more) |
| A13 | Untouched full sheet round trip on a local copy of a large roster | 0 changes, 0 needs-attention |

Server-side test runs on the live box use `--no-http` (G12).

## 7. Deploy, QA login and live walk

Tier 2 for the four existing databases (Python only, no stored-data change); tier 3 for
`sudima` (new module install there): back up `sudima` first.

1. `/opt/deploy-notes.md`: read, wait if someone else's START is open, append START, take
   the flock `/tmp/payobook-studio-deploy.lock`.
2. Dry-run rsync `pb_records` and `pb_updates` against the server; only this phase's
   differences may show.
3. Stop; upgrade `pb_records` (and `pb_updates` if changed) on `payobook`,
   `payobook_template`, `p0clone`, `rize`; on `sudima` upgrade `pb_records` and install
   `pb_updates`. Cron-count snapshot before/after on all five; switch off anything newly
   active (memory note `cron-snapshot-boolean-trap`).
4. **QA password reset — owner-approved 2026-11-11.** While the service is stopped, set a
   new random password (≥ 20 characters, generated on the server, never echoed into a file
   in the repo) on the QA user of the `payobook` database with an `odoo-bin shell`
   one-liner. Record the new password ONLY in
   `/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/payobook-qa-login.md`
   (replace the old one, add the date). Never in the repo, the report, a commit message or
   `/opt/deploy-notes.md`.
5. Asset purge per database only if JS/SCSS changed; start; warm each of the five sites
   with one curl; grep the log.
6. Verify: byte-identical hashes for both modules; manifest version ==
   `latest_version` in all five databases.
7. **Live write walk on `payobook`** with the QA login through Chrome MCP (read the console
   at each step): People › Updates → download a sheet → change three cells for existing
   DEMO people (one job title, one phone or similar text field, one pay item amount) →
   upload → review → apply → Past updates shows it with the file → undo → confirm the
   three values are back. Then the made-up-headings CSV: match, apply, undo, re-upload to
   see "Remembered from last time". Then send an untouched full sheet back: it must read
   0 changes. If the QA role cannot apply, report exactly which permission is missing —
   do not use the owner's admin account to apply. Leave nothing changed; never delete demo data.
8. On `sudima`: open People › Updates once (look only), console clean.
9. Append DONE/FAILED to `/opt/deploy-notes.md`. Commit with explicit paths; credential
   scan; push `origin 19.1`.

## 8. Report back — `UPDATES_P2A_REPORT.md`

- A1–A13 results with output; the profile before/after and the three timings.
- Deploy evidence for five databases; cron counts; log grep.
- The live walk: every step, console state, and proof the three values were restored.
- Deviations and why; new gotchas into the ledger.
- For Phase 2b/2c (answer from the code, with file:line):
  1. What `records_approval.py` does at approval time (`_approval_apply` → which method
     writes the plan), and where a "hold until a date" state would attach.
  2. How the pay run reads a contract component amount for a period (current line value,
     or the change history by effective date?) — one paragraph with the call chain.
  3. Whether `hr.contract.advantage.change.effective_date` is read by anything except
     history screens.
  4. Where one-off pay items for a pay month are stored and approved today
     (`hr.payroll.period.input`, `pb.payroll.month.inputs`, `pb.oneoff.feed`) and which one
     a pay run actually reads.
