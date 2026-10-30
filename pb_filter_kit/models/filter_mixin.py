# -*- coding: utf-8 -*-
"""The filter panel's server half: one mixin every cockpit list inherits.

A screen says WHAT can be filtered (`_pbf_spec`); the mixin owns HOW:

* the domain a filter state means (`pbf_domain`),
* the count beside every value, counted the way shops count (each section
  counts against every OTHER active filter, so ticking a second country
  never zeroes the first one's number),
* which sections are worth showing on THIS database (a section whose field
  holds one value or none is hidden: the demo world has one country, Rize
  has five),
* the built-in views and the views people saved.

Filter state, as the browser sends it, keyed by section::

    {"department": [12, 14, false],          # many2one / selection / char / choice
     "joined": {"preset": "this_month"},       # date: a preset ...
     "ends": {"from": "2026-11-01", "to": ""}, # ... or a range
     "wage": {"min": 5000000, "max": null}}    # number

Every section degrades on its own: a field this database does not have, or
one the user may not read (``groups=``), drops out of the panel instead of
breaking it (the every-probe-its-own-guard rule).
"""
import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

#: Values sent per section. The rest are found by typing in the panel.
VALUE_CAP = 300
#: Saved views counted per load (each is one count query).
VIEW_CAP = 40
LIST_TYPES = ('many2one', 'selection', 'char', 'choice')
PAST_PRESETS = ('this_month', 'last_month', 'last_90', 'this_year', 'last_year', 'none')
FUTURE_PRESETS = ('passed', 'next_30', 'next_90', 'later', 'none')


class PbFilterMixin(models.AbstractModel):
    _name = 'pb.filter.mixin'
    _description = 'Filter panel for a list screen'

    # ================================================================ hooks
    # A screen overrides these. Only `_pbf_model` and `_pbf_spec` are required.

    def _pbf_model(self):
        """Technical name of the model the list shows, e.g. 'hr.employee'."""
        raise NotImplementedError

    def _pbf_screen(self):
        """Key the saved views are filed under (one per list)."""
        return self._name

    def _pbf_base_domain(self):
        """What the list holds before anybody filters it."""
        return []

    def _pbf_spec(self):
        """The sections, in panel order. See the module docstring."""
        return []

    def _pbf_search_fields(self):
        """Paths the list's search box looks in."""
        return ['display_name']

    def _pbf_builtin_views(self):
        """[{key, label, icon, filters}] — the first one is the start view."""
        return [{'key': 'all', 'label': _('All'), 'icon': 'layoutList', 'filters': {}}]

    def _pbf_sorts(self):
        """[{key, label, order}] — the first one is the default."""
        return []

    def _pbf_layout_extra(self):
        """Anything else the screen wants to hand the panel (e.g. currency)."""
        return {}

    # ============================================================ helpers
    def _pbf_records(self):
        return self.env[self._pbf_model()]

    @api.model
    def _pbf_groups(self):
        return [
            {'key': 'people', 'label': _('People')},
            {'key': 'work', 'label': _('Work')},
            {'key': 'contract', 'label': _('Contract')},
            {'key': 'pay', 'label': _('Pay')},
            {'key': 'dates', 'label': _('Dates')},
            {'key': 'other', 'label': _('Other')},
        ]

    @api.model
    def _pbf_resolve(self, path):
        """(model, field) at the end of `path`, or (None, None) when any hop
        is missing on this database or not readable by this user."""
        Model = self._pbf_records()
        parts = (path or '').split('.')
        field = None
        for i, part in enumerate(parts):
            field = Model._fields.get(part)
            if field is None or not Model._has_field_access(field, 'read'):
                return None, None
            if i < len(parts) - 1:
                if field.type != 'many2one':
                    return None, None
                Model = self.env[field.comodel_name]
        return Model, field

    @api.model
    def _pbf_opt_domain(self, option):
        """A choice option's domain. Either a literal `domain` (any domain the
        records model accepts, one2many/many2many paths and `any` included,
        `self.env.uid` baked in at spec time for "mine") or a `domain_method`:
        the name of a method on this screen model that returns a domain at
        request time — the door for facts that are Python, not fields
        (e.g. `[('id', 'in', ids_found_by_the_pay_feed)]`)."""
        if option.get('domain_method'):
            return getattr(self, option['domain_method'])() or []
        return option.get('domain') if option.get('domain') is not None else []

    @api.model
    def _pbf_clean_spec(self):
        """The screen's spec, minus sections this database cannot serve."""
        out = []
        for s in self._pbf_spec() or []:
            s = dict(s)
            t = s.get('type')
            try:
                if t == 'choice':
                    opts = [o for o in s.get('options') or []
                            if o.get('domain') is not None or o.get('domain_method')]
                    if s.get('requires'):
                        if not all(self._pbf_resolve(p)[1] for p in s['requires']):
                            continue
                    if len(opts) < 2:
                        continue
                    s['options'] = opts
                else:
                    Model, field = self._pbf_resolve(s.get('path'))
                    if field is None:
                        continue
                    if t == 'selection':
                        sel = Model.fields_get([field.name], ['selection']).get(field.name, {})
                        s['selection'] = dict(sel.get('selection') or [])
                out.append(s)
            except Exception as e:  # noqa: BLE001 — one section never breaks the panel
                _logger.info("Filter section %s dropped: %s", s.get('key'), e)
        return out

    @api.model
    def _pbf_today(self):
        return fields.Date.context_today(self)

    @api.model
    def _pbf_preset_range(self, preset):
        """(start, end_exclusive) for a date preset; None bounds are open."""
        t = self._pbf_today()
        month = t.replace(day=1)
        if preset == 'this_month':
            return month, month + relativedelta(months=1)
        if preset == 'last_month':
            return month - relativedelta(months=1), month
        if preset == 'last_90':
            return t - timedelta(days=90), t + timedelta(days=1)
        if preset == 'this_year':
            return date(t.year, 1, 1), date(t.year + 1, 1, 1)
        if preset == 'last_year':
            return date(t.year - 1, 1, 1), date(t.year, 1, 1)
        if preset == 'passed':
            return None, t
        if preset == 'next_30':
            return t, t + timedelta(days=31)
        if preset == 'next_90':
            return t, t + timedelta(days=91)
        if preset == 'later':
            return t + timedelta(days=91), None
        return None

    @api.model
    def _pbf_preset_labels(self):
        return {
            'this_month': _('This month'),
            'last_month': _('Last month'),
            'last_90': _('Last 90 days'),
            'this_year': _('This year'),
            'last_year': _('Last year'),
            'passed': _('Already passed'),
            'next_30': _('Next 30 days'),
            'next_90': _('Next 90 days'),
            'later': _('Later than 90 days'),
        }

    @api.model
    def _pbf_presets(self, s):
        return FUTURE_PRESETS if s.get('presets') == 'future' else PAST_PRESETS

    @api.model
    def _pbf_date_domain(self, path, preset=None, start=None, end=None):
        if preset == 'none':
            return Domain(path, '=', False)
        if preset:
            rng = self._pbf_preset_range(preset)
            if not rng:
                return None
            start, end = rng
        parts = []
        if start:
            parts.append(Domain(path, '>=', fields.Date.to_string(start)))
        if end:
            parts.append(Domain(path, '<', fields.Date.to_string(end)))
        return Domain.AND(parts) if parts else None

    @api.model
    def _pbf_section_domain(self, s, val):
        """Domain for one section's state, or None when it filters nothing."""
        t = s['type']
        path = s.get('path')
        if t in ('many2one', 'selection', 'char'):
            vals = val if isinstance(val, list) else []
            if not vals:
                return None
            real = [v for v in vals if v not in (False, None, '')]
            if t == 'many2one':
                real = [int(v) for v in real if str(v).lstrip('-').isdigit()]
            parts = []
            if real:
                parts.append(Domain(path, 'in', real))
            if len(real) != len(vals):
                parts.append(Domain(path, '=', False))
            return Domain.OR(parts) if parts else None
        if t == 'choice':
            vals = val if isinstance(val, list) else []
            opts = {o['value']: o for o in s.get('options') or []}
            parts = [Domain(self._pbf_opt_domain(opts[v])) for v in vals if v in opts]
            return Domain.OR(parts) if parts else None
        if t == 'date' and isinstance(val, dict):
            if val.get('preset'):
                if val['preset'] not in self._pbf_presets(s):
                    return None
                return self._pbf_date_domain(path, preset=val['preset'])
            start = fields.Date.to_date(val.get('from')) if val.get('from') else None
            end = fields.Date.to_date(val.get('to')) if val.get('to') else None
            return self._pbf_date_domain(path, start=start,
                                         end=end + timedelta(days=1) if end else None)
        if t == 'number' and isinstance(val, dict):
            parts = []
            for key, op in (('min', '>='), ('max', '<=')):
                v = val.get(key)
                if v not in (None, ''):
                    try:
                        parts.append(Domain(path, op, float(v)))
                    except (TypeError, ValueError):
                        continue
            return Domain.AND(parts) if parts else None
        return None

    @api.model
    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        parts = []
        for p in self._pbf_search_fields():
            if p == 'display_name' or self._pbf_resolve(p)[1] is not None:
                parts.append(Domain(p, 'ilike', q))
        return Domain.OR(parts) if parts else None

    @api.model
    def pbf_domain(self, filters=None, search=None, skip=None, spec=None):
        """The whole list's domain: base AND search AND every section (except
        `skip`, used when counting that section's own values)."""
        spec = spec if spec is not None else self._pbf_clean_spec()
        parts = [Domain(self._pbf_base_domain() or [])]
        sd = self._pbf_search_domain(search)
        if sd is not None:
            parts.append(sd)
        filters = filters if isinstance(filters, dict) else {}
        for s in spec:
            if s['key'] == skip or s['key'] not in filters:
                continue
            try:
                d = self._pbf_section_domain(s, filters[s['key']])
            except Exception as e:  # noqa: BLE001
                _logger.info("Filter %s ignored: %s", s['key'], e)
                d = None
            if d is not None:
                parts.append(d)
        return Domain.AND(parts)

    @api.model
    def _pbf_pretty(self, value):
        """A label for a raw char value ('retail' -> 'Retail', 'it' -> 'IT')."""
        v = str(value)
        if v != v.lower():
            return v
        return v.upper() if len(v) <= 3 else v.replace('_', ' ').capitalize()

    # ============================================================ counting
    @api.model
    def _pbf_list_values(self, s, domain, selected=None):
        """[{v, label, n}] for a list-type section, most common first."""
        Rec = self._pbf_records()
        t, path = s['type'], s.get('path')
        none_label = s.get('none_label') or _('Not set')
        rows = []
        if t == 'choice':
            for o in s.get('options') or []:
                n = Rec.search_count(Domain.AND([domain, Domain(self._pbf_opt_domain(o))]))
                rows.append({'v': o['value'], 'label': o['label'], 'n': n,
                             'tone': o.get('tone') or ''})
            return rows, False
        groups = Rec._read_group(domain, [path], ['__count'])
        for value, count in groups:
            if t == 'many2one':
                v = value.id if value else False
                label = (value.display_name if value else none_label) or none_label
            elif t == 'selection':
                v = value if value else False
                label = s.get('selection', {}).get(value, self._pbf_pretty(value)) if value else none_label
            else:
                v = value if value not in (None, '') else False
                label = self._pbf_pretty(value) if v else none_label
            rows.append({'v': v, 'label': label, 'n': count})
        if t == 'selection':
            order = list(s.get('selection', {}).keys())
            rows.sort(key=lambda r: (r['v'] is False, order.index(r['v']) if r['v'] in order else 999))
        else:
            rows.sort(key=lambda r: (r['v'] is False, -r['n'], (r['label'] or '').lower()))
        more = len(rows) > VALUE_CAP
        rows = rows[:VALUE_CAP]
        # A ticked value always shows, even when nothing matches it any more.
        have = {r['v'] for r in rows}
        missing = [v for v in (selected or []) if v not in have]
        if missing:
            rows.extend(self._pbf_label_values(s, missing))
        return rows, more

    @api.model
    def _pbf_label_values(self, s, values):
        out = []
        none_label = s.get('none_label') or _('Not set')
        Model, field = self._pbf_resolve(s.get('path'))
        for v in values:
            label = none_label
            if v not in (False, None, ''):
                label = str(v)
                try:
                    if s['type'] == 'many2one' and field is not None:
                        rec = self.env[field.comodel_name].browse(int(v)).exists()
                        label = rec.display_name if rec else _('Removed')
                    elif s['type'] == 'selection':
                        label = s.get('selection', {}).get(v, str(v))
                    else:
                        label = self._pbf_pretty(v)
                except Exception:  # noqa: BLE001
                    pass
            out.append({'v': v, 'label': label, 'n': 0})
        return out

    @api.model
    def _pbf_number_range(self, s, domain):
        """(min, max) of a number section over `domain`, or (None, None)."""
        Rec = self._pbf_records()
        path = s['path']
        if '.' not in path:
            res = Rec._read_group(domain, [], ['%s:min' % path, '%s:max' % path])
            return tuple(res[0]) if res else (None, None)
        head, tail = path.split('.', 1)
        if '.' in tail:
            return None, None
        target = Rec.search(domain).mapped(head)
        if not target:
            return None, None
        res = target._read_group([('id', 'in', target.ids)], [], ['%s:min' % tail, '%s:max' % tail])
        return tuple(res[0]) if res else (None, None)

    @api.model
    def _pbf_count_section(self, s, filters, search, spec):
        domain = self.pbf_domain(filters, search, skip=s['key'], spec=spec)
        Rec = self._pbf_records()
        t = s['type']
        if t in LIST_TYPES:
            selected = filters.get(s['key']) if isinstance(filters.get(s['key']), list) else []
            values, more = self._pbf_list_values(s, domain, selected)
            return {'values': values, 'more': more}
        if t == 'date':
            labels = self._pbf_preset_labels()
            presets = []
            for p in self._pbf_presets(s):
                d = self._pbf_date_domain(s['path'], preset=p)
                presets.append({
                    'v': p,
                    'label': s.get('none_label') if p == 'none' else labels.get(p, p),
                    'n': Rec.search_count(Domain.AND([domain, d])) if d is not None else 0,
                })
            return {'presets': presets}
        if t == 'number':
            lo, hi = self._pbf_number_range(s, domain)
            return {'min': lo, 'max': hi}
        return {}

    @api.model
    def _pbf_worth_showing(self, s, base):
        """Does this section split THIS database's list into more than one
        group? Judged on the unfiltered list, once per load, so sections do
        not come and go while somebody filters."""
        if s.get('always'):
            return True
        Rec = self._pbf_records()
        t = s['type']
        if t == 'choice':
            total = Rec.search_count(base)
            for o in s.get('options') or []:
                n = Rec.search_count(Domain.AND([base, Domain(self._pbf_opt_domain(o))]))
                if 0 < n < total:
                    return True
            return False
        if t in ('many2one', 'selection', 'char'):
            return len(Rec._read_group(base, [s['path']], ['__count'], limit=2)) >= 2
        if t in ('date', 'number'):
            return bool(Rec.search_count(Domain.AND([base, Domain(s['path'], '!=', False)]), limit=1))
        return False

    # ============================================================== views
    @api.model
    def _pbf_views(self, spec, base):
        Rec = self._pbf_records()

        def count(filters, search=''):
            try:
                return Rec.search_count(self.pbf_domain(filters, search, spec=spec))
            except Exception as e:  # noqa: BLE001
                _logger.info("View count failed: %s", e)
                return None

        keys = {s['key'] for s in spec}
        builtin = []
        for v in self._pbf_builtin_views() or []:
            fl = v.get('filters') or {}
            # a built-in view that needs a section this database lacks is not offered
            if any(k not in keys for k in fl):
                continue
            builtin.append({
                'key': v['key'], 'label': v['label'], 'icon': v.get('icon') or '',
                'filters': fl, 'search': '', 'builtin': True, 'shared': True,
                'mine': False, 'owner': '', 'n': count(fl),
            })
        saved = []
        try:
            recs = self.env['pb.filter.view'].search(
                [('screen', '=', self._pbf_screen())], limit=VIEW_CAP)
            for r in recs:
                p = r._pbf_payload()
                p['n'] = count(p['filters'], p['search'])
                saved.append(p)
            saved.sort(key=lambda p: (not p['mine'], p['label'].lower()))
        except Exception as e:  # noqa: BLE001
            _logger.info("Saved views unavailable: %s", e)
        return builtin + saved

    # ============================================================ the API
    # Every call may carry `context={'pbf_ctx': {...}}` from the browser (the
    # kit's `ctx` option): a screen that shows several record types under one
    # action reads `self.env.context.get('pbf_ctx')` in its hooks to pick the
    # model, screen key and spec. A screen that must refuse some readers
    # overrides `pbf_layout` to return `{'refused': <message>}` — the kit then
    # shows nothing and the screen shows its own refusal.

    @api.model
    def _pbf_ctx(self):
        ctx = self.env.context.get('pbf_ctx')
        return ctx if isinstance(ctx, dict) else {}

    @api.model
    def pbf_layout(self):
        """Once per load: the sections worth showing, views, sorts."""
        spec = self._pbf_clean_spec()
        base = Domain(self._pbf_base_domain() or [])
        sections = []
        for s in spec:
            try:
                shown = self._pbf_worth_showing(s, base)
            except Exception as e:  # noqa: BLE001
                _logger.info("Filter section %s hidden: %s", s.get('key'), e)
                shown = False
            # Hidden sections still travel: a view or a link may switch one on,
            # and its chip needs a name. The panel lists them only while on.
            out = {k: s.get(k) for k in ('key', 'label', 'icon', 'group', 'type', 'unit',
                                          'pinned', 'help', 'none_label')}
            out['shown'] = bool(shown)
            out['group'] = out.get('group') or 'other'
            if s['type'] == 'date':
                out['presets'] = 'future' if s.get('presets') == 'future' else 'past'
            sections.append(out)
        Rec = self._pbf_records()
        return {
            'screen': self._pbf_screen(),
            'sections': sections,
            'groups': self._pbf_groups(),
            'sorts': [{'key': s['key'], 'label': s['label']} for s in self._pbf_sorts() or []],
            # Views are judged on every section this database HAS, shown or
            # not: "Not payroll-ready 0" is good news, not a missing tab.
            'views': self._pbf_views(spec, base),
            'total': Rec.search_count(base),
            'extra': self._pbf_layout_extra() or {},
        }

    @api.model
    def pbf_counts(self, filters=None, search=None, keys=None):
        """Every time the filters change: the count beside each value."""
        filters = filters if isinstance(filters, dict) else {}
        spec = self._pbf_clean_spec()
        out = {}
        for s in spec:
            if keys is not None and s['key'] not in keys:
                continue
            try:
                out[s['key']] = self._pbf_count_section(s, filters, search, spec)
            except Exception as e:  # noqa: BLE001
                _logger.info("Filter counts for %s failed: %s", s['key'], e)
                out[s['key']] = {'error': True}
        Rec = self._pbf_records()
        return {
            'sections': out,
            'matched': Rec.search_count(self.pbf_domain(filters, search, spec=spec)),
        }

    @api.model
    def pbf_find_values(self, key, query, filters=None, search=None):
        """Values of one long section matching what was typed in the panel's
        find box (the panel only holds the first VALUE_CAP of them)."""
        q = (query or '').strip().lower()
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == key), None)
        if not s or s['type'] not in ('many2one', 'char', 'selection') or not q:
            return []
        domain = self.pbf_domain(filters or {}, search, skip=key, spec=spec)
        if s['type'] == 'many2one':
            Model, field = self._pbf_resolve(s['path'])
            co = self.env[field.comodel_name]
            hits = co.search([('display_name', 'ilike', q)], limit=40)
            if not hits:
                return []
            domain = Domain.AND([domain, Domain(s['path'], 'in', hits.ids)])
        values, _more = self._pbf_list_values(s, domain)
        return [v for v in values if q in (v['label'] or '').lower()][:40]

    @api.model
    def pbf_order(self, sort=None):
        sorts = self._pbf_sorts() or []
        for s in sorts:
            if s['key'] == sort:
                return s['order']
        return sorts[0]['order'] if sorts else None
