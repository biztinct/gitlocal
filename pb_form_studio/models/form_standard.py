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

from odoo import SUPERUSER_ID, api, models, tools
from odoo.exceptions import UserError

from .ir_model_fields import PREFIX

_logger = logging.getLogger(__name__)

#: Context key: the form exactly as the modules draw it, before any R23 rule
#: (the Form builder lists the fields from it; hosts' `_get_view` honours it).
#: R31: the product's "taken off the screens" boxes are drawn too (TIDY-E
#: honours it), so the Form builder knows their label and their tab.
STD_RAW = 'pbfs_std_raw'
#: R31 (FS-15) — "Shown for": `std_show` 'all' | 'only' | 'none' | 'builtin'
#: (= put the product's built-in setting back), the countries of 'only', and
#: whether people with no Country of Work see it too.
SHOW_KEYS = ('std_show', 'std_show_country_ids', 'std_show_unset')
#: The keys `update_standard` accepts besides the My Payobook ticks. The FS-7
#: pair (`std_hidden`, `std_country_ids` = hidden in these countries) is still
#: accepted and translated into "Shown for".
STD_KEYS = ('std_hidden', 'std_country_ids', 'std_labels') + SHOW_KEYS

# R31 — a "Shown for" setting is a tuple (mode, frozenset of res.country ids,
# people with no Country of Work see it). 'all' and 'none' carry no country.
SHOW_ALL = ('all', frozenset(), True)
SHOW_NONE = ('none', frozenset(), False)
#: Settings rows that carry a "Shown for" rule (new or FS-7).
RULE_DOMAIN = ['|', '|', ('std_show', '!=', False), ('std_hidden', '=', True),
               ('std_country_ids', '!=', False)]


def show_only(ids, unset=False):
    """'Only these Countries of Work'; no country and nobody unset = hidden."""
    ids = frozenset(int(i) for i in (ids or ()) if i)
    if not ids and not unset:
        return SHOW_NONE
    return ('only', ids, bool(unset))


def show_union(a, b):
    """Shown wherever either says shown (a locked field's widening)."""
    if a[0] == 'all' or b[0] == 'all':
        return SHOW_ALL
    if a[0] == 'none':
        return b
    if b[0] == 'none':
        return a
    return show_only(a[1] | b[1], a[2] or b[2])


def show_covers(a, b):
    """Does `a` show the field everywhere `b` does?"""
    return show_union(a, b) == a


def show_hides(show, country_id):
    """Is a field with `show` hidden for a record of `country_id`?"""
    if show[0] == 'all':
        return False
    if show[0] == 'none':
        return True
    if not country_id:
        return not show[2]
    return country_id not in show[1]
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

    # ======================================================= really used (FS-10)
    @api.model
    def _pbfs_std_readers(self, model):
        """`[(field name, kind, what)]` — the things on THIS database that
        really read a standard field of `model` today: `kind` 'formula' (a
        pay scheme component bound to it; `what` = the scheme's name) or
        'datafile' (a pay data file column fills it; `what` = the scheme).
        Hosts extend. Never called directly: go through `_pbfs_std_used`."""
        return []

    @api.model
    def _pbfs_std_datafile_readers(self, model):
        """`[(field, 'datafile', scheme)]` — pay data file columns (Mapping)
        that fill a field of `model`, in schemes that are not archived."""
        if 'hr.payslip.import.mapping' not in self.env:
            return []
        Mapping = self.env['hr.payslip.import.mapping'].sudo()
        out = []
        for row in Mapping.search([('target_field_id.model', '=', model),
                                   ('salary_structure_id.active', '=', True)]):
            out.append((row.target_field_id.name, 'datafile',
                        row.salary_structure_id.display_name or ''))
        return out

    @api.model
    @tools.ormcache('model', 'self.env.lang or "en_US"', cache='templates')
    def _pbfs_std_used(self, model):
        """`((field, kind, what), …)` of `_pbfs_std_readers`, cached per
        database with the screen designs: every save of a reader calls
        `_pbfs_std_readers_changed`, which clears that cache (the registry
        tells every worker). A tuple, never mutated."""
        rows = set()
        for name, kind, what in self._pbfs_std_readers(model) or []:
            if name:
                rows.add((name, kind, what or ''))
        return tuple(sorted(rows))

    @api.model
    def _pbfs_std_used_reasons(self, model):
        """`{field: reason}` in the reader's language, naming what uses it:
        "Used by pay formula: <scheme>" / "Filled by pay data file: <scheme>"."""
        _ = self.env._
        by = {}
        for name, kind, what in self._pbfs_std_used(model):
            by.setdefault(name, {}).setdefault(kind, [])
            if what and what not in by[name][kind]:
                by[name][kind].append(what)

        def names(items):
            items = sorted(items)
            if len(items) > 2:
                return _('%(names)s and %(n)s more', names=', '.join(items[:2]), n=len(items) - 2)
            return ', '.join(items)
        out = {}
        for name, kinds in by.items():
            if 'formula' in kinds:
                out[name] = _('Used by pay formula: %s', names(kinds['formula']))
            else:
                out[name] = _('Filled by pay data file: %s', names(kinds.get('datafile') or []))
        return out

    @api.model
    def _pbfs_std_used_things(self, model):
        """`{field: what uses it}` for a sentence: "the pay formula X" /
        "the pay data file of X" (the first one found)."""
        _ = self.env._
        out = {}
        for name, kind, what in self._pbfs_std_used(model):
            if name in out and kind != 'formula':
                continue
            out[name] = (_('the pay formula %s', what) if kind == 'formula'
                         else _('the pay data file of %s', what))
        return out

    @api.model
    def _pbfs_std_readers_changed(self, models=None, thing=''):
        """THE shared helper every reader calls at its save point (a pay
        formula component saved, a pay data file column mapped, a scheme
        archived or restored): forget the cached answer (every worker), then
        show again — with a history line and a one-time notice to the
        administrators — any standard field that was hidden and is now used.
        `thing` names what changed in screen words ("the pay formula X").
        Cheap: one query per reader kind, only when a reader is saved."""
        self.env.registry.clear_cache('templates')
        shown = {}
        Meta = self.env['pb.form.field.meta'].sudo()
        for model in models or self._pbfs_host_models():
            if model not in self.env or not Meta.search_count(
                    [('model', '=', model), ('custom', '=', False)] + RULE_DOMAIN, limit=1):
                continue                # nothing hidden: nothing to show again
            names = self._pbfs_std_unhide_locked(model, '', notice=thing or True)
            if names:
                shown[model] = names
                self._pbfs_std_notify(model)
        return shown

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

    # ========================================================= R31 (FS-15)
    @api.model
    def _pbfs_std_comeback(self, model):
        """`{field: reason}` — boxes the product took off the screens that
        must NOT come back (a live source took their place, or they are
        worked-out figures nobody types). Hosts extend. Every other
        "taken off the screens" box can be shown again."""
        return {}

    @api.model
    def _pbfs_std_propose(self, model, name):
        """The "Shown for" a box gets when the administrator presses Show
        again: all countries here; hosts propose the country it belongs to."""
        return SHOW_ALL

    @api.model
    def _pbfs_countries_in_use(self):
        """`([{id, name, code, n}], people with no Country of Work)` — the
        Countries of Work in use on this site with their number of people,
        most first: the figures of the People list's Country of Work filter.
        Hosts provide them (the People host); none here."""
        return [], 0

    @api.model
    def _pbfs_cow_universe(self):
        """res.country ids of every Country of Work a person can have (the
        choices of the employee's Country of Work box)."""
        field = self.env['hr.employee']._fields.get('payroll_country') \
            if 'hr.employee' in self.env else None
        if not field or field.type != 'selection':
            return frozenset(self.env['res.country'].sudo().search([]).ids)
        codes = [str(k).upper() for k, _l in field._description_selection(self.env) if k]
        return frozenset(self.env['res.country'].sudo().search([('code', 'in', codes)]).ids)

    @api.model
    def _pbfs_std_code_ids(self, codes):
        codes = {str(c).upper() for c in codes or () if c}
        if not codes:
            return {}
        return {(c.code or '').upper(): c.id
                for c in self.env['res.country'].sudo().search([('code', 'in', list(codes))])}

    @api.model
    def _pbfs_std_base(self, model, name, code_ids=None):
        """The product's built-in "Shown for" of a box (R31: the default an
        administrator can change): all countries, none (taken off the
        screens) or only the country of its built-in rule."""
        rule = self._pbfs_std_builtin_rule(model, name)
        if not rule:
            return SHOW_ALL
        if rule == 'remove':
            return SHOW_NONE
        code_ids = code_ids if code_ids is not None else self._pbfs_std_code_ids([rule])
        cid = code_ids.get(str(rule).upper())
        return show_only([cid]) if cid else SHOW_NONE

    @api.model
    def _pbfs_std_override(self, meta, base):
        """The administrator's "Shown for" of a box, or None when the box
        follows its built-in setting. An FS-7 row (hidden for everyone /
        hidden in some countries) reads as exactly what it did: the built-in
        setting minus those countries, people with no Country of Work kept."""
        if not meta:
            return None
        if meta.std_show:
            show = SHOW_ALL if meta.std_show == 'all' else (
                SHOW_NONE if meta.std_show == 'none'
                else show_only(meta.std_show_country_ids.ids, meta.std_show_unset))
        elif meta.std_hidden or meta.std_country_ids:
            show = self._pbfs_std_legacy(base, bool(meta.std_hidden), meta.std_country_ids.ids)
        else:
            return None
        return None if show == base else show

    @api.model
    def _pbfs_std_legacy(self, base, hidden, hidden_ids):
        """FS-7's (hidden for everyone, hidden in these countries) on top of
        the built-in setting, as a "Shown for"."""
        if hidden:
            return SHOW_NONE
        hidden_ids = frozenset(hidden_ids or ())
        if not hidden_ids:
            return base
        if base[0] == 'all':
            return show_only(self._pbfs_cow_universe() - hidden_ids, True)
        if base[0] == 'only':
            return show_only(base[1] - hidden_ids, base[2])
        return SHOW_NONE

    @api.model
    def _pbfs_std_effective(self, model, name, meta, locked=None, code_ids=None):
        """→ (built-in, what the screens apply, override as stored or None).
        A locked box is never shown less than its built-in setting: a
        narrower rule saved before it became locked is widened back."""
        base = self._pbfs_std_base(model, name, code_ids)
        override = self._pbfs_std_override(meta, base)
        if override is None:
            return base, base, None
        locked = locked if locked is not None else self._pbfs_standard_locked(model)
        eff = show_union(base, override) if name in locked else override
        return base, eff, override

    @api.model
    def _pbfs_std_tidy_overrides(self, model):
        """`{field: rule}` for TIDY-E's table (its boxes only): None = shown
        for everyone, 'remove' = hidden for everyone, an ISO code, or a
        frozenset of codes (None in it = people with no Country of Work see
        it too). Read by `pb_employee_form_tidy` in `_get_view`."""
        out = {}
        metas = self._pbfs_std_metas(model)
        if not metas:
            return out
        locked = self._pbfs_standard_locked(model)
        codes = {}
        for name, meta in metas.items():
            if not self._pbfs_std_builtin_rule(model, name):
                continue
            _base, eff, override = self._pbfs_std_effective(model, name, meta, locked)
            if override is None or eff == _base:
                continue
            if eff[0] == 'all':
                out[name] = None
            elif eff[0] == 'none':
                out[name] = 'remove'
            else:
                if not codes:
                    codes = {c.id: (c.code or '').upper()
                             for c in self.env['res.country'].sudo().search([])}
                found = frozenset(codes[i] for i in eff[1] if codes.get(i))
                if len(found) == 1 and not eff[2]:
                    out[name] = next(iter(found))
                else:
                    out[name] = found | ({None} if eff[2] else set())
        return out

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
            # R31: the boxes the product took off the screens are listed too
            # ("Taken off the screens"; most of them can be shown again).
            return (field is not None and not name.startswith(PREFIX) and name not in skip
                    and field.type not in STD_SKIP_TTYPES and name not in out)

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
                if not m.custom and (m.std_show or m.std_hidden or m.std_country_ids
                                     or m.std_labels)}

    @api.model
    def _pbfs_std_label_of(self, meta, lang=None):
        labels = (meta.std_labels or {}) if meta else {}
        if not isinstance(labels, dict):
            return None
        text = labels.get(lang or self.env.lang or 'en_US')
        return text.strip() if isinstance(text, str) and text.strip() else None

    @api.model
    def _pbfs_std_rules(self, model):
        """THE rules every screen applies, in the reader's language, for the
        boxes an administrator changed: `{field name: {'all': hidden for
        everyone, 'only': [res.country ids] or None (shown only there),
        'unset': people with no Country of Work see it, 'show': 'all' |
        'only' | 'none' | None (built-in), 'builtin': the box has a built-in
        country rule (TIDY-E applies the "Shown for" of those on Full
        details), 'label': own label or None}}`. A locked box is never shown
        less than its built-in setting."""
        metas = self._pbfs_std_metas(model)
        if not metas:
            return {}
        locked = self._pbfs_standard_locked(model)
        out = {}
        for name, meta in metas.items():
            if name not in self.env[model]._fields:
                continue
            base, eff, override = self._pbfs_std_effective(model, name, meta, locked)
            changed = override is not None and eff != base
            label = self._pbfs_std_label_of(meta)
            if not changed and not label:
                continue
            out[name] = {
                'all': changed and eff[0] == 'none',
                'only': sorted(eff[1]) if changed and eff[0] == 'only' else None,
                'unset': bool(eff[2]) if changed else False,
                'show': eff[0] if changed else None,
                'builtin': bool(self._pbfs_std_builtin_rule(model, name)),
                'label': label,
            }
        return out

    @api.model
    def _pbfs_std_hidden(self, rule, country_id):
        """Is a box with `rule` (from `_pbfs_std_rules`) hidden for a record
        of `country_id`?"""
        if not rule:
            return False
        if rule.get('all'):
            return True
        only = rule.get('only')
        if only is None:
            return False
        if not country_id:
            return not rule.get('unset')
        return country_id not in only

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
        # Boxes with a built-in country rule: the product's own `_get_view`
        # (TIDY-E) draws their "Shown for", built-in or changed (R31) —
        # whatever order the two `_get_view` overrides run in (FS7-4). Here
        # they only get their own label. `gone` = off the screen for everyone.
        builtin = {n: self._pbfs_std_builtin_rule(model, n) for n in Model._fields}
        builtin = {n: r for n, r in builtin.items() if r}
        gone = {n for n, r in builtin.items()
                if (r == 'remove' and not (rules.get(n) or {}).get('show'))
                or (rules.get(n) or {}).get('show') == 'none'}

        def expr_of(rule):
            if rule['all']:
                return 'True'
            if rule.get('only') is not None:
                if not cvf:
                    return 'True'       # nothing to test here: hide, never show to all
                if rule.get('unset'):
                    return '%s and %s not in %s' % (cvf, cvf, list(rule['only']))
                return '%s not in %s' % (cvf, list(rule['only']))
            return None

        def touch(node, name):
            rule = rules.get(name)
            if not rule:
                return None
            if rule['label'] and not _static_hidden(node):
                node.set('string', rule['label'])
            changed.append(name)
            if name in builtin:
                return None             # its "Shown for" is TIDY-E's to draw
            expr = expr_of(rule)
            if expr:
                node.set('invisible', _or(node.get('invisible'), expr))
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
                if tag == 'field' and child.get('name') in gone:
                    touch(child, child.get('name'))     # its own label, nothing else
                    continue        # off the screen for everyone anyway
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

    @api.model
    def _pbfs_translate_pages(self, arch, words):
        """Give a tab (`<page string>`) still carrying its English words the
        host's own words in the reader's language (`words` = {English: text}).
        → number of tabs renamed. Never touches a tab that already reads
        differently (an owner translation wins)."""
        n = 0
        for page in arch.iter('page'):
            text = words.get(page.get('string'))
            if text and text != page.get('string'):
                page.set('string', text)
                n += 1
        return n

    # ======================================================= administrator
    @api.model
    def _pbfs_std_context(self, model):
        """Everything `_pbfs_std_desc` needs, worked out ONCE per call: the
        catalogue in every language, the locked list, the settings rows."""
        cat = self._pbfs_std_catalogue(model)
        rules = {n: self._pbfs_std_builtin_rule(model, n) for n in cat}
        codes = {r for r in rules.values() if r and r != 'remove'}
        code_ids = self._pbfs_std_code_ids(codes)
        return {
            'cats': {lang: self.with_context(lang=lang)._pbfs_std_catalogue(model)
                     for lang in self._pbfs_langs()},
            'cat': cat,
            'locked': self._pbfs_standard_locked(model),
            'metas': self._pbfs_meta(model),
            'countries': {},
            'code_ids': code_ids,
            'comeback': self._pbfs_std_comeback(model),
            'panel': {n for n, _l, _t in self._pbfs_std_panel_boxes(model)},
            'names': {},
        }

    @api.model
    def _pbfs_show_desc(self, show, ctx=None):
        """A "Shown for" as the Form builder reads it."""
        names = ctx['names'] if ctx is not None else {}
        missing = [i for i in show[1] if i not in names]
        if missing:
            for c in self.env['res.country'].browse(missing).exists():
                names[c.id] = {'id': c.id, 'name': c.name, 'code': c.code}
        countries = sorted((names[i] for i in show[1] if i in names), key=lambda c: c['name'])
        return {'mode': show[0], 'countries': countries, 'unset': bool(show[2])}

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
        # R31 — the built-in "Shown for", what the screens apply, and whether
        # the administrator changed it.
        base, eff, override = self._pbfs_std_effective(
            model, name, meta, ctx['locked'], ctx.get('code_ids'))
        changed = override is not None
        removed = rule == 'remove'
        hidden = changed and eff[0] == 'none'
        # FS-7 words kept for older readers: the countries it is hidden in
        hidden_in = []
        if changed and eff[0] == 'only' and base[0] != 'none':
            pool = self._pbfs_cow_universe() if base[0] == 'all' else base[1]
            hidden_in = sorted(pool - eff[1])
        comeback = (ctx.get('comeback') or {}).get(name, '') if removed else ''
        return {
            'tab': cat.get('tab') or '', 'order': cat.get('order', 0), 'seq': cat.get('seq', 0),
            'builtin': cat.get('label') or name, 'builtins': builtins,
            'labels': {k: v for k, v in labels.items() if isinstance(v, str) and v.strip()},
            'hidden': hidden,
            'countries': self._pbfs_show_desc(('only', frozenset(hidden_in), False),
                                              ctx)['countries'] if hidden_in else [],
            'lock': lock.get('reason') or '',
            'label_lock': (lock.get('reason') or '') if lock.get('label') else '',
            'ignored': bool(lock) and changed and eff != override,
            'rule': rule_desc,
            'base': self._pbfs_show_desc(base, ctx),
            'show': self._pbfs_show_desc(eff, ctx),
            'changed': changed,
            'removed': removed,
            'off': removed and eff[0] == 'none',
            'comeback': str(comeback or ''),
            'propose': self._pbfs_show_desc(self._pbfs_std_propose(model, name), ctx)
            if removed and not comeback else None,
            'panel': name in (ctx.get('panel') or ()),
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
        base = self._pbfs_std_base(model, name)
        old = self._pbfs_std_override(meta, base)
        cur = old if old is not None else base
        new = cur
        if any(k in vals for k in SHOW_KEYS):
            # R31 — "Shown for": all countries / only these / hidden for
            # everyone, or the built-in setting put back.
            mode = vals.get('std_show') or 'builtin'
            if mode == 'builtin':
                new = base
            elif mode == 'all':
                new = SHOW_ALL
            elif mode == 'none':
                new = SHOW_NONE
            elif mode == 'only':
                new = show_only(self._pbfs_country_ids(vals.get('std_show_country_ids')),
                                bool(vals.get('std_show_unset')))
            else:
                raise UserError(_('Choose who sees this field: all countries, only some '
                                  'Countries of Work, or nobody.'))
        elif 'std_hidden' in vals or 'std_country_ids' in vals:
            # FS-7's words (hidden for everyone / hidden in these countries),
            # read on top of the built-in setting, as before.
            old_hidden = cur[0] == 'none' and base[0] != 'none'
            old_in = []
            if cur[0] == 'only' and base[0] != 'none':
                pool = self._pbfs_cow_universe() if base[0] == 'all' else base[1]
                old_in = sorted(pool - cur[1])
            hidden = bool(vals['std_hidden']) if 'std_hidden' in vals else old_hidden
            hidden_in = self._pbfs_country_ids(vals['std_country_ids']) \
                if 'std_country_ids' in vals else old_in
            if not hidden and not hidden_in:
                new = base
            else:
                new = self._pbfs_std_legacy(base, hidden, [] if hidden else hidden_in)
        changes = []
        new_vals = {}
        if new != cur or (meta.std_hidden or meta.std_country_ids):
            if new != cur:
                comeback = self._pbfs_std_comeback(model).get(name) \
                    if base[0] == 'none' and self._pbfs_std_builtin_rule(model, name) == 'remove' \
                    else ''
                if comeback and new[0] != 'none':
                    raise UserError(_('%s It cannot be shown again.', comeback))
                # A locked field may be shown MORE than the product shows it
                # (R31: widening is always allowed), never less: a rule saved
                # before it became locked can be widened or put back.
                if lock and not show_covers(new, base):
                    raise UserError(_('%s It cannot be hidden.', lock['reason']))
            new_vals.update(std_hidden=False, std_country_ids=[(5,)])
            if new == base:
                new_vals.update(std_show=False, std_show_country_ids=[(5,)], std_show_unset=False)
            else:
                new_vals.update(std_show=new[0], std_show_country_ids=[(6, 0, sorted(new[1]))],
                                std_show_unset=bool(new[2]) and new[0] == 'only')
            if new != cur:
                changes.append(self._pbfs_show_words(new, base))
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
    def _pbfs_show_words(self, show, base=None):
        """A "Shown for" in a history line: "shown for all countries",
        "shown only for Vietnam, Indonesia", "hidden for everyone", "built-in
        setting put back"."""
        _ = self.env._
        if base is not None and show == base:
            return _('built-in setting put back')
        if show[0] == 'all':
            return _('shown for all countries')
        if show[0] == 'none':
            return _('hidden for everyone')
        names = sorted(self.env['res.country'].browse(sorted(show[1])).exists().mapped('name'))
        if show[2]:
            names.append(_('people with no Country of Work'))
        return _('shown only for %s', ', '.join(names))

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
    def _pbfs_std_unhide_locked(self, model, why='', notice=False):
        """Clear the hide rule (for everyone or by country) of every standard
        field of `model` the locked list now holds, with one history line
        each. The screens already ignore such a rule (`_pbfs_std_rules`); this
        makes the stored rule say so too. Own labels are kept. Idempotent.
        Called by the hosts' upgrade steps and by `_pbfs_std_readers_changed`
        (`notice`: the administrators get one notice per field, "<box> is
        shown again because <thing> now uses it"). → the names cleared."""
        if model not in self.env:
            return []
        locked = self._pbfs_standard_locked(model)
        Meta = self.env['pb.form.field.meta'].sudo()
        rows = Meta.search([('model', '=', model), ('custom', '=', False),
                            ('name', 'in', list(locked))] + RULE_DOMAIN)
        names = []
        _ = self.env._
        todo = []
        for meta in rows:
            # R31: a locked field is never shown LESS than its built-in
            # setting; a wider rule (shown for more countries) is kept.
            base = self._pbfs_std_base(model, meta.name)
            override = self._pbfs_std_override(meta, base)
            if override is None or show_covers(override, base):
                continue
            todo.append((meta, show_union(base, override), base))
        things = self._pbfs_std_used_things(model) if notice and todo else {}
        for meta, wide, base in todo:
            if wide == base:
                meta.write({'std_hidden': False, 'std_country_ids': [(5,)], 'std_show': False,
                            'std_show_country_ids': [(5,)], 'std_show_unset': False})
            else:
                meta.write({'std_hidden': False, 'std_country_ids': [(5,)], 'std_show': wide[0],
                            'std_show_country_ids': [(6, 0, sorted(wide[1]))],
                            'std_show_unset': bool(wide[2]) and wide[0] == 'only'})
            box = self._pbfs_std_screen_label(model, meta.name)
            reason = locked[meta.name]['reason']
            self._pbfs_audit('update_field', None, model, meta.name,
                             ('%s: %s %s %s' % (box, _('shown again, it cannot be hidden.'),
                                                reason, why or '')).strip(),
                             detail={'standard': True, 'unhidden_locked': True})
            if notice:
                thing = things.get(meta.name) or (notice if isinstance(notice, str) else '')
                self._pbfs_std_notice(box, thing, reason)
            names.append(meta.name)
        if names:
            self.env.registry.clear_cache('templates')
        return names

    @api.model
    def _pbfs_std_notice(self, box, thing, reason=''):
        """One notice to the tenant administrators: "<box> is shown again
        because <thing> now uses it". In the inbox of those who read notices
        in the app (nobody is mailed for it) and as a pop-up for those online."""
        _ = self.env._
        if thing:
            text = _('%(box)s is shown again because %(thing)s now uses it.', box=box, thing=thing)
        else:
            text = _('%(box)s is shown again: %(reason)s', box=box, reason=reason)
        group = self.env.ref('base.group_system', raise_if_not_found=False)
        if not group:
            return
        users = group.sudo().all_user_ids.filtered(lambda u: u.active and not u.share
                                                   and u.id != SUPERUSER_ID)
        inbox = users.filtered(lambda u: getattr(u, 'notification_type', 'inbox') == 'inbox')
        if inbox and 'mail.thread' in self.env:
            try:
                with self.env.cr.savepoint():
                    self.env['mail.thread'].sudo().message_notify(
                        partner_ids=inbox.partner_id.ids, body=text, subject=_('Form builder'))
            except Exception:                           # noqa: BLE001
                _logger.info('Form builder: the notice could not be posted', exc_info=True)
        for user in users:
            try:
                user._bus_send('simple_notification', {'title': _('Form builder'),
                                                       'message': text, 'sticky': True})
            except Exception:                           # noqa: BLE001
                _logger.debug('Form builder: no pop-up', exc_info=True)

    @api.model
    def _pbfs_std_sweep(self):
        """Drop the screen rule of a standard field that no longer exists
        (an upgrade removed it), with a history line. The settings row is
        removed by the database with its field; this catches a row left on a
        field the registry no longer has. → number of rows dropped."""
        dropped = 0
        Meta = self.env['pb.form.field.meta'].sudo()
        for meta in Meta.search([('custom', '=', False)]):
            if not (meta.std_show or meta.std_hidden or meta.std_country_ids or meta.std_labels):
                continue
            model, name = meta.model, meta.name
            if model in self.env and name in self.env[model]._fields:
                continue
            self._pbfs_audit('update_field', None, model, name,
                             self.env._('%s no longer exists: its screen rule was removed.', name))
            meta.write({'std_hidden': False, 'std_country_ids': [(5,)], 'std_labels': False,
                        'std_show': False, 'std_show_country_ids': [(5,)],
                        'std_show_unset': False})
            dropped += 1
        if dropped:
            self.env.registry.clear_cache('templates')
        return dropped
