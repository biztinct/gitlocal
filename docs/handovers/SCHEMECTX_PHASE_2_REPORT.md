# SCHEMECTX Phase 2 — report

Built, tested, deployed and upgraded on all six databases on 2026-09-19.
Handover: `SCHEMECTX_PHASE_2_HANDOVER.md`. Ledger: `SCHEMECTX_LEDGER.md`
(gotchas SC8–SC11 appended by this phase).

**Headline**: the defect is closed. On `rize`, a person who would have shown
~20 components — Vietnamese ones on somebody an Indian scheme pays — now shows
the 2 components of `Rize India Payroll`, in ₹. A new contract no longer
collects the whole catalogue. Not one payslip amount moved anywhere.

**Not done, deliberately, and it needs an owner decision**: the one-time
clean-up was dry-run on all six databases and **applied on none of them except
`rztest`, where it had nothing to do**. Two of the dry-run numbers are
surprising in exactly the way the instruction said to stop for. §5.

---

## 1. The test cases

| # | What it proves | Result | Evidence |
|---|---|---|---|
| 1 | Person on a VN scheme → rows ⊆ that scheme's codes | **PASS** | `pb_contracts` `TestSchemeCtxP2Components.test_01`, rztest |
| 2 | Stray non-zero line → in `other_rows`, not lost | **PASS** | `test_02` (asserts the line still exists) |
| 3 | Stray zero line → in neither list, still in the database | **PASS** | `test_03` |
| 4 | Scheme code with no line → virtual row `id False`; the read wrote nothing | **PASS** | `test_04` (line count unchanged across the read) |
| 5 | Saving a virtual row creates exactly one line | **PASS** | `test_05` |
| 6 | Regular + advance schemes → union, strip shows both | **PASS** | `test_06` (roles `regular` / `advance`) |
| 7 | No scheme → `scope.state == 'unassigned'`, valued lines only | **PASS** | `test_07` |
| 8 | No scheme map → payload identical to pre-change | **PASS** | `test_08` (probe patched on the registry class) |
| 9 | `addable` ⊆ scope codes | **PASS** | `test_09` |
| 10 | New contract → zero lines created | **PASS** | `pb_hr_payroll_formula` `TestSchemeCtxP2Scope.test_10` |
| 10b | Import sync afterwards creates only the file's components | **PASS** | `test_10b` |
| 11 | Payslip neutrality: zero line vs no line → identical inputs | **PASS** | `test_11`, **and** the live diff in §4 |
| 12 | Comp card ignores empty out-of-scheme lines, keeps valued ones | **PASS** | `pb_comp_ben` `TestSchemeCtxP2Package.test_12` |
| 13 | Clean-up dry-run deletes nothing; apply never selects a non-zero line; `--restore` recreates | **PARTIAL** | Dry-run proven on all six (§5) and `--apply` proven to be a no-op on `rztest`. The delete and restore paths are **not exercised**, because no database has a safe non-empty set pending the owner's decision. Stated, not claimed |
| 14 | Explorer: an IN scheme in a VN company groups AND filters as India | **PASS** | `pb_explorer` `TestSchemeCtxP2Country.test_14a/b/c`; live read in §6 |
| 15 | Insights: group by scheme, by country, mixed currencies → one row per currency | **PASS** | `pb_payroll_ai_insights` `TestSchemeCtxP2Grouping.test_15a/b/c`; live read in §6 |
| 16 | Existing suites still green | **PASS — zero regressions** | §2 |

Plus three cases the helper needed that the handover did not number: `12a`
(the helper names the scheme and its codes), **`12a2`** (a code belonging only
to ANOTHER scheme stays out — the pin the coordinator asked for on the SC8
deviation), `12b` (the helper writes nothing), `12c` (a stale answer is worked
out again and still not stored).

## 2. Test 16 in full — and the pre-existing reds

Run twice on `rztest` over the same seven modules, once with this phase and
once with a clean `git worktree` of `HEAD` (`a22f0c6f2`), same command, same
database.

| | with this phase | baseline (`HEAD`) |
|---|---|---|
| tests | 743 | 720 |
| failed | 7 | 8 |
| errors | 1 | 1 |
| distinct red names | 8 | 9 |

The phase's 8 reds are a **strict subset** of the baseline's 9: no regressions,
and one baseline red — `TestJourneyJ10Writeback.test_13b` — is now **green**,
because it counts the lines a component sync creates and the fan-out was what
made that count wrong.

The 8 that remain are pre-existing and data-dependent on `rztest`:

* `TestStructurelessPayslip` ×3, `TestNetRoleClassifier.test_24`,
  `TestRd49SyncCost.test_01a` — the SC6 family, `rztest`'s June 2026 pay run;
* `TestDataQueryAccess.test_06`, `TestEgressSeams.test_04d`, `test_04e` — the
  individual-salary refusal and the voice-consent copy have no Vietnamese in
  `pb_payroll_ai_insights/i18n/vi_VN.po`. **Pre-existing** (red on the clean
  baseline too) and in a module Phase 1's tag set never covered, which is why
  they are new to this report and not new to the product. Not fixed: they are
  nothing to do with this phase, and writing that copy is its own decision.

Three reds WERE mine and are fixed: the pay package test called an instance
method on an empty recordset; the CD1 fixture had flagged two rules as contract
components, which made one of them un-removable and broke case 18; and the
scheme lookup in the insights query layer was elevated, which that module's
own anti-escalation grep correctly refused.

## 3. Deploy

* Clean staging dir, `rsync` per module, `--delete` scoped to each module's own
  subdirectory, never the addons root. **All seven trees byte-identical** repo
  vs server after the wave.
* `om_hr_payroll` confirmed **ours**: `git -C /odoo/odoo-server ls-files addons`
  lists 625 standard addons and none of our seven is among them.
* PO parse gate: 109 `pb_*` `.po` files read with Odoo's own `PoFileReader` —
  **0 failures**; the three new `pb_contracts` entries and the one new
  `pb_comp_ben` entry read back with their Vietnamese.
* Six `pg_dump` backups first, `/odoo/backups/schemectx-p2/` (209 MB).
* Service stopped, upgrade in a detached `systemd-run` unit with a sentinel and
  a per-database logfile. **`EXIT=0` for all six, zero `CRITICAL`.** Never
  `pkill`.
* `/web/assets/%` deleted and `web.assets.version` bumped per database, then
  restart. Service `active`, `https://rize.payobook.com/web/login` → **200**.

Versions, identical on all six: `om_hr_payroll` 1.6.0, `pb_comp_ben` 1.5.0,
`pb_contracts` 1.7.0, `pb_explorer` 2.5.0, `pb_hr_payroll_formula` 1.142.0,
`pb_payroll_ai_insights` 3.2.0, `pb_payrun_results` 1.5.0.

## 4. Pay neutrality, on real data

`hr_payslip_line` `(slip_id, code, total)` on `rztest`, taken out of the
PRE-WAVE `pg_dump` and compared with the live table after the upgrade:

```
before rows: 230     after rows: 230     diff lines: 0
```

**Not one payslip amount moved.** That is the whole-wave version of test 11.

## 5. The clean-up — dry-run on all six, applied on none

| DB | contracts | would delete | kept (hold a value) | kept (in scheme) | skipped (no scheme) | CSV |
|---|---|---|---|---|---|---|
| `rztest` | 5 | **0** | 0 | 95 | 0 | `/var/tmp/schemectx_cleanup_rztest_20260919.csv` |
| `rize` | 102 | **140** | 0 | 0 | 95 | `/var/tmp/schemectx_cleanup_rize_20260919.csv` |
| `payobook` | 4,523 | **117,058** | 0 | 175 | 14 | `/var/tmp/schemectx_cleanup_payobook_20260919.csv` |
| `payobook_template` | 0 | 0 | 0 | 0 | 0 | `/var/tmp/schemectx_cleanup_payobook_template_20260919.csv` |
| `p9clone` | 4,521 | **7** | 0 | 175 | 4,514 | `/var/tmp/schemectx_cleanup_p9clone_20260919.csv` |
| `abm` | 152 | **0** | 0 | 3,192 | 0 | `/var/tmp/schemectx_cleanup_abm_20260919.csv` |

`--apply` was run **only on `rztest`**, where it had nothing to do and said so.
Every other database was left exactly as it was.

**Why I stopped.** Two numbers are surprising in the way the instruction named.
Note first what is NOT at risk: `kept — they hold a value` is **0 everywhere**,
so every line in scope for deletion is empty. Nothing with money in it would be
touched. What is surprising is the SCALE, and the cause is not the code:

* **`payobook`** — 4,503 of the 4,523 people are paid by the six
  "Payobook <sector> — End-Month Payroll" schemes, and **not one of those
  schemes marks a single rule as a contract component** (`ccrules=0` on each,
  against ~53 rules apiece). The 26 catalogue templates come from the two VPTQ
  schemes, which declare 24 each and pay 7 people. So for 4,503 people the
  honest answer is "your scheme holds nothing on a contract", and all 26 of
  their empty lines qualify.
* **`rize`** — all 7 mapped people point at **`Rize India Payroll`**, while
  their contracts carry 20 Vietnamese components each. The live Vietnamese
  scheme (`Rize Vietnam Payroll`) declares only **1** contract component; the
  one that declares 19 (`Rize Vietnam`) is **archived**. `rztest`, an older
  clone, still has `Rize Vietnam` active, which is why the same data reads
  95-in-scope there and 140-out-of-scope here.

Both are demo/mapping drift, not a product fault, and the consequence is
already live on screen whether the rows are deleted or not — the drawer hides
an empty out-of-scheme line either way. Recorded as ledger **SC11**.

**What the owner has to decide**: whether those schemes SHOULD declare contract
components (in which case the fix is in the schemes, and the clean-up numbers
collapse), or whether the mapping on `rize` should point at a Vietnamese
scheme. The clean-up can be run afterwards in one command per database, and
every run writes its undo file first.

## 6. What the screens say now — read live on `rize`

Read through the same server-side calls the screens make, read-only and rolled
back:

```
PERSON Abhishek DM            contract=1839
   scope: scoped   schemes=[('Rize India Payroll', 'IN', '₹')]
   rows=2  other=0  addable=0  count=2
   row codes: ['ANNUAFIXECTC', 'VARIABLECOMP']   virtual rows: 2
scheme scope   Rize India Payroll  IN codes=2 · Rize Vietnam Payroll VN codes=1
explorer       scheme 3939 -> country 104 (India), 3938 -> 241 (Vietnam)
               IN filter -> (config_id IN %s) | configs: [3939]
insights       "payroll cost by payroll scheme" -> payroll_cost_by_scheme
               "salary by country"              -> salary_by_country, 2 rows, mixed currency
```

Before this phase that first person's Components tab carried ~20 Vietnamese
components. That is the owner's defect, closed.

## 7. What could NOT be validated in a browser, and why

**There is still no logged-in session for `rize.payobook.com` in Chrome.**
`/bizapp` redirects to `/web/login`, the page offers a password field and no
stored credential, and per ledger rule 11 I did not guess one and did not reset
one. Phase 1 reported the same.

Not photographed, and still owed:

* a. Contracts → a demo person: the scope strip, the list, the badge;
* b. a person attached to `Rize India Payroll` showing that scheme's components
   and ₹ — **note that the live data already IS this case** (§6), so this is a
   look, not a change;
* c. the unassigned empty state and its button landing on Who is paid by what;
* d. editing a virtual row, saving, reopening;
* e. Explorer grouped by Country and by Payroll scheme;
* f. the insights assistant answering "payroll cost by payroll scheme";
* the 390px phone width of the scope strip and the folded group.

**Nothing was attached or changed on `rize` for validation** — the data already
contained the case the handover asked me to create, so there is nothing to
undo.

What was done instead, and what it does and does not prove:

* the public sign-in page was opened in Chrome MCP and its console read: **one
  non-blocking issue** ("Lazy-loaded images should have explicit dimensions"),
  **no JavaScript errors**;
* the backend asset bundle was compiled on the live `rize` database —
  **3,076,376 bytes of CSS, JS OK**, and `pbc-scope`, `pbc-scope-name`,
  `pbc-scope-co`, `pbc-other-h`, `pbc-comp-nil` and the `virtual` row state are
  all present, so the new SCSS is valid and shipped;
* the edited OWL template parses as XML and `node --check` passes on the JS;
* the exact payloads the screens read are in §6.

## 8. Handover facts that were wrong or incomplete

1. **§4.2's virtual rows need a key that is not the line id.** Every virtual
   row has `id: False`, so the client had to be re-keyed onto
   `compRowKey`/`compRefKey` throughout; `false` repeated down a list is one
   key for many rows, and OWL edits the wrong cell.
2. **§4.2 assumed the drawer's add path already handles a row with no
   catalogue entry.** It does not — `_cd_judge_components` requires a
   `template_id`. It now accepts a `code`, and the SAVE creates the catalogue
   row; the preview judges the same plan and still writes nothing.
3. **§4.4 says "skip lines outside the scope unless they hold a value".** The
   comp card already skipped every zero line before this phase, so that rule
   changed nothing by itself. A valued out-of-scheme line is now KEPT and
   labelled, which is what the non-goal demands.
4. **§4.5's `/root` CSV path cannot be written.** An Odoo shell runs as `odoo`.
   Ledger **SC10** — and the same trap in mirror image blocks `pg_restore`
   reading out of `/odoo` as `postgres`.
5. **§6's rize validation step (b) has nothing to attach.** The live data is
   already a person on the India scheme with Vietnamese components.
6. **The handover did not anticipate that removing the fan-out breaks the
   fixtures that relied on it** — three CD suites and one formula suite.
   Ledger **SC9**.

## 9. Deviations from the spec

1. **The component scope is wider than §4.1 says** — the scheme's declared
   contract/text components PLUS any other rule of the SAME scheme whose code
   the catalogue already carries a row for. Accepted by the owner in flight and
   recorded as ledger **SC8**; pinned by test `12a2`, which proves a code
   belonging only to another scheme still stays out.
2. **The clean-up was not applied beyond `rztest`.** §5. This is the
   instruction's own stop condition, not an omission.

## 10. New gotchas appended to the ledger

**SC8** the widened component scope and why · **SC9** the fixtures the fan-out
was feeding · **SC10** an Odoo shell runs as `odoo`, so the undo file cannot
live in `/root` (and `postgres` cannot read out of `/odoo`) · **SC11** what the
six dry-runs found about the schemes on the demo databases.

## 11. Commits (not pushed)

| Hash | Feature |
|---|---|
| `515e33e83` | the scope helper (`pb_hr_payroll_formula`) |
| `64c862216` | the create-time fan-out removed (`om_hr_payroll`) |
| `fb5d97bdb` | the drawer and the pay package card (`pb_contracts`, `pb_comp_ben`) |
| `e95eeb004` | the clean-up script (`tools/`) |
| `9afdc0d68` | analytics: country from the scheme, grouping by scheme (`pb_explorer`, `pb_payrun_results`, `pb_payroll_ai_insights`) |
| `40272af91` | ledger SC8 / SC9 |
| `00a4fdbf5` | the clean-up's undo path, ledger SC10 / SC11 |

Explicit file staging throughout; the working tree's unrelated deleted and
modified files were left alone. Nothing pushed. 31 commits now unpushed on
`19.1`.

## 12. Open for the owner

1. **The clean-up decision** (§5) — do the six sector schemes on `payobook`
   and the Vietnamese scheme on `rize` need contract components declared, or is
   the mapping wrong? Until that is answered the 117,058 + 140 + 7 empty rows
   stay where they are, harmlessly.
2. **A `rize` login, or seven clicks** (§7). Same item Phase 1 left open.
3. **`pb_payrun_ledgers` still has Phase 1's currency defect** — recommended
   for Phase 2 by Phase 1's report and not taken into scope by this handover.
4. **The Vietnamese for the PayAI individual-salary refusal and the
   voice-consent copy is missing** (§2). Pre-existing, now measured.
