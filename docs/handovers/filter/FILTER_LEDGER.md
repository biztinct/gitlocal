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

## 5. PO gate (run on the server before shipping translations)
```python
import sys, logging; logging.disable(logging.CRITICAL)
sys.path.insert(0, "/odoo/odoo-server")
from odoo.tools.translate import PoFileReader
for po in [...]:
    with open(po, "rb") as f:
        for _ in PoFileReader(f): pass
```
