# FILTER programme — conventions and gotcha ledger

Every FILTER handover references this file. Read it before writing a line.
Add to it whenever a new gotcha is hit (F-numbered, newest last).

Programme: one shared filter panel ("B+", owner choice 2026-10-30) on every
list / kanban / card screen in Payobook. Pilot = People › Employees, LIVE on
all four databases 2026-10-30 (commits `b974e79a6` POC, `600b9db5c` feature).
Design source: `docs/design/filter-patterns-poc.html` (tab "B+").

---

## 1. Binding rules (owner, standing — restate in every handover)

- **White-label.** The word "Odoo" never appears in anything a user can see:
  labels, tooltips, placeholders, empty states, toasts, menu/action names,
  field `string=`/`help=`, selection labels, reports, exports, emails, `.po`
  msgstr. Technical identifiers (`from odoo import`, module/xml ids, log
  lines, comments, docs) keep the real name.
- **Design bar (verbatim):** "extreme WOW, intuitive, out-of-this-world
  experience, best in class." A hero moment; zero dead-ends (empty, loading,
  error, partial, huge are all designed, every failure names its reason and
  next step); plain language over code vocabulary; motion with purpose;
  keyboard + bulk ergonomics where rows are involved; measured against the
  best SaaS tool in the category, not stock screens. Lucide icons only, never
  emoji; locked indigo palette (`#5A4BB0`), no gradients.
- **Plain English** in every user-visible string and in reports to the owner.
- **Learn follows the screen.** Any `data-coach` anchor, lesson, tour or
  practice replica (`pb_learn/static/src/engine/screens.js`,
  `pb_learn/static/src/anchors.json`, `pb_learn/static/content/learn_content.json`)
  that describes a screen you change is updated in the same work; bump
  `pb_learn`. If nothing in Learn is affected, say so in the report.
- **Browser validation is mandatory.** Never call a screen done without
  Chrome MCP on payobook.com: click through, and read the console for errors.
- **Commit per feature**, explicit paths only (never `git add .`/`-A`; never
  `__pycache__`/`.pyc`/`.DS_Store`), message = problem → fix → decisions, end
  with the Co-Authored-By line from the session reminder. Branch `19.1`.
  Scan the diff for passwords/keys before committing (the repo is public).
  The coordinator pushes.

## 2. Deploy contract (live server `Payobook19v2`)

- ONE addons dir: `/odoo/odoo-server/addons`. Per-module scoped
  `sudo rsync -a --delete --chown=odoo:odoo /tmp/<stage>/<m>/ /odoo/odoo-server/addons/<m>/`.
  NEVER `--delete` with the addons root as destination.
- Databases: `payobook`, `payobook_template`, `rize`, `p0clone` — these four
  only. **Never `abm`.**
- Before any deploy: `cat /opt/deploy-notes.md`; if someone's START has no
  DONE, wait. Append `YYYY-MM-DD HH:MM UTC | <who> | START | modules | DBs | downtime | notes`
  with `sudo tee -a`, then a DONE/FAILED line after. Run the steps under
  `sudo flock -w 600 /tmp/payobook-studio-deploy.lock bash <script>`
  (the lock file is root-owned; a plain `exec 9>` fails).
- `-u` re-activates scheduled jobs (21 came back on in rehearsal). Always
  snapshot `select id from ir_cron where active` per DB before, and restore
  `update ir_cron set active = (id in (...))` after. Current counts on
  2026-10-30: p0clone 31, payobook_template 28, rize 74, payobook 42.
- Python/XML/manifest change ⇒ stop service, `-u` each DB one at a time
  (stop at the first failure, keep the old module trees for rollback),
  restore crons, purge assets, start. JS/SCSS/XML-template-only change ⇒
  "looks-only": rsync + per DB
  `delete from ir_attachment where url like '/web/assets/%'`,
  `update ir_config_parameter set value='<tag>' where key='web.assets.version'`,
  `insert into orm_signaling_assets default values` — no restart.
- A new dependency on `pb_filter_kit` from a module ⇒ every DB where that
  module is installed must get the `-u` in the same deploy (otherwise its
  Python `_inherit = ['pb.filter.mixin']` would not resolve and its JS import
  would fail the bundle). `pb_filter_kit` is already installed everywhere.
- Rehearse anything with Python/data changes on a throwaway copy first:
  `pg_dump -Fc rize` → `createdb pbf_rehearse` → `pg_restore`, then
  immediately `update ir_cron set active=false; update ir_mail_server set active=false`
  (the live service's cron threads DO connect to it), run with
  `--addons-path=/tmp/<stage>,/odoo/odoo-server/addons`, and `dropdb --force`
  it the moment you are done (every DB is reachable at `<db>.payobook.com`).
- Files written by `sudo -u odoo` in `/tmp` can only be removed with `sudo rm`.
- After a restart, warm with one `curl https://<host>/web/login` per site.
- Verify: per-module tree hash identical stage vs live (skip `__pycache__`,
  `*.pyc`, `.DS_Store`); `ir_module_module.latest_version` matches the
  manifest in all four DBs; log has no new ERROR lines.

## 3. How a screen adopts the panel (the recipe)

Reference implementation: `pb_people` (model `pb/people`, JS `people.js`,
template `people.xml`).

Server (the screen's data model, usually an AbstractModel `pb.<x>`):
```python
class PbX(models.AbstractModel):
    _name = 'pb.x'
    _inherit = ['pb.filter.mixin']
    def _pbf_model(self): return 'hr.contract'          # what the list shows
    def _pbf_screen(self): return 'contracts'           # saved-views key, unique
    def _pbf_base_domain(self): return [...]            # the list before filtering
    def _pbf_search_fields(self): return ['name', 'employee_id.name', ...]
    def _pbf_sorts(self): return [{'key','label','order'}, ...]   # first = default
    def _pbf_layout_extra(self): return {'currency': ...}         # optional
    def _pbf_spec(self): return [ {section}, ... ]                # panel order
    def _pbf_builtin_views(self): return [ {'key','label','icon','filters'}, ... ]
    @api.model
    def get_x_page(self, filters=None, search=None, sort=None, offset=0, limit=60):
        domain = self.pbf_domain(filters or {}, search)
        recs = self.env[...].search(domain, order=self.pbf_order(sort), offset=offset, limit=limit)
        return {'rows': [...], 'total': self.env[...].search_count(domain)}
```
Section dict: `key`, `label` (`_()`), `icon` (pb_import_kit `IC` name or kit
extras `panelLeft pin arrowUpDown usersRound bookmark`), `group`
(`people|work|contract|pay|dates|other`), `type`, `pinned` (max 3 per
screen), `none_label`, `help`; per type:
- `many2one` / `selection` / `char`: `path` (m2o hops allowed:
  `contract_id.struct_id`; the LAST hop must be a stored field — see F2).
- `choice`: `options=[{value,label,tone,domain}]`, `requires=[paths]`
  (dropped if a path is missing). Tones: green amber rose blue slate.
- `date`: `path`, `presets='past'|'future'`, `none_label`.
- `number`: `path`, `unit='money'` (uses `extra.currency`).
Sections with < 2 values on a database hide themselves; active ones always show.

Client:
```js
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
static components = { PbFilterLayout };
this.kit = useFilterKit({ model: "pb.x", noun: _t("contracts"), onChange: () => this.loadPage() });
async loadPage({ more = false } = {}) {
    const q = this.kit.query;               // {filters, search, sort, seq}
    const d = await this.orm.call("pb.x", "get_x_page", [], {...q, offset, limit});
    if (!this.kit.isCurrent(q.seq)) return; // drop stale replies
    ...
}
```
```xml
<PbFilterLayout kit="kit" coach="'xx-filters'" searchPlaceholder="'Search …'">
    <t t-set-slot="toolbar">…optional extra buttons…</t>
    …the list / board / cards…
</PbFilterLayout>
```
- Figures on a QuietGlance line that used to filter now call
  `kit.toggleFilters({...})`; lit = `kit.isExactly({...})`.
- Old chip rows (`pbim-fchip`, date chips, status buttons) are removed —
  their meaning moves into sections or built-in views.
- Kanban/board screens: the panel filters the cards; the columns stay. Put
  per-column counts from the server if the board caps rows.
- Manifest: add `'pb_filter_kit'` to `depends`, bump the version.
- Translations: after deploy, `odoo-bin i18n export -c /etc/odoo-server.conf
  -d p0clone -l vi_VN -o /tmp/x.po <modules>` (service may stay up), merge
  Vietnamese into `<module>/i18n/vi_VN.po` keeping old entries, run the PO
  gate (§5), deploy (code translations need only rsync + restart).

### 3a. Kit options added 2026-10-31 (pb_filter_kit 19.0.1.1.0)

- **`choice` options may carry `domain_method`** instead of `domain`: the
  name of a method on the screen model returning a domain at request time
  (`[('id', 'in', ids)]` for facts only Python knows: pay-feed status,
  "waiting on me", settlement found by employee). Must answer in well under
  300 ms on payobook (4,575 people); otherwise keep the fact as a glance
  figure and say so in the report.
- **Literal `domain`s may use one2many/many2many paths and `any`**
  (`[('task_ids', 'any', [('state','=','open'), ('due_date','<', today)])]`)
  — only `requires` and `path` go through `_pbf_resolve`, which walks
  many2one hops. The LAST hop of a `path` may be a many2many (listed as
  `type: 'many2one'`); intermediate hops must be many2one.
- **"Mine" = a choice whose domain is built in `_pbf_spec` with
  `self.env.uid`** (the spec is computed per request).
- **Counts under sudo:** override `_pbf_records()` to return
  `self.env['x'].sudo()` ONLY where the screen already reads under sudo, and
  carry the same company/scope restriction in `_pbf_base_domain`.
- **Several record types under one action:** one facade model; the JS passes
  `useFilterKit({ model, ctx: { kind } })`; every call then carries
  `context.pbf_ctx`; hooks read `self._pbf_ctx().get('kind')` to pick the
  model, spec and `_pbf_screen()` (`'<screen>:<kind>'` so saved views stay
  apart). On a tab switch call `await kit.reconfigure({ ctx: { kind } })`.
- **Filters from a door:** `useFilterKit({ ..., initial: { filters, search, viewKey } })`
  wins over the URL and the tab memory on first load; later
  `kit.setFilters(filters, { search })`. Figures on a numbers line still use
  `kit.toggleFilters(f)` / `kit.isExactly(f)`.
- **Refusal screens:** override `pbf_layout` to return `{'refused': msg}`
  when the screen's own gate refuses; the kit renders nothing
  (`kit.failed`, `kit.refusal`) and the screen shows its usual refusal.
- **Search folding:** the kit search is `ilike`; a screen with a folded
  Python search (Vendors "Bùi") may override `_pbf_search_domain` to add
  `unaccent`-style alternatives; otherwise note the regression.

### 3b. Rulings for the rollout (coordinator, 2026-10-31)

- **R1** Lane / step / tab counts FOLLOW the filters (the kit's counts). This
  supersedes the Pay Run ruling W82 ("lane counts stay un-narrowed").
- **R2** No new stored fields and no migrations in this programme; a fact
  that is only Python goes through `domain_method`, or stays a glance figure
  with a debt note in the report.
- **R3** Catalogues under ~30 rows still convert for consistency and saved
  views (Structures, Connectors), pure settings pages do not.
- **R4** Where other code reads a screen's old `get_board` payload (Pay Run
  "Right now", composer connectors, Learn facades), the old method keeps
  returning it; the list the panel shows comes from the new paged method.
- **R5** Rows that are not records (attendance exceptions engine, workbook
  grids, the statutory tax union) are out of scope: convert the record-backed
  half, leave the rest as it is, and name it as debt.
- **R6** A screen's bulk actions act on the kit's filtered set: the page the
  user sees, or "everything matching" through one server call that takes
  the kit's `filters`/`search` and runs `pbf_domain` — never a stale array.
- **R7** Default pinned sections = the three questions asked most on that
  screen; everything else under "More filters".
- **R8** Access › People (INVENTORY #34) is NOT in any Opus wave
  (security-sensitive visibility rule); the coordinator decides later.

### 3c. Preview workflow (builders never deploy to live)

A second Odoo on the box serves a throwaway copy of payobook from a
staging addons dir: `/odoo/ops/pbf_preview.sh` (source `tools/pbf_preview.sh`).
Builders take turns on it:

```
ssh Payobook19v2 'sudo /odoo/ops/pbf_preview.sh hold w3'          # waits for the previous holder
rsync -az --delete --exclude=__pycache__ --exclude='*.pyc' --exclude=.DS_Store <modules> Payobook19v2:/tmp/pbf_stage_w3/
ssh Payobook19v2 'chmod -R a+rX /tmp/pbf_stage_w3; sudo /odoo/ops/pbf_preview.sh sync /tmp/pbf_stage_w3 pb_hiring,pb_learn; sudo /odoo/ops/pbf_preview.sh upgrade pb_hiring,pb_learn'
ssh -f -N -L 8170:127.0.0.1:8170 Payobook19v2 2>/dev/null || true   # tunnel (ok if already up)
# Chrome MCP → http://localhost:8170/web/login ; user + password are the two lines of
#   ssh Payobook19v2 'cat /tmp/pbf_preview/.login'   (a throwaway copy on localhost — never paste them in a report)
# then /bizapp/action-<tag> ; after a JS/XML change: sync + `pbf_preview.sh restart`
ssh Payobook19v2 'sudo /odoo/ops/pbf_preview.sh release w3'
```
`pbf_preview.sh upgrade` is the rehearsal (EXIT code + error count in its
output; full log `/tmp/pbf_preview/upgrade.log`). Hold the preview once per
wave for the whole test-and-fix pass; build everything first. Export
translations from it while you hold it:
`odoo-bin i18n export -c /etc/odoo-server.conf --addons-path=/tmp/pbf_preview/addons,/odoo/odoo-server/addons -d pbf_preview -l vi_VN -o /tmp/<wave>.po <modules>`
(run as odoo, service may stay up). The live deploy of a merged batch is the
coordinator's (`filter_deploy.sh full`).

## 4. Gotchas (F-ledger)

- **F1** A model field named `search` hides `Model.search()` → `'bool' object
  is not callable`. (`pb.filter.view` uses `search_text`.)
- **F2** Group-by on a path whose last hop is non-stored fails
  (`res.company.country_id`); use a stored equivalent
  (`company_id.partner_id.country_id`). The kit hides the section and logs
  `Filter section … hidden:` at INFO — grep for it after a deploy.
- **F3** `.pbim.pbim-page` is `overflow:auto` → kills `position:sticky`.
  The kit's CSS overrides it on pages that contain `.pbf`. Other page roots
  with overflow set need the same treatment.
- **F4** In OWL templates an arrow must call methods through `this.`
  (`() => this.pick(x)`); a bare `pick(x)` loses `this` and crashes.
- **F5** Grid rows holding long text need `grid-template-columns: minmax(0,1fr)`
  or the text pushes the count out of the panel.
- **F6** `scrollIntoView` scrolls every ancestor, including the page; scroll
  the panel box itself (`box.scrollTo`).
- **F7** The Chrome test robot types faster than focus lands: wait ~1 s after
  opening a popover before typing, or the app's barcode listener throws
  `handleBarcode … getAttribute` (platform, not ours).
- **F8** First load after an asset purge compiles the bundle: give the page
  10–15 s before judging a blank screen. A blank screenshot with content in
  `document.body.innerText` is a paint delay, not a bug.
- **F9** `-u pb_learn` / `-u pb_people` re-activate cron jobs → snapshot and
  restore (§2).
- **F10** The live service's cron threads connect to any database on the
  cluster, including rehearsal copies → switch crons and mail off on the copy
  right after restore; `dropdb --force` to remove it.
- **F11** `.po` entries need `#. module: <m>` FIRST, then
  `#. odoo-python`/`#. odoo-javascript`, and `#: code:addons/<m>/<path>:0`.
  A missing module line crashes the whole upgrade.
- **F12** In Chrome, the test browser is signed in as Mitchell Admin on
  payobook.com; use that session (never type a password). Saved views you
  create while testing must be deleted again; clear `pbf:*` keys from
  localStorage/sessionStorage at the end so the owner sees defaults.
- **F13** (w4) The preview Odoo is started by `pbf_preview.sh` with `nohup … &`
  inside YOUR ssh session; when a long `upgrade`/`restart` call is moved to
  the background and its ssh session ends, the preview dies with it
  (`status` shows `pid=` empty, http 000). Run them detached and poll:
  `ssh Payobook19v2 'sudo setsid /odoo/ops/pbf_preview.sh upgrade <mods> </dev/null >/tmp/<w>_up.out 2>&1 &'`
  then `grep -E "upgrade EXIT|preview http" /tmp/<w>_up.out`.
- **F14** (w4) `odoo-bin i18n export`: `--addons-path` goes BEFORE `i18n export`,
  and `-c/-d/-l/-o` AFTER it (`odoo-bin --addons-path=… i18n export -c /etc/odoo-server.conf -d pbf_preview -l vi_VN -o /tmp/x.po <m>`);
  `-c` before the sub-command makes it a server run (`no such option: -l`).
- **F15** (w4) A module's stale `i18n/<module>.pot` silently drops translations:
  the server's PoFileReader merges the .pot into the .po and every entry the
  .pot does not know becomes obsolete. pb_approval_config's .pot dated
  2026-09-12 hid every term added since (refreshed in w4). Before shipping
  terms, compare `grep -c ^msgid` of the .pot with the code, or regenerate it
  with `-l pot`.
- **F16** (w4) A code term used from Python needs BOTH `#. odoo-python` AND a
  `#: code:addons/<m>/<file>.py:0` reference in its entry; the flag alone does
  not load (rows are typed by reference). When a term already translated for
  JS starts being used in Python, replace the entry's comment/reference block
  with the export's.
- **F17** (w4) The Learn anchor test (`pb_learn/tests/test_anchor_registry.py`
  test_01) greps the declared file for the literal `data-coach="<key>"`; a key
  given through `PbFilterLayout coach="'<key>'"` is not literal. Keep the
  literal in an XML comment next to the layout (`pe-filters` currently fails).
- **F18** (w4) Claude-in-Chrome may be stuck at a ~567 px window that
  `resize_window` cannot change (kit goes narrow ≤ 900 px). Use the
  chrome-devtools MCP instead: `new_page` with an `isolatedContext`,
  `emulate viewport 1440x900x1`, sign in with a `fetch('/web/session/authenticate')`.
  The webclient refuses to be framed, so an iframe harness does not work.
- **F19** (w4) Parallel builders share the session scratchpad: a file named
  `merge_po.py` was overwritten by another wave mid-run. Prefix every scratch
  file with the wave id.
- **F20** (w4) Python facts a choice section needs many times per request
  (`domain_method`, a folded search) are re-evaluated once per count (~12 per
  `pbf_counts`). Memoise them on `self.env.cr.cache[(key, uid, …)]` — one
  request, one cursor.

## 5. PO gate (run on the server before shipping translations)
```python
import sys, logging; logging.disable(logging.CRITICAL)
sys.path.insert(0, "/odoo/odoo-server")
from odoo.tools.translate import PoFileReader
for po in [...]:
    with open(po, "rb") as f:
        for _ in PoFileReader(f): pass
```
