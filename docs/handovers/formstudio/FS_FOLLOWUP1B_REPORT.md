# FORM STUDIO follow-up 1b — R18 (every company, both screens) + R19 (more My Payobook boxes)

Builder agent, 2026-11-20. Branch `fs-followup-1b` from `origin/fs-followup-1` @ `91076674f`.
Local only: nothing deployed, the live server not touched. White-label checked: no new
user-visible string names the platform; every new string has vi_VN + id_ID entries (and the
`.pot`), all touched `.po`/`.pot` parse with `PoFileReader` (0 empty msgstr).

Commits: `e4d93c3f5` R18 · `f79f0d1ad` R19 · this report.

## 1. Facts found (code at `origin/fs-followup-1`, then proved on a local two-company copy)

| # | Fact | Where |
|---|---|---|
| F1 | A layout row is per company (`company_id` required, unique `host_key, company_id`) | `pb_form_studio/models/form_layout.py:19-28` |
| F2 | `_pbfs_layout` looked up the row of `company or self.env.company` — the WORKING company unless a caller passed one | `pb_form_studio/models/form_studio.py:633-636` |
| F3 | With no row, `_pbfs_effective` falls back to the host's `default_layout`, which places **no custom field** (`'custom': []`) — so "no layout in this company" = "no custom field on this screen" | `form_studio.py:646-660`; hosts `pb_form_studio_people/models/form_studio.py:135`, `pb_form_studio_contracts/models/form_studio_host.py:50` |
| F4 | `render()` (both panels, both pages) reads `_pbfs_effective(host_key)` = the working company | `form_studio.py:1358`, version at `:1383` |
| F5 | Employee panel / full page: `Studio.render(HOST, emp.id)` in the reader's own env → **working company's layout** | `pb_form_studio_people/models/pb_people.py:49` |
| F6 | Contract panel / page: `_fs3_render` switches to `with_company(contract.company_id)` when the reader has that company → **the contract's company's layout** | `pb_form_studio_contracts/models/contract_drawer.py:62-67` (used by `_cd_terms` :117 and `get_contract_detail` :250) |
| F7 | Full details (employee) and the restyled contract full form ("Company details" tab) are ONE database-wide view each, written from the layout of whoever published / deleted / changed a country — so they showed in every company. Latent bug: a delete or a Field-library country change made while working in a company with no layout re-drew the page from the empty default and removed it for everybody | `pb_form_studio/models/form_native_view.py:62-75, 141-149`; callers `form_studio.py` publish `:1320`, delete `:1211`, `update_field` (M-c) |
| F8 | People / Contracts table columns and Excel, Updates sheets / Master records, Mapping: decided by `fields_for` (field marks + who-can-see), never by a layout → already every company | `pb_form_studio_lists/models/list_columns.py:24`, `pb_form_studio_reach/models/records.py:28-37`, `mapping.py:59-72` |
| F9 | My Payobook ordering used the record's company's layout | `form_studio.py:1594-1596` |

**Why "the employee side shows everywhere"** — it does only for readers whose WORKING company is the
publishing company (F5): they see the field on people of every company. A reader working in
company B (only B, or B picked in the switcher) did NOT see it on the employee panel either.
The contract panel was stricter (F6): the contract's company decides, so even a reader working
in A did not see it on a company-B contract. Probe on a local copy (field made and placed while
working in company A, person + contract in company B):

| Reader | Employee panel | Full details | Contract panel | Contract page | Full contract form | Contracts table |
|---|---|---|---|---|---|---|
| HR, company B only — before | **no** | yes | **no** | **no** | yes | yes |
| HR, A+B, working in A — before | yes | yes | **no** | **no** | yes | yes |
| HR, A+B, working in B — before | **no** | yes | **no** | **no** | yes | yes |
| all three — after | yes | yes | yes | yes | yes | yes |

## 2. What changed

### R18 — one layout per screen for every company (engine only)
- `_pbfs_layout` (`pb_form_studio/models/form_studio.py:650`) reads THE layout of a screen for the
  whole database; the `company` argument is accepted and ignored. Until the fold below has run,
  the newest published row wins. This one change fixes F5, F6, F7 (the Full details / contract
  form pages are now always written from the same layout) and F9. The contract bridge's
  `with_company` (F6) is left in place: harmless now (it only picks the currency symbol), so
  `pb_form_studio_contracts` is not touched.
- `_pbfs_merge_company_layouts` (`:671`): one-time fold — per screen with 2+ rows, keep the newest
  published, append (same section) any field placed only in another company's row, version =
  highest + 1, delete the other rows, re-draw the Full details pages of the record types touched.
  A field placed in NO layout stays off every screen (the administrator's choice kept).
- Migration `pb_form_studio/migrations/19.0.1.2.0/end-one_layout_per_screen.py` (an `end-` script:
  the screens are registered by the bridge modules loaded after the engine). Does nothing when no
  screen has 2+ rows; idempotent; logs counts (see §5).
- Drafts follow their administrator across companies (`_pbfs_drafts` `:1300`, used by
  `get_studio`, `save_draft`, `discard_draft`, `publish`); the publish notice goes to every
  internal user (`_pbfs_notify` `:1408`).
- Publish sheet line: "Everyone in this company sees…" → "Everyone, in every company, sees the
  new layout the next time the screen loads." (vi, id updated).
- Unchanged: Country of Work limits (R10), who-can-see, field marks, the five hosts.

### R19 — more standard boxes on My Payobook
- Engine `_pbfs_portal_writes_through` (`form_studio.py:285`): a box the employee holds through
  `hr.version` (`_inherits`, Odoo 19) is changeable when the box it stands for is plain, stored and
  editable — those were all refused as "worked out by the system". Writing goes through the same
  single path (`portal_apply`), so the history line and audit row are unchanged.
- Employee host (`pb_form_studio_people/models/form_studio.py`):
  `_pbfs_people_formula_names` no longer counts the two boxes the formula catalogue lists but
  refuses to hand to a payslip (`PAYROLL_EXCLUDED_FIELDS`,
  `pb_hr_payroll_formula/models/application_domain_sources.py:38`, refused at `:274`);
  `_pbfs_portal_locked` keeps the newly reachable boxes that must stay HR's, one plain reason each
  (`PORTAL_ADDRESS` + five single boxes, lines 84-96 and 241-252).
- Nothing in `pb_me_details`, `pb_me_portal`, `pb_form_studio_reach` code changed; the reach
  request flow already handled standard boxes.

**Readers checked before opening a box** (repository-wide grep of `.py/.xml/.js`, vendored
standard addons excluded): pay formula catalogue `application_domain_sources.py:19-49` (+ related
`:45-51`), tax sources `pb_me_tax/models/formula_sources.py:34-44`, Vietnamese social-insurance
files `pb_hr_govt/models/report_base.py:175-261`, government tax forms
`pb_form_lines/models/reader.py:214-282` and `render_sg.py:183`, working time zone
`pb_hr_payroll_formula/models/employee_work_timezone.py:76-106`, Mapping lanes
`pb_formula_studio/models/pb_formula_studio.py:10276-10291` (import destinations only), the side
panel display `pb_employee_vault/models/employee_details.py:65-66`. No Indonesian BPJS or tax file
reads any of the six opened boxes (BPJS numbers, family card, NPWP, PTKP stay locked).

### R19 plain-words table (standard boxes on the employee screen)

| Box (as on screen) | Can be opened now | Why not |
|---|---|---|
| Work Mobile | yes (already) | |
| Show to all employees (birthday) | yes (already) | |
| Country of Birth | yes (already) | |
| Visa No | yes (already) | |
| Visa Expiration Date | yes (already) | |
| **Spouse Legal Name** | **yes (new)** | |
| **Spouse Birthdate** | **yes (new)** | |
| **Home-Work Distance** | **yes (new)** | |
| **Home-Work Distance unit** | **yes (new)** | |
| **Blood type** | **yes (new)** | |
| **Religion** | **yes (new)** | |
| Private Phone, Private Email, Private Street (first address line) | no | The employee already changes it on My details (address and phone request) |
| Emergency Contact, Emergency Phone | no | The employee already changes it on My details |
| Private Street2, City, Zip, State, Country (rest of the address) | no | Government forms print the home address; the first line already goes through My details |
| Identification No, Passport No / expiry, Work Permit No / expiry, Marital Status | no | The employee already changes it on My details (ID papers, marital status) |
| Dependent Children | no | Children who count for tax go through My details, Family, where the pay team confirms them |
| SSN No | no | Social security numbers are set by HR |
| Legal Name | no | Must match the ID papers; its given and family parts are read by pay formulas |
| Additional Note | no | HR's own note about the person |
| Timezone | no | Follows the place of work and is used to count working time |
| Employee Name, Legal given / family name, Birthday, Place of Birth, Gender, Nationality, Certificate Level, Field of Study, Permanent address, Visa status, Job level, Work Phone, Work Email, Employee Id, Badge ID | no | A pay formula can read it |
| Bank, Account holder | no | Bank details change through the bank change request |
| Tax numbers and tax status boxes | no | Changed through Tax details |
| Country of Work | no | Decides which rules apply |
| Company, Department, Job, Job Title, Manager, HR business partner, Buddy, Work Address, Work Location | no | Set by HR |
| Contract dates, Contract Type, Salary Structure Type, Working Hours, Employee Type, Trial period, Date of Joining, Departure boxes, Ruleset, Absence policy family | no | Part of the contract |
| User, PIN, Clock number, HR Responsible, approvers | no | Login and access are set by HR |
| Wage, Hourly Cost | no (not even shown) | Pay figures are never shown on My Payobook |

Two competing ways? Address and emergency contact: yes (My details writes the same boxes) → left
closed. Spouse: My details › Family lets the employee add a husband or wife as a family member —
a DIFFERENT record, not these two boxes, so they are opened; see owner question 1.

## 3. Version raises (one each)
| Module | Before | After |
|---|---|---|
| pb_form_studio | 19.0.1.1.0 | 19.0.1.2.0 (migration) |
| pb_form_studio_people | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_form_studio_reach | 19.0.1.0.1 | 19.0.1.1.0 (tests only) |

Not touched: pb_form_studio_contracts, pb_form_studio_lists, pb_form_native_look,
pb_employee_form_tidy (19.0.1.2.0), and every "do not edit" module. **No merge risk** in another
work stream's module.

## 4. Tests (local, `--test-tags` the five Form builder suites, `-u` of the five)
Baseline on an untouched copy of `fsf1_base`: **93 tests, 0 failed, 0 errors**.
After: **112 tests, 0 failed, 0 errors** = baseline + 19 new, all passing.

| # | Test | Result |
|---|---|---|
| E1 | Layout published working in A is read by a reader working only in B | pass |
| E2 | Publishing from B updates the same row; A sees it | pass |
| E3 | Fold of two per-company layouts: newest kept, other field carried, version above both; second run writes nothing | pass |
| E4 | A field placed nowhere stays off every screen after the fold | pass |
| E5 | No layout: the fold writes and creates nothing | pass |
| E6 | One draft per administrator across companies | pass |
| C1 | Employee panel / page, Full details, People table column — HR working only in B | pass |
| C2 | Contract panel group (+ saved there), contract page, full contract form tab, Contracts table, Excel cell, Updates catalogue — company B | pass |
| C3 | Reader with A+B, either working company, on a company-B contract and person | pass |
| C4 | India-only contract field absent for a Vietnam contract in B (panel, page, table blank, form rule), present for India | pass |
| C5 | Administrators-only contract field never reaches the company-B manager | pass |
| B1 | The six boxes take both ticks (default HR approves); 15 locked boxes refuse with a reason, no "Odoo" | pass |
| B2 | Nothing ticked by default; the employee sees none of the six | pass |
| B3 | Unticked: not on the page or form; forged POST and direct calls refused; nothing written | pass |
| B4 | HR approves: request in the inbox, value unchanged; approve writes; refuse leaves it | pass |
| B5 | Saves at once: saved, history line on the record, one history row per box | pass |
| B6 | Another employee sees only their own values; cannot read or change Lan's (page, forged id, direct calls) | pass |
| B7 | Locked boxes (address, children, emergency contact, bank, Country of Work, manager, SSN, legal name, note, time zone, birthday, name) refused even when forged, even with "shown" ticked | pass |
| B8 | My details flows untouched (address, phone, email, emergency, ID papers, marital still "Already on My details") | pass |

Also run by hand: the migration on a local copy holding two employee layouts (companies A and B,
three fields, one unplaced) + one contract layout → log "folded 1 screen(s)… 1 per-company
layout(s) removed, 1 field placement(s) carried over"; Full details then names both placed fields,
not the unplaced one; all five module versions = manifests. On a copy with no layout: "0
layout(s) for 0 screen(s), one each; nothing to fold". No browser walk this time (the change
has no new screen; the HTTP tests drive My Payobook as a real portal login).

## 5. Deploy notes
1. Ship trees: `pb_form_studio`, `pb_form_studio_people`, `pb_form_studio_reach` (the other
   Form builder trees are unchanged vs `origin/fs-followup-1`).
2. Per database: `-u pb_form_studio,pb_form_studio_people,pb_form_studio_reach` (the engine
   first; `-u` of it also re-loads its dependents). JS string changed → purge `/web/assets/%`
   attachments, restart.
3. **Before**, per database: `SELECT host_key, company_id, version FROM pb_form_layout ORDER BY 1,2;`
   Expected today: 0 rows on the customer databases, ≤1 row per screen on payobook (2 DEMO fields).
   **After**: the log line `pb_form_studio R18:` — "nothing to fold" where every screen had ≤1 row;
   otherwise "folded N screen(s)…" and the same query shows one row per screen.
4. What the migration writes: only where a screen has 2+ rows — one row rewritten (sections,
   version), the others deleted, the Full details / contract form pages re-drawn. Nothing else.
5. Nothing to press. Nothing is ticked for My Payobook anywhere; no employee sees anything new until
   an administrator ticks a box.
6. On payobook.com: after the upgrade the two DEMO fields show on the employee and contract panels
   in all four demo companies (that is R18).

## 6. Risks
- R18 is a behaviour change by design: on a database with several companies, an administrator who
  had DIFFERENT layouts per company now has one (the newest). None exists on the live databases
  per the deploy report (§6: no custom field on any customer database).
- Publishing now notifies every internal user (bus message only, no mail).
- Writing a spouse / distance box from My Payobook writes the person's current `hr.version`, exactly
  as the HR form does (a "Modified on the Version" note appears on the record next to the history
  line).

## 7. Owner questions (plain words)
1. **Spouse.** Employees can already add a husband or wife on My details › Family (for tax and
   insurance). The two spouse boxes can now also be offered on My Payobook. Offering both may give
   HR two answers — tick the spouse boxes only if you want them kept separately.
2. **Blood type and religion** are now offerable (they never reach a payslip). They are sensitive;
   nothing is offered until an administrator ticks them.

## 8. Not done
- Browser walk (optional) not run.
- The Field library's subtitle still says "Every custom field in this company" (it always listed
  the whole database); left as is to keep this change small.
