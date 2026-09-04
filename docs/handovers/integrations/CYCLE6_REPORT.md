# Integrations Cycle 6 — report: the fields a source is expected to deliver

> Implementation report for `CYCLE6_EXPECTED_FIELDS.md`. Every claim below is
> backed by an artefact: a query against the live database, a ratio computed
> from the live CSSOM, a log line, or a browser observation on
> `abm.payobook.com` / `payobook.com`.

## The owner's two sentences, and what each became

| The owner's words | What shipped |
|---|---|
| "make the studio show the expected Zoho fields from the catalog we shipped in Cycle 3 (marked 'not yet synced') instead of dumping Odoo internals" | A field catalogue — 94 seeded template rows across seven feeds — and a three-layer discovery merge (`live` / `catalog` / `odoo`) carrying a `provenance` on every item. The abm board went from **206 `hr.employee` columns and 0 wires** to **58 named Zoho fields and 16 wires**, and the Odoo fallback can no longer pass itself off as a vendor's schema |
| "the button at top to go back … is not visible intuitively because of the colour and shades … so is Mapping studio on far right" | The chip was not badly shaded — it was rendering the **dark tone on the wrong bar**, because `.pbms` is two different components' root class and specificity handed the studio pb_mission's styling. Fixed at the cause. Measured live: chip boundary **1.30 → 12.73:1**, wordmark **3.17 → 15.08:1** |

---

## Root cause 1 — discovery had no middle layer

`get_available_source_fields` was a two-rung fallback: stored payloads, and
failing that `hr.employee`. On abm:

```sql
SELECT count(*) FROM hr_api_data_store;   -->  0
```

Zero store rows — disconnected by design, per the owner's Cycle-4 ruling — so
the studio listed **206 `hr.employee` columns** under "FROM — ZOHO PEOPLE (ABM)".

It also made correct data look broken. The fifteen mappings Cycle 4 seeded,
read out of `abm` before the fix:

```
 id | feed            | source_field
----+-----------------+-----------------------
  2 | zohoemployees   | EmployeeID
  7 | zohoemployees   | Dateofjoining
 18 | zohoemployees   | Full_Name_Vietnamese
 19 | zohoemployees   | Employeestatus
 21 | zohoemployees   | LocationName
 33 | zohoemployees   | DEPCOUNT
 34 | zohoattsummary  | expectedWorkingHours
 35 | zohoattsummary  | totalWorkedHours
 36 | zohoattsummary  | WORKEDHRS
 37 | zohoovertime    | OTHRS150
 38 | zohoovertime    | OTHRS200
 39 | zohoovertime    | OTHRS300
 40 | zohoovertime    | OTHRS210
 41 | zohoovertime    | OTHRS270
 42 | zohoovertime    | OTHRS390
```

**Nine of the fifteen are not vendor fields at all.** `DEPCOUNT`, `WORKEDHRS`
and the six `OTHRS*` are `hr.api.transformation.rule.output_key` values — the
fields *this platform* adds to a payload. WP-1's seed list does not cover them,
and a catalogue built from seed data alone would have left nine of the fifteen
unresolved. They are derived live from the connector's own rules instead — see
*Deviations*.

## Root cause 2 — `.pbms` is two different components' root class

| file | line | markup |
|---|---|---|
| `pb_mission/static/src/xml/pb_mission.xml` | 8 | `<div class="pbim pbms">` — a DARK shell |
| `pb_formula_studio/static/src/xml/mapping_studio.xml` | 5 | `<div class="pbim pbms">` — a light cockpit |

pb_mission ships **65** `.pbms-*` rules; **four** of its class names are also the
studio's — `pbms-top`, `pbms-brand`, `pbms-brand__ic`, `pbms-canvas`. Every
pb_mission rule is written `.pbim.pbms .pbms-top`, specificity (0,3,0); the
studio's were bare `.pbms-top` at (0,1,0). So Mission Control won every property
it declared and the studio won the rest: the studio's header **background, gap
and font size were Mission Control's command bar**, and its colours were the
studio's. Nothing errored.

The same accident hit the shared back chip. The studio asks for
`tone="'light'"` and gets `.pbhub-back--lite` (0,1,0), which loses to
`.pbim.pbms .pbhub-back` (0,3,0) — so the way home rendered in the **dark tone**,
on a bar it was never designed for.

This is the failure shape that block's own header comment warns about, reached
from the other side: there an *unmatched* selector left the chip unstyled; here
an *over-matched* one styled it for the wrong background.

---

## Contrast — measured in the live browser (test 8)

WCAG 2.1 relative luminance computed from `getComputedStyle`, with
`color-mix(in srgb, …)` flattened against the backdrop the element actually sits
on. Two parsing traps had to be handled to get honest numbers: `color(srgb …)`
reports channels in 0..1 while `rgb()` uses 0..255 (treating one as the other
silently turns white into black), and the studio's bar is **`#241F52`**, not the
light `--pbim-bg`.

> **Correction.** The commit message for `b5837bd6` quotes "1.08:1" for the back
> chip. That figure assumed the studio's bar was `--pbim-bg` and is wrong. The
> table below is the measured truth, and `ba8c7039` carries the correction. The
> defect and its cause are unchanged; only the number describing it was.

### The Mapping Studio header (backdrop `#241F52`)

| | before | after | needs | |
|---|---:|---:|---:|---|
| back chip **text** on its own fill | 11.55:1 | 7.39:1 | 4.5 | both pass |
| back chip **fill** vs the bar | **1.30:1** | **12.73:1** | 3.0 | ✗ → ✓ |
| back chip **border** vs the bar | 2.01:1 | 2.20:1 | — | n/a — the fill carries the boundary here |
| back chip border vs its own fill | — | 5.78:1 | 3.0 | ✓ |
| chip height | 28px | **32px** | | |
| **wordmark** text | **3.17:1** | **15.08:1** | 4.5 | ✗ → ✓ |
| wordmark pill vs the bar | 1.00:1 | 15.08:1 | 3.0 | ✗ → ✓ |

So the chip was never illegible — it had **no body**. White text inside a 1.30:1
ghost of a fill, on navy, is a word floating in a bar. That is precisely "not
visible intuitively": it did not read as a control. The wordmark, at 3.17:1,
genuinely failed AA with no large-text exemption at 12px.

### The light cockpits (backdrop `#F5F6FA`) — Structures, Integrations

| | before | after | needs | |
|---|---:|---:|---:|---|
| chip **text** | 6.84:1 | **7.39:1** | 4.5 | ✓ |
| chip **border** vs the bar | **1.14:1** | **6.34:1** | 3.0 | ✗ → ✓ |
| chip fill vs the bar | 1.08:1 | 1.10:1 | — | n/a — the border carries it here |
| chip hover text | — | 6.84:1 | 4.5 | ✓ |

### The dark hosts (backdrop `#241F52`) — pb_hub shell, probed live

| | before | after | needs | |
|---|---:|---:|---:|---|
| chip **text** | 11.55:1 | 9.17:1 | 4.5 | ✓ |
| chip **border** vs the bar | **2.01:1** | **3.82:1** | 3.0 | ✗ → ✓ |
| chip height | 28px | 30px | | |

The boundary is carried by whichever of border/fill contrasts with the host: the
fill on the studio's dark bar (12.73:1), the border on a light cockpit (6.34:1),
the border on dark chrome (3.82:1). Every host clears WCAG 1.4.11's 3:1 on at
least one, which is what makes it read as a control rather than as a caption.
Both tones also gained an `:active` state and a `:focus-visible` ring.

The light chip is deliberately **not** a solid primary button at rest — it would
outrank every real action on the page above it. It fills on hover: it announces
itself when reached for and stays second in the hierarchy when it is not.

---

## Test results

### Python — **0 failed, 0 error(s) of 152 tests**

Scoped run (`-u` + `--test-tags` across `pb_hr_payroll_formula`,
`pb_formula_studio`, `pb_import_advanced`, `pb_integrations`, `pb_settings`,
`pb_hub`), inside a W136 stall-proof unit.

```
odoo.tests.result: 0 failed, 0 error(s) of 152 tests when loading database 'payobook'
```

Cycle 5's comparable run was 109 tests; this cycle adds 13 and brings `pb_hub`
into scope.

An earlier **whole-tree** run (1338 tests) reported 6 failed + 1 error. The 1
error was this cycle's own test 4 — a `KeyError: 'expected_missing'`, which is
the test doing its job (fixed in `509957ee`). The 6 failures are all outside this
cycle's scope and were not touched:

| test | module | why it is not ours |
|---|---|---|
| `test_a_day_that_has_not_happened_yet_is_not_unfinished_business` | pb_close | clock-dependent; the run was at 22:00 UTC |
| `test_a_live_shift_nobody_punched_is_late_only_once_the_clock_passes` | pb_today | clock-dependent |
| `test_day_defaults_to_today` | pb_today | clock-dependent |
| `test_every_seeded_punch_is_inside_the_utc_safe_window` | pb_demo | clock-dependent |
| `test_the_today_board_carries_the_tile_and_stays_read_only` | pb_ess_workforce | clock-dependent |
| `test_today_invents_no_hex` | pb_today | its `_walk` scans `pb_today` only (`pb_today/tests/test_static.py:70`) — no file this cycle touched is in its path |

### Per-test evidence

| # | Test | Evidence |
|---|---|---|
| 1 | Catalogue templates instantiate create-only; re-run creates 0; a renamed/deactivated row survives | `test_01` — relabels `EmployeeID`, deactivates `Mobile`, re-syncs, asserts `created == 0`, the label and sample intact, the deactivated row still counted under `active_test=False`. `test_01b` proves an unresolvable `endpoint_code` is counted as `unresolved` and never attached to another feed |
| 2 | No store rows → `catalog` provenance and **no** Odoo fields; with rows, live wins and duplicates collapse; neither → `odoo`, marked | `test_02` asserts the three `hr.employee` columns from the owner's screenshot are absent. `test_02b` asserts one card per path, `provenance == 'live'`, and the live sample overriding. `test_02c` uses an uncatalogued vendor and asserts **every** item is `provenance == 'odoo'`. `test_02d` asserts directly that with an empty store nothing may claim `live`, across five scopes |
| 3 | Catalogue `sample_value` surfaces; a live sample overrides it | `test_03`, both directions |
| 4 | `expected_missing` only after a first sync — never on a virgin connector | `test_04`, extended after the live pass to assert the **per-feed** rule too (see W153) |
| 5 | The 15 abm-shaped mappings resolve; no false warning; a genuinely unknown path still warns | `test_05` replicates all fifteen paths and asserts each resolves *on its own feed*; `test_05b` an unknown path; `test_05c` rule outputs are `catalog`/`computed`, not `live`. Live confirmation below |
| 6 | Fetch-field-list upserts where implemented, errors honestly where not, leaks no credential | Live on payobook — below |
| 7 | ACLs: read for user, CRUD for admin, on both new models | `test_07` (both models, both tiers) and `test_07b` (uniqueness proven against PostgreSQL, since W33 means the python guard does not exist) |
| 8 | Contrast before/after, asserting AA | The measured tables above, from the live CSSOM on five hosts |
| 9 | Cycle 5 regressions; legacy overlay; suites green | Below |
| 10 | Live validation on abm and payobook at ~1900px | Below |

### JS — 3 new tests for the provenance chip

Added to `pb_formula_studio/static/tests/mapping_canvas.test.js`: the quiet case
(a delivered field wears no chip), the three catalogue sentences with drift
outranking both, and the four boards that send no `prov` at all rendering
exactly as they did.

---

## T5 — the fifteen abm mappings, path by path

Resolved against the live `abm` database after deploy. **15 of 15.**

| # | source_field | feed | resolves as |
|---|---|---|---|
| 1 | `EmployeeID` | zohoemployees | catalog · feed |
| 2 | `Dateofjoining` | zohoemployees | catalog · feed |
| 3 | `Full_Name_Vietnamese` | zohoemployees | catalog · feed |
| 4 | `Employeestatus` | zohoemployees | catalog · feed |
| 5 | `LocationName` | zohoemployees | catalog · feed |
| 6 | `DEPCOUNT` | zohoemployees | catalog · **computed** |
| 7 | `expectedWorkingHours` | zohoattsummary | catalog · feed |
| 8 | `totalWorkedHours` | zohoattsummary | catalog · feed |
| 9 | `WORKEDHRS` | zohoattsummary | catalog · **computed** |
| 10 | `OTHRS150` | zohoovertime | catalog · **computed** |
| 11 | `OTHRS200` | zohoovertime | catalog · **computed** |
| 12 | `OTHRS300` | zohoovertime | catalog · **computed** |
| 13 | `OTHRS210` | zohoovertime | catalog · **computed** |
| 14 | `OTHRS270` | zohoovertime | catalog · **computed** |
| 15 | `OTHRS390` | zohoovertime | catalog · **computed** |

No mapping was re-seeded, edited, created or deleted. The fifteen rows are
byte-identical to what Cycle 4 wrote; only what the board can *see* changed.

---

## T10 — the owner's exact scene, on abm

`Zoho People (ABM) → AB Mauri Payroll Vietnam`, 1900px viewport.

| | before | after |
|---|---|---|
| FROM column | 206 `hr.employee` columns — `account_number`, `active`, `activity_calendar_event_id`… | **58 named Zoho fields** — `Aadhaar_Number`, `Actual_Pay_Hour`, `ApprovalStatus`, `Bank_Account_Number_VND`… |
| FROM sub-line | `206 fields · never synced` | **`58 expected fields · Zoho People (ABM) catalogue · not yet synced`** |
| wires drawn | 0 | **16** (15 mapped + 1 suggested) |
| honesty banner | `15 mappings point at a field this source no longer delivers.` | **absent** — every mapping now has a card |
| first-run hint | — | *"These are the fields Zoho People (ABM) is expected to deliver. Map them now — the first sync will confirm them."* |
| provenance chips | — | `EXPECTED` on catalogue fields, `COMPUTED` on rule outputs |
| samples | — | `e.g. 2345 6789 0123`, `e.g. 4.5`, `e.g. Approved` — italic `e.g.` in the neutral wash, so an illustration cannot be mistaken for a received value |

Screenshots in `.ig-c6-shots/`: `after-04-owner-scene-abm.png` is the scene.

Console: **0 errors**. Network: **0 responses ≥400** across 27 requests.

## T10 — payobook

The whole-database provenance census, taken through the live RPC across all
**26** connectors:

* every item on every connector carries a `provenance` — **0** items without one;
* **0** items came back `odoo` anywhere on payobook, because every connector
  there has store rows. The fallback is now genuinely last-resort;
* the demo `Zoho People` connector reports `{catalog: 58, live: 3}`;
* `DarwinHR (Darwinbox)` reports `{catalog: 24, live: 3}` after test 6's fetch.

Cycle-5 regressions on the payobook board: five mode tabs, both column search
boxes, `All / Mapped / Unmapped` chips, the story-bar counts, the FROM picker
listing 26 connectors with their feed/mapping/sync sub-lines — all present and
behaving.

## T6 — vendor metadata fetch, live

Three tiers, because there are genuinely three different things
`get_available_fields()` does in this codebase:

| tier | connectors | what it does |
|---|---|---|
| `live` | **zoho**, **excel** | a real request — Zoho GETs `forms/{form}/components` (`zoho_connector.py:216`); Excel reads the loaded file's headers (`excel_connector.py:272`) |
| `sample` | **darwin**, **demo** | derived from a sample record built into the class (`darwin_connector.py:116`, `demo_connector.py:421`) — real paths, real types, no network |
| *(refused)* | **sap**, **workday**, **oracle** | each logs "not implemented" and returns a hard-coded example list (`sap_connector.py:79`, `workday_connector.py:75`, `oracle_connector.py:77`) |

Verified on payobook:

* **DarwinHR** — `field_fetch: {mode: 'sample', ready: true}`; pressing *Fetch
  fields* on "Employee Master Data" took it from no catalogue to **24 expected
  fields**, and **only that feed** changed;
* **Oracle ERP Cloud** — `field_fetch: {mode: null, ready: false, reason: "Payobook's
  Oracle HCM connector cannot yet ask that system what fields it has. The
  expected fields below come from the shipped catalogue instead."}` and the
  button is **not rendered at all** (`Sync · View data · Map fields` only);
* **no credential value in any payload.** The cockpit detail JSON was fetched
  and scanned for `client_secret`, `refresh_token`, `access_token`, `api_key`
  and `password` holding a non-empty value: **none found**. The credentials
  block carries `is_set` booleans only.

The abm Zoho connector's button renders **enabled** (it has stored credentials),
and it was deliberately **not pressed** — see *Nothing was left for the owner to
decide*.

## T9 — the shared back chip, swept

`.pbhub-back` is rendered by eleven cockpits. Measured on five surfaces:

| host | tone | text | boundary | verdict |
|---|---|---:|---:|---|
| Mapping Studio (abm) | light on `#241F52` | 7.39:1 | 12.73:1 (fill) | ✓ |
| Structures (abm) | light on `#F5F6FA` | 7.39:1 | 6.34:1 (border) | ✓ |
| Integrations, entered from Settings (abm) | light on `#F5F6FA` | 7.39:1 | 6.34:1 (border) | ✓ |
| pb_hub shell command bar (People hub, abm) | dark on `#241F52` | 9.17:1 | 3.82:1 (border) | ✓ |
| Mission Control (abm) | — | — | — | renders unchanged; its dark `.pbms-top` and layout are intact, confirming the `.pbms-wrap` scoping cannot reach it |

The connector cockpit uses a `pbim-btn ghost` back button rather than the kit
chip; noted, not changed.

The dark tone had no drill-in on this tenant (every hub was entered from the
rail, so `back` is correctly absent — W29), so it was verified by mounting a
real `.pbhub-back` into the real pb_hub command bar and measuring the shipped
rule against the real backdrop, before and after.

## Item 5 — the floating launchers

Both are ours, and both position themselves against the **viewport**, so nothing
inside the cockpit could push them off it. Measured at 1900px with the TO column
running x 1580-1920:

| | before | after |
|---|---|---|
| `.lrn-fab` (pb_learn "Stuck?") | x 1794-1896 — inside the column | x 1438-1540 — clear |
| `.payai-floating-pill` | x 1838-1896 — inside the column | x 1482-1540 — clear |

Moved, not hidden, and only on this board: they belong bottom-right everywhere
else, and this is the one screen whose right edge is a dense scrolling list all
the way down. `:has()` was needed because both hosts are siblings of the
cockpit; an engine without it drops the rule and they stay put. Verified
unchanged on Mission Control in the same session. **Trade-off, stated:** they now
sit over the wire canvas, which is decorative rather than interactive — clear of
both columns, but visually in the middle of the wires.

---

## Deploy

Four windows, all W136 stall-proof units (each stops the service, upgrades, and
starts it again itself), plus asset-only redeploys.

| unit | what | result |
|---|---|---|
| `i6deploy` | models + data + assets, both databases | `EXIT_PAYOBOOK=0` `EXIT_ABM=0` `ACTIVE=active` |
| `i6deploy2` | the catalogue-instantiation migration | `EXIT_PAYOBOOK=0` `EXIT_ABM=0` `ACTIVE=active` |
| `i6tests2` | scoped `-u` + `--test-tags`, then abm `-u` | `EXIT_TESTS=0`, 152 tests green |
| `i6css` ×3 | SCSS redeploys | `EXIT_PAYOBOOK=0` `EXIT_ABM=0` each |
| `i6final` | final scoped test + abm `-u` | `EXIT_TESTS=0` `EXIT_ABM=0` `ACTIVE=active` |

ERROR/CRITICAL in the upgrade windows: **0**.

Versions after, identical on both databases:

```
pb_hr_payroll_formula  19.0.1.56.0
pb_formula_studio      19.0.1.76.0
pb_hub                 19.0.1.4.0
pb_import_advanced     19.0.1.5.0
```

Data landed, verified by count and per-connector:

```
              templates   instantiated
payobook          94           50  (Zoho People)
abm               94           50  (Zoho People (ABM))
```

```
Cycle 6: expected-field catalogue instantiated on 32 connectors —
         50 created, 0 already present, 94 templates naming a feed
         these connectors have not got.            [payobook]
Cycle 6: expected-field catalogue instantiated on 2 connectors —
         50 created, 0 already present, 0 …        [abm]
```

Asset discipline: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` on
both databases after each SCSS redeploy, plus a cache-ignoring reload (W150.2).
W131 was re-earned: two `--test-tags` processes kept running past
`--stop-after-init` and had to be ended by PID before the unit could proceed.

---

## Findings for the owner (not bugs in this cycle's code)

1. **The `.pbms` class collision is wider than the back chip.** pb_mission owns
   65 `.pbms-*` rules and the Mapping Studio 52; four names overlap. This cycle
   made the studio's header immune, but the *canvas* (`pbms-canvas`) still
   shares a name, and any new `.pbms-*` rule in either module can silently take
   over the other's. Worth a rename in one of them; out of scope here.
2. **payobook's DarwinHR connector has derived feeds, not catalogued ones.** Its
   endpoints are `Dependents / Family`, `Employee Master Data`, `Leave /
   Time-Off` — derived from store data types, not the vendor codes
   `darwinemployees` / `darwincompensation`. So the Darwin field templates
   resolve to nothing there, and the `unresolved` counter says so rather than
   attaching paths to a feed that cannot return them. "Detect feeds" would
   catalogue the vendor codes alongside.
3. **The demo Zoho People connector on payobook now shows 58 catalogue fields
   against 3 live ones.** That is honest — its synthetic payloads carry
   `external_id`, `kind`, `source` and nothing else — but it means the demo
   board is mostly "expected". If the demo world should look like a working
   integration, its seeded payloads need the real Zoho keys.
4. **abm's Zoho People (ABM) connector has stored credentials and a working
   `Test connection`.** The cockpit reports *Connection successful* while the
   connector is `Disconnected` by the Cycle-4 ruling. Nothing was pulled.

---

## Deviations from the handover, and why

1. **Transformation-rule outputs are derived live, not seeded as data.** WP-1's
   seed list covers the vendor's own keys; nine of abm's fifteen mappings name a
   rule `output_key` instead. Those rules are **per connector** and an operator
   can add more, so duplicating them in `integration_endpoint_fields.xml` would
   have created a second source of truth that drifts the first time somebody
   adds a rule. They are read from `hr.api.transformation.rule` at discovery
   time, still under `provenance='catalog'` — the three-value vocabulary is
   unchanged — with a secondary `catalog_kind` of `feed` or `computed` so the
   studio can say "computed" rather than "expected". Without this, nine of the
   fifteen would still be unresolved.
2. **A migration was needed that the handover did not call for.** Shipping the
   data is not landing it: after the first `-u`, both databases had all 94
   template rows and **zero** instantiated fields, because the sync only fires
   on connector create and from "Detect feeds". `19.0.1.53.0/post-instantiate_field_catalog.py`
   calls the create-only sync on every existing connector (W121's second-pass rule).
3. **Ask 2's root cause was a CSS collision, not a colour choice**, so the fix
   is a `:not()` guard and a `.pbms-wrap` scope as well as new tones. Fixing only
   the shades would have left the studio taking pb_mission's styling and the bug
   one refactor away from returning.
4. **The studio's `.pbms-top` and `.pbms-brand` were re-scoped** — beyond the
   handover's brief — because leaving them at (0,1,0) meant this cycle's
   carefully measured header could be silently re-overridden by any pb_mission
   edit. Same pixels, by intent rather than by luck.
5. **The PayAI pill was moved as well as the coach FAB.** The handover named one
   floating widget; measurement found two, both ours, both inside the TO column.
6. **The contrast table was recomputed and corrected mid-cycle.** The first
   pass assumed the studio's bar was `--pbim-bg`; it is `#241F52`. See the
   correction note above.
7. **Commits are 12, not 7.** Five of them are fixes the live pass forced —
   the swallowed AttributeError, the migration, the header scoping, per-feed
   drift, and the launcher offset that did not move anything the first time.
   This program's incident history says those land as their own commits rather
   than being folded back into the feature they correct.
8. **`Fetch field list` reads `Fetch fields` on the button.** The full label
   clipped inside the feed card at four-across; the tooltip carries the meaning.
9. **The abm Zoho fetch button was not pressed.** Firing it would make an
   authenticated outbound call to AB Mauri's real Zoho People account. Test 6
   was proven on payobook's demo connectors instead.

---

## New rules — W151 … W153

Appended to `docs/WORKFORCE_REDESIGN_CONVENTIONS.md` in the same commit as this
report.

- **W151** A root class name is a GLOBAL name; two components sharing one do not
  clash loudly — the more specific selector silently wins, property by property.
  Grep before claiming one; exclude a self-declared variant with `:not()` rather
  than out-specifying it; disambiguate on a wrapper only one host has; and
  measure contrast against the backdrop the element *actually* sits on.
- **W152** A `try/except` that renders an empty region instead of a 500 must
  still LOG, or a raised exception and a genuinely empty result are the same
  screen. Also: `_schema_ready()` is not inheritable by wishing — check which
  class declares it.
- **W153** A per-connector fact must not be asserted about a per-feed thing. A
  warning that fires on a screen with nothing wrong trains the reader to stop
  reading warnings.


---

## Final live state, after the last deploy

**abm** — `Zoho People (ABM) → AB Mauri Payroll Vietnam`:

```
FROM sub-line : 58 expected fields · Zoho People (ABM) catalogue · not yet synced
left column   : 58 cards  (50 EXPECTED + 8 COMPUTED, 0 NOT SENT)
story bar     : 15 mapped · 1 suggested
honesty banner: absent
console errors: 0        non-200 responses: 0 / 27
```

Zero `NOT SENT` chips is the correct answer for a connector that has never
synced — that is W153 holding.

**payobook** — the demo `Zoho People` connector, which is what forced W153:

```
61 fields  {catalog: 58, live: 3}
drift: 35, and only on the two catalogued feeds that have actually run
       employee 31 · leave 4
feeds that have synced: dependent, employee, leave
attendance / custom / salary have never run and report no drift
```

Before the fix the same board reported **58** drift — every catalogued field of
every feed, including five that have never run.

## Teardown

Both temp validators and their residue removed in the same session. Residue
cleared **before** the `unlink`, fallback branch beginning with `rollback()`
(W144).

```
===== abm =====                        ===== payobook =====
IGC6-TARGET ig-c6-validator@abm  [10]  IGC6-TARGET …@payobook  [2101]
IGC6-RESIDUE payroll.ai.conversation 1 IGC6-RESIDUE mail.presence 1
IGC6-RESIDUE mail.presence 1           IGC6-RESIDUE res.device.log 1
IGC6-RESIDUE res.device.log 3          IGC6-RESIDUE res.users.log 1
IGC6-RESIDUE res.users.log 1           IGC6-UNLINKED ok
IGC6-UNLINKED ok                       IGC6-PARTNER-UNLINKED ok
IGC6-PARTNER-UNLINKED ok
```

`payroll.ai.conversation` on abm again — the same row that blocked Cycle 4's
teardown and Cycle 5's. Absence read back from the database rather than from the
script's own output (W144.3):

```sql
-- payobook                              -- abm
SELECT count(*) FROM res_users            SELECT count(*) FROM res_users
  WHERE login LIKE 'ig-c6%';   -->  0       WHERE login LIKE 'ig-c6%';   -->  0
SELECT count(*) FROM res_partner          SELECT count(*) FROM res_partner
  WHERE name ILIKE '%IG-C6%';  -->  0       WHERE name ILIKE '%IG-C6%';  -->  0
```

Service after teardown: `active`; `payobook.com` 200, `abm.payobook.com` 200.
The session-unique staging directory and all six deploy unit scripts were
deleted (W118/W119).

**Not mine, left alone:** payobook's login page still offers
`c6_probe_manager / C6 PROBE`, and abm's still offers `ig-c5-validator@abm.local`
and `ig-c4-validator@abm.local` — those two are *browser-remembered logins*, not
users (both were confirmed deleted in their own cycles). `c6_probe_manager` is a
real user from another work stream and was not touched.

## Commits

| # | Hash | Subject |
|---|---|---|
| 1 | `eff3848c` | feat(pb_hr_payroll_formula): the fields a feed is expected to deliver |
| 2 | `67c006a1` | feat(pb_hr_payroll_formula): the Zoho and Darwin field catalogues, as data |
| 3 | `2dd7b6cf` | feat(pb_hr_payroll_formula): discovery is layered, and says where each field came from |
| 4 | `c486ab5d` | feat(pb_formula_studio): the studio stops calling Odoo's schema "Zoho" |
| 5 | `cc957034` | feat(pb_import_advanced): fetch the field list from the vendor |
| 6 | `b5837bd6` | fix(pb_hub): the way back is a control you can see |
| 7 | `80508e4e` | fix(pb_hr_payroll_formula): land the field catalogue on connectors that already exist |
| 8 | `509957ee` | fix: two defects the live abm board found, and the reason it could |
| 9 | `ba8c7039` | fix(pb_formula_studio): the studio's own header, and the coach off the TO column |
| 10 | `0f1d082f` | fix: drift is a claim about a feed that ran, not about a connector |
| 11 | `a982046c` | docs(integrations): Cycle 6's ledger — W151-W153 — and the report |
| 12 | `6d397ec8` | fix(pb_formula_studio): move the launchers themselves, not their host |

Explicit staging throughout. Nothing pushed. `.claude/settings.json`, `thaco/`
and `ABM/` never staged.

Note on commit 5: its server side (`action_fetch_endpoint_fields`,
`field_fetch_capability`, `FIELD_FETCH_SUPPORT`) landed inside commit 2, which
also carried the sync hook in the same file. The commit message for 2 describes
only the hook; this is the correction.

## Nothing was left for the owner to decide mid-cycle

No destructive or irreversible action was required. On abm: no mapping,
connector, endpoint or payload record was created, modified or deleted — the
only writes were the 50 catalogue rows the migration created, which is the
cycle's deliverable. The `Fetch field list` button on abm's Zoho connector
renders enabled and was **deliberately not pressed**: firing it would make an
authenticated outbound call to AB Mauri's real Zoho People account, which is the
owner's decision and not an implementation detail. Test 6 was proven on
payobook's demo connectors, where the fetch is sample-derived and touches no
network.

On payobook, one deliberate write: the DarwinHR connector's "Employee Master
Data" feed gained 24 catalogue rows from that test. It is a demo connector, the
rows are create-only, and they are the correct content for that feed.


## Postscript — one more thing the browser caught

`ba8c7039` offset `.lrn-coachhost`. That element is a zero-size,
`pointer-events: none` wrapper; both launchers inside it are `position: fixed`
in their own right, so the host's offsets were never load-bearing. The computed
style changed and **nothing moved** — still x 1794-1896, still inside the TO
column. `6d397ec8` targets the two buttons instead, and the rects were asserted
rather than the CSS: `.lrn-fab` 1438-1540, `.payai-floating-pill` 1482-1540,
both clear of the column at 1580, and both back at bottom-right on Mission
Control in the same session.

A fixed child does not inherit its fixed parent's offsets, and "the rule
applied" is not the same claim as "the thing moved".
