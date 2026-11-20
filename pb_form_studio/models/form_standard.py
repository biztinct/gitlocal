# -*- coding: utf-8 -*-
"""R23 (FS-7) — the administrator hides and renames STANDARD fields.

Owner ruling R23 (2026-11-20): on the employee and the contract, a standard
field can be switched off ("Hidden for everyone" or "Hidden for these
Countries of Work") and get its own label per language. Nothing moves
between tabs; a field's type, required-ness and who may change it stay the
product's.

It is a SCREEN rule only. The field, its values and every reader (pay
formulas, imports, Mapping, Updates sheets, reports, My Payobook) are
untouched. In particular nothing is ever written on `ir.model.fields` (its
label would leak into Mapping, the Updates sheets and exports, and an
upgrade would reset it): the own label lives on the field's settings row
(`pb.form.field.meta.std_labels`) and is applied where a person sees the
field:

* the record's native forms ("Full details", the full contract form): the
  host calls `_pbfs_std_apply_arch` from its model's `_get_view` — the same
  seam TIDY-E uses for its country rules (`pb_employee_form_tidy/models/
  hr_employee.py`) and core uses to relabel currency rates
  (`base/models/res_currency.py`, `_get_view`). It works on the combined
  form, so a field that is gone after an upgrade simply matches nothing: no
  xpath can go dead and break the page. Every change clears the screen-design
  cache (`templates`), which every worker follows;
* the side panels, the Company details grids, the table columns and their
  Excel headings: through `_pbfs_std_rules(model)`, one place.

The LOCKED list (`_pbfs_standard_locked`, one hook) names every standard
field a payslip, a bank file, a statutory file, an approval or an access
rule reads, and every field that must be filled in to save the record: those
can never be hidden (their label can still change, except name, company and
Country of Work). A field that becomes locked after it was hidden is shown
again by every screen at once (the rule is kept but not applied, and the
Form builder says so).
"""
import logging

from lxml import etree

from odoo import api, models, tools
from odoo.exceptions import UserError

from .ir_model_fields import PREFIX

_logger = logging.getLogger(__name__)

#: Context key: the form exactly as the modules draw it, before any R23 rule
#: (the Form builder lists the fields from it; hosts' `_get_view` honours it).
STD_RAW = 'pbfs_std_raw'
#: The keys `update_standard` accepts besides the My Payobook ticks.
STD_KEYS = ('std_hidden', 'std_country_ids', 'std_labels')
#: Kinds of box never offered: pictures, files and free property bags.
STD_SKIP_TTYPES = ('binary', 'properties', 'properties_definition', 'json', 'reference',
                   'many2one_reference')
MAX_STD_LABEL = 60


def _static_hidden(node):
    return (node.get('invisible') or '').strip() in ('1', 'True', 'true')


def _truthy(expr):
    expr = (expr or '').strip()
    return bool(expr) and expr not in ('0', 'False', 'false')


def _or(old, new):
    """`invisible` = hidden if either rule says hidden (TIDY-E's own helper)."""
    old = (old or '').strip()
    if not old or old in ('0', 'False', 'false'):
        return new
    if old in ('1', 'True', 'true'):
        return old
    if new in ('1', 'True'):
        return new
    return '(%s) or (%s)' % (old, new)


class PbFormStudioStandard(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ================================================================ hooks
    @api.model
    def _pbfs_standard_locked(self, model):
        """`{field name: {'reason': text, 'label': bool}}` — standard fields
        that can NEVER be hidden; `label` True = their label is locked too.
        ONE hook: hosts extend it with `super()` (pay, bank, statutory,
        approval and access readers). Here: every field that must be filled
        in to save the record (the model's own rule and the form's)."""
        _ = self.env._
        out = {}
        if model not in self.env:
            return out
        reason = _('It must be filled in to save the record, so it always stays on screen.')
        for name, field in self.env[model]._fields.items():
            if field.required and not name.startswith(PREFIX):
                out[name] = {'reason': reason, 'label': False}
        for row in self._pbfs_std_scan(model):
            if row[4]:                      # required on the form itself
                out.setdefault(row[0], {'reason': reason, 'label': False})
        return out

    @api.model
    def _pbfs_std_panel_boxes(self, model):
        """`[(field name, label as the panel shows it, panel title)]` — fields
        a host's side panel shows that its full form may not. Hosts extend."""
        return []

    @api.model
    def _pbfs_std_exclude(self, model):
        """Names never offered (status widgets, helpers drawn as boxes)."""
        return set()

    @api.model
    def _pbfs_std_builtin_rule(self, model, name):
        """The product's own country rule of a box: None, 'remove' (never on
        screen) or an ISO code (shown only where Country of Work is that
        country). Hosts extend (TIDY-E's table on the employee)."""
        return None

    # ============================================================= catalogue
    @api.model
    def _pbfs_std_views(self, model):
        out = []
        for host in self._pbfs_hosts().values():
            if host['model'] == model and not host.get('dev'):
                for xmlid in host.get('native_views') or []:
                    if xmlid not in out:
                        out.append(xmlid)
        return out

    @api.model
    @tools.ormcache('model', 'self.env.lang or "en_US"', cache='templates')
    def _pbfs_std_scan(self, model):
        """The boxes of the record's native forms, in screen order, as the
        modules draw them (no R23 rule), in the reader's language:
        `((name, label, tab, tab order, required on the form), …)`.

        Cached with the screen designs (`templates`): any view change and any
        R23 change clears it. A tuple, never mutated by a caller."""
        if model not in self.env:
            return ()
        Model = self.env[model].sudo().with_context(**{STD_RAW: True})
        rows, seen = [], set()
        _ = self.env._
        top, below = _('Top of the page'), _('Below the tabs')
        for xmlid in self._pbfs_std_views(model):
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if not view or view._name != 'ir.ui.view':
                continue
            try:
                arch, _view = Model._get_view(view.id, 'form')
            except Exception:                           # noqa: BLE001
                _logger.info('Form builder: the form %s could not be read', xmlid,
                             exc_info=True)
                continue
            labels = {}
            for lab in arch.iter('label'):
                if lab.get('for') and lab.get('string') and lab.get('for') not in labels:
                    labels[lab.get('for')] = lab.get('string')
            tabs = []

            def walk(node, tab, after_tabs):
                for child in node:
                    tag = child.tag if isinstance(child.tag, str) else ''
                    if not tag or tag == 'button':
                        continue
                    if tag == 'notebook':
                        walk(child, tab, after_tabs)
                        after_tabs[0] = True
                        continue
                    if tag == 'page':
                        if _static_hidden(child):
                            continue
                        title = child.get('string') or ''
                        if title not in tabs:
                            tabs.append(title)
                        walk(child, title, after_tabs)
                        continue
                    if tag == 'field':
                        name = child.get('name')
                        if name and name not in seen and not _static_hidden(child) \
                                and name in Model._fields:
                            seen.add(name)
                            where = tab if tab is not None else (below if after_tabs[0] else top)
                            rows.append((name, child.get('string') or labels.get(name) or '',
                                         where, _truthy(child.get('required'))))
                        continue            # a field's own sub-view is another model
                    if _static_hidden(child):
                        continue
                    walk(child, tab, after_tabs)

            walk(arch, None, [False])
        order = {}
        out = []
        for name, label, tab, required in rows:
            order.setdefault(tab, len(order))
            field = Model._fields[name]
            if not label:
                label = field.get_description(self.env, ['string']).get('string') or name
            out.append((name, label, tab, order[tab], required))
        return tuple(out)

    @api.model
    def _pbfs_std_catalogue(self, model):
        """`{name: {name, label, tab, order, seq}}` — every standard field a
        person can meet on this record type's screens, under its on-screen
        label in the reader's language, grouped by the tab it sits on."""
        if model not in self.env:
            return {}
        Model = self.env[model]
        skip = self._pbfs_std_exclude(model)
        out = {}

        def ok(name):
            field = Model._fields.get(name)
            return (field is not None and not name.startswith(PREFIX) and name not in skip
                    and field.type not in STD_SKIP_TTYPES and name not in out
                    and self._pbfs_std_builtin_rule(model, name) != 'remove')

        scan = self._pbfs_std_scan(model)
        last = max([r[3] for r in scan] or [0])
        for name, label, tab, order, _req in scan:
            if ok(name):
                out[name] = {'name': name, 'label': label, 'tab': tab, 'order': order,
                             'seq': len(out)}
        panel_order = {}
        for name, label, title in self._pbfs_std_panel_boxes(model):
            if ok(name):
                panel_order.setdefault(title, last + 1 + len(panel_order))
                out[name] = {'name': name, 'label': str(label), 'tab': str(title),
                             'order': panel_order[title], 'seq': len(out)}
        other = self.env._('Other fields')
        for host in self._pbfs_hosts().values():
            if host['model'] != model or host.get('dev'):
                continue
            for name in self._pbfs_std_names(host):
                if ok(name):
                    out[name] = {'name': name, 'tab': other, 'order': last + 99,
                                 'seq': len(out),
                                 'label': Model._fields[name].get_description(
                                     self.env, ['string']).get('string') or name}
        return out

    @api.model
    def _pbfs_std_is_box(self, model, name):
        return name in self._pbfs_std_catalogue(model)

    # ================================================================ rules
    @api.model
    def _pbfs_std_metas(self, model):
        return {n: m for n, m in self._pbfs_meta(model).items()
                if not m.custom and (m.std_hidden or m.std_country_ids or m.std_labels)}

    @api.model
    def _pbfs_std_label_of(self, meta, lang=None):
        labels = (meta.std_labels or {}) if meta else {}
        if not isinstance(labels, dict):
            return None
        text = labels.get(lang or self.env.lang or 'en_US')
        return text.strip() if isinstance(text, str) and text.strip() else None

    @api.model
    def _pbfs_std_rules(self, model):
        """THE rules every screen applies, in the reader's language:
        `{field name: {'all': bool, 'countries': [res.country ids],
        'label': own label or None}}`. Locked fields never come back hidden
        (a rule saved before the field became locked is not applied)."""
        metas = self._pbfs_std_metas(model)
        if not metas:
            return {}
        locked = self._pbfs_standard_locked(model)
        out = {}
        for name, meta in metas.items():
            if name not in self.env[model]._fields:
                continue
            hide_ok = name not in locked
            rule = {'all': bool(meta.std_hidden) and hide_ok,
                    'countries': meta.std_country_ids.ids if hide_ok else [],
                    'label': self._pbfs_std_label_of(meta)}
            if rule['all'] or rule['countries'] or rule['label']:
                out[name] = rule
        return out

    @api.model
    def _pbfs_std_hidden(self, rule, country_id):
        """Is a box with `rule` hidden for a record of `country_id`?"""
        if not rule:
            return False
        if rule.get('all'):
            return True
        return bool(country_id) and country_id in (rule.get('countries') or [])

    @api.model
    def _pbfs_std_apply_arch(self, arch, model, country_field=None):
        """Apply the rules of `model` to a combined form `arch` (in place):
        own label on the field and on its `<label for>`, `invisible` joined
        with the product's own rule ("hidden if either says hidden"). A field
        inside another field (a list's own columns) is another record type
        and is never touched. A box that is not on the form matches nothing.
        → the names it changed."""
        rules = self._pbfs_std_rules(model)
        if not rules:
            return []
        Model = self.env[model]
        cvf = country_field if country_field and country_field in Model._fields else None
        changed = []
        # Boxes the product's own rule removes from the screen (whatever order
        # the two `_get_view` overrides run in).
        removed = {n for n in Model._fields if self._pbfs_std_builtin_rule(model, n) == 'remove'}

        def expr_of(rule):
            if rule['all']:
                return 'True'
            if rule['countries'] and cvf:
                return '%s in %s' % (cvf, sorted(rule['countries']))
            return None

        def touch(node, name):
            rule = rules.get(name)
            if not rule:
                return None
            if rule['label'] and not _static_hidden(node):
                node.set('string', rule['label'])
            expr = expr_of(rule)
            if expr:
                node.set('invisible', _or(node.get('invisible'), expr))
            changed.append(name)
            return expr

        def walk(node):
            """→ the hide expressions of the boxes under `node`: a set of
            expressions, or None when something there stays shown (an
            untouched box, a button). A group or page whose every box this
            rule hides is hidden with them, so no empty card is left
            (TIDY-E does the same for its own rules)."""
            exprs, open_ = set(), False
            for child in node:
                tag = child.tag if isinstance(child.tag, str) else ''
                if not tag or _static_hidden(child):
                    continue
                if tag == 'field' and child.get('name') in removed:
                    continue        # the product takes it off the screen anyway
                if tag == 'field':
                    expr = touch(child, child.get('name'))   # never into a sub-view
                    if expr:
                        exprs.add(expr)
                    else:
                        open_ = True
                    continue
                if tag == 'label' and child.get('for'):
                    touch(child, child.get('for'))
                    continue
                if tag in ('button', 'widget'):
                    open_ = True
                    continue
                sub = walk(child)
                if sub is None:
                    open_ = True
                else:
                    exprs |= sub
            result = None if open_ or not exprs else exprs
            if result and node.tag in ('group', 'page'):
                inner = sorted(e for e in result if e != 'True')
                both = 'True' if not inner else ' and '.join('(%s)' % e for e in inner)
                node.set('invisible', _or(node.get('invisible'), both))
            return result

        walk(arch)
        return changed

    # ======================================================= administrator
    @api.model
    def _pbfs_std_context(self, model):
        """Everything `_pbfs_std_desc` needs, worked out ONCE per call: the
        catalogue in every language, the locked list, the settings rows."""
        return {
            'cats': {lang: self.with_context(lang=lang)._pbfs_std_catalogue(model)
                     for lang in self._pbfs_langs()},
            'cat': self._pbfs_std_catalogue(model),
            'locked': self._pbfs_standard_locked(model),
            'metas': self._pbfs_meta(model),
            'countries': {},
        }

    @api.model
    def _pbfs_std_all(self, model):
        """`{name: stdbox description}` for every standard field of `model`."""
        ctx = self._pbfs_std_context(model)
        return {name: self._pbfs_std_desc(model, name, ctx) for name in ctx['cat']}

    @api.model
    def _pbfs_std_desc(self, model, name, ctx=None):
        """What the Form builder shows about one standard field's screen rule."""
        ctx = ctx or self._pbfs_std_context(model)
        cat = ctx['cat'].get(name) or {}
        meta = ctx['metas'].get(name)
        lock = ctx['locked'].get(name) or {}
        labels = dict(meta.std_labels or {}) if meta and isinstance(meta.std_labels, dict) else {}
        builtins = {lang: (c.get(name) or {}).get('label') or cat.get('label') or name
                    for lang, c in ctx['cats'].items()}
        rule = self._pbfs_std_builtin_rule(model, name)
        rule_desc = None
        if rule and rule != 'remove':
            if rule not in ctx['countries']:
                country = self.env['res.country'].search([('code', '=', rule)], limit=1)
                ctx['countries'][rule] = {'code': rule, 'country': country.name or rule,
                                          'country_id': country.id or False}
            rule_desc = ctx['countries'][rule]
        hidden = bool(meta and meta.std_hidden)
        cids = meta.std_country_ids if meta else self.env['res.country']
        return {
            'tab': cat.get('tab') or '', 'order': cat.get('order', 0), 'seq': cat.get('seq', 0),
            'builtin': cat.get('label') or name, 'builtins': builtins,
            'labels': {k: v for k, v in labels.items() if isinstance(v, str) and v.strip()},
            'hidden': hidden,
            'countries': [{'id': c.id, 'name': c.name, 'code': c.code} for c in cids],
            'lock': lock.get('reason') or '',
            'label_lock': (lock.get('reason') or '') if lock.get('label') else '',
            'ignored': bool(lock) and (hidden or bool(cids)),
            'rule': rule_desc,
        }

    @api.model
    def _pbfs_std_light(self, Model, name, sd):
        """A standard field that is not placeable, as the Form builder lists
        it (no My Payobook ticks: those are offered on the placeable list)."""
        from .form_studio import TTYPE_KIND
        field = Model._fields[name]
        kind = TTYPE_KIND.get(field.type, 'text')
        own = sd['labels'].get(self.env.lang or 'en_US')
        return {
            'name': name, 'label': own or sd['builtin'], 'help': '', 'type': field.type,
            'kind': kind, 'type_label': self._pbfs_type_label(kind), 'custom': False,
            'std': True, 'locked': False, 'reason': '', 'vis': 'all', 'required': False,
            'list_ok': False, 'formula_ok': False, 'formula_possible': False, 'countries': [],
            'portal': None, 'options': [], 'comodel': False, 'comodel_label': '',
            'placeable': False,
        }

    @api.model
    def _pbfs_set_standard(self, model, name, vals):
        """Validate and store one standard field's screen rule. Refused on the
        server, in screen words, for anything the locked list forbids.
        → list of changed words (empty when nothing changed)."""
        _ = self.env._
        if not any(k in vals for k in STD_KEYS):
            return []
        if name.startswith(PREFIX) or not self._pbfs_std_is_box(model, name):
            raise UserError(_('This field is not offered on this screen.'))
        lock = self._pbfs_standard_locked(model).get(name) or {}
        meta = self._pbfs_ensure_meta(model, name)
        old_hidden, old_cids = bool(meta.std_hidden), set(meta.std_country_ids.ids)
        hidden = bool(vals['std_hidden']) if 'std_hidden' in vals else old_hidden
        cids = set(self._pbfs_country_ids(vals['std_country_ids'])) \
            if 'std_country_ids' in vals else set(old_cids)
        if hidden:
            cids = set()            # hidden for everyone: no country list to keep
        changes = []
        new_vals = {}
        if (hidden, cids) != (old_hidden, old_cids):
            # A locked field may only ever be shown more (a rule saved before
            # it became locked can be narrowed or cleared), never hidden more.
            more = False if old_hidden else (hidden or bool(cids - old_cids))
            if lock and more:
                raise UserError(_('%s It cannot be hidden.', lock['reason']))
            new_vals.update(std_hidden=hidden, std_country_ids=[(6, 0, sorted(cids))])
            if hidden:
                changes.append(_('hidden for everyone'))
            elif cids:
                names = ', '.join(self.env['res.country'].browse(sorted(cids)).mapped('name'))
                changes.append(_('hidden in %s', names))
            else:
                changes.append(_('shown again'))
        if 'std_labels' in vals:
            labels = {}
            langs = self._pbfs_langs()
            for lang, text in (vals['std_labels'] or {}).items():
                text = (text or '').strip() if isinstance(text, str) else ''
                if not text or lang not in langs:
                    continue
                if len(text) > MAX_STD_LABEL:
                    raise UserError(_('A field name can be at most %s characters.', MAX_STD_LABEL))
                labels[lang] = text
            old = {k: v for k, v in (meta.std_labels or {}).items()} \
                if isinstance(meta.std_labels, dict) else {}
            if labels != old:
                if labels and lock.get('label'):
                    raise UserError(_('%s Its name cannot be changed either.', lock['reason']))
                new_vals['std_labels'] = labels or False
                changes.append(_('own label') if labels else _('built-in label put back'))
        if new_vals:
            meta.write(new_vals)
        return changes

    @api.model
    def update_standard(self, model, name, vals):
        """Administrator: a standard field's My Payobook ticks (R14) and its
        screen rule (R23: `std_hidden`, `std_country_ids`, `std_labels`
        {lang: text}, empty = the built-in label). One history line. Every
        screen follows at once (the screen-design cache is cleared, which
        every worker follows) — no Publish needed from the Field library."""
        self._pbfs_check_admin()
        _ = self.env._
        if model not in self._pbfs_host_models() or name not in self.env[model]._fields:
            raise UserError(_('This field is not offered on this screen.'))
        vals = dict(vals or {})
        before = self._pbfs_std_screen_label(model, name)
        changes = []
        portal = {k: v for k, v in vals.items() if k in ('portal_show', 'portal_edit', 'portal_mode')}
        if portal:
            changes += self._pbfs_set_portal(model, name, portal)
        std = {k: vals[k] for k in STD_KEYS if k in vals}
        publishing = self.env.context.get('pbfs_publishing')
        std_changes = self._pbfs_set_standard(model, name, std) if std else []
        changes += std_changes
        if changes:
            self._pbfs_audit('update_field', None, model, name,
                             _('Changed %(label)s: %(what)s', label=before,
                               what=', '.join(str(c) for c in changes)),
                             detail={'standard': True, 'vals': {
                                 k: v for k, v in vals.items()
                                 if k in STD_KEYS or k in portal}})
        if publishing:
            # Publish clears the screen designs and tells everybody ONCE,
            # after the last field; nobody reads the answer.
            return {}
        if std_changes:
            self.env.registry.clear_cache('templates')
            self._pbfs_std_notify(model)
        desc = self._pbfs_describe(self.env[model], name)
        if self._pbfs_std_is_box(model, name):
            desc['stdbox'] = self._pbfs_std_desc(model, name)
        return desc

    @api.model
    def _pbfs_std_screen_label(self, model, name):
        """The label a person sees now (own label, else the on-screen one)."""
        meta = self._pbfs_meta(model, [name]).get(name)
        own = self._pbfs_std_label_of(meta)
        if own:
            return own
        cat = self._pbfs_std_catalogue(model).get(name)
        if cat:
            return cat['label']
        field = self.env[model]._fields.get(name)
        return (field.get_description(self.env, ['string']).get('string') if field else name) or name

    @api.model
    def _pbfs_std_notify(self, model):
        """A change made outside Publish (Field library) reaches every open
        screen too (FSD-1)."""
        for key, host in self._pbfs_hosts().items():
            if host['model'] == model and not host.get('dev'):
                layout = self._pbfs_layout(key)
                self._pbfs_notify(key, layout.version if layout else 0)

    @api.model
    def _pbfs_std_sweep(self):
        """Drop the screen rule of a standard field that no longer exists
        (an upgrade removed it), with a history line. The settings row is
        removed by the database with its field; this catches a row left on a
        field the registry no longer has. → number of rows dropped."""
        dropped = 0
        Meta = self.env['pb.form.field.meta'].sudo()
        for meta in Meta.search([('custom', '=', False)]):
            if not (meta.std_hidden or meta.std_country_ids or meta.std_labels):
                continue
            model, name = meta.model, meta.name
            if model in self.env and name in self.env[model]._fields:
                continue
            self._pbfs_audit('update_field', None, model, name,
                             self.env._('%s no longer exists: its screen rule was removed.', name))
            meta.write({'std_hidden': False, 'std_country_ids': [(5,)], 'std_labels': False})
            dropped += 1
        if dropped:
            self.env.registry.clear_cache('templates')
        return dropped
