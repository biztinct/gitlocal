# -*- coding: utf-8 -*-
"""FS-8 — the Explorer split and filtered by the customer's own fields.

`pb_explorer` asks five generic hooks (`_pbx_extra_*`, FS8_FACTS §5); this
file answers them from the Form builder engine:

* WHICH fields: `pb.form.studio.fields_for(model, 'list')` as the REAL reader
  — custom fields marked "Show in lists" that this person may see (the
  engine's own visibility, FS-1 §2; field rules from Access hook the same
  check). Asked per call, so a field made a minute ago on another worker is
  there on the next request, with no upgrade and no restart (FS8_FACTS §5).
* WHERE the value comes from: an employee field is the person's value as it
  is TODAY (`hr_employee`, joined on `pb_fact_emp.employee_id`); a contract
  field is read from the contract each payslip of the run was made with
  (`hr_payslip.contract_id`). Nothing is stored, nothing is rebuilt, no
  column or index is added: the stand-in table exists for one statement.
* Country of Work (R10): a field limited to some countries reads "—" for
  people elsewhere — and for people with no Country of Work, exactly as
  `_pbfs_applies` decides on every other screen.

Keys look like `field:hr.employee:x_pbfs_shirt_size` (and, for a date,
`…:month` / `…:quarter` / `…:year`). They are only ever matched against the
fields offered to the reader, never interpolated.
"""
import re
from datetime import date

from odoo import api, models

from odoo.addons.pb_explorer.models.pb_explorer import _extra_col
from odoo.addons.pb_form_studio.models.ir_model_fields import PREFIX

PREFIX_KEY = 'field'
EMPLOYEE, CONTRACT = 'hr.employee', 'hr.contract'
MODELS = (EMPLOYEE, CONTRACT)
#: Choice list, yes / no, short text, date, link to a record (handover
#: constraint 1). Long text, files, numbers and money are never offered.
ELIGIBLE = ('selection', 'boolean', 'char', 'date', 'many2one')
GRAINS = ('month', 'quarter', 'year')
NONE, NA = '__none__', '__na__'
_NAME = re.compile(r'^%s[a-z0-9_]{1,55}$' % re.escape(PREFIX))
_CODE = re.compile(r'^[A-Z]{2,3}$')
#: How many values a text / link / date filter offers to pick from.
OPTIONS_CAP = 200


def make_key(model, name, grain=None):
    return ':'.join([PREFIX_KEY, model, name] + ([grain] if grain else []))


def parse_key(key):
    """`(model, name, grain)` or `None` — shape only; whether the reader may
    use it is decided by `_pbx_extra_dims`."""
    if not isinstance(key, str):
        return None
    parts = key.split(':')
    if len(parts) not in (3, 4) or parts[0] != PREFIX_KEY or parts[1] not in MODELS:
        return None
    if not _NAME.match(parts[2]):
        return None
    grain = parts[3] if len(parts) == 4 else None
    if grain is not None and grain not in GRAINS:
        return None
    return parts[1], parts[2], grain


class PbExplorerOwnFields(models.AbstractModel):
    _inherit = 'pb.explorer'

    # ------------------------------------------------------------ which
    def _pbfx_fingerprint(self):
        """Changes whenever a field's settings row changes — even twice in one
        transaction (every update writes a new row version, so a new ctid)."""
        self.env.cr.execute(
            "SELECT COUNT(*), md5(COALESCE(string_agg(ctid::text, ',' ORDER BY id), '')) "
            "FROM pb_form_field_meta")
        count, digest = self.env.cr.fetchone()
        sizes = tuple(len(self.env[m]._fields) for m in MODELS if m in self.env)
        return count, digest, sizes

    @api.model
    def _pbfx_fields(self):
        """`{key: descriptor}` of every own field THIS reader may split and
        filter by. Remembered for the rest of the request only (a request
        asks several times); the memory is keyed on everything the answer
        depends on, so a change is never answered from it."""
        user = self.env.user
        memo_key = ('pbfx_fields', self.env.uid, self.env.su,
                    self.env.lang or '', tuple(self.env.companies.ids),
                    tuple(user._get_group_ids()) if user else (),
                    self._pbfx_fingerprint())
        cache = self.env.cr.cache
        if memo_key in cache:
            return cache[memo_key]
        out = {}
        Studio = self.env['pb.form.studio']
        hosts = set(Studio._pbfs_host_models())
        _ = self.env._
        where = {EMPLOYEE: _("Employee · as it is today"),
                 CONTRACT: _("Contract · as on each payslip")}
        grain_words = {'month': _("by month"), 'quarter': _("by quarter"),
                       'year': _("by year")}
        for model in MODELS:
            if model not in hosts or model not in self.env:
                continue
            Model = self.env[model]
            metas = Studio._pbfs_meta(model)
            for spec in Studio.fields_for(model, 'list'):
                name = spec['name']
                field = Model._fields.get(name)
                if not field or field.type not in ELIGIBLE or not _NAME.match(name) \
                        or not field.store or not field.column_type:
                    continue
                meta = metas.get(name)
                codes = tuple(sorted(c for c in (meta.country_ids.mapped('code') if meta else [])
                                     if c and _CODE.match(c.upper())))
                base = {'label': spec['label'], 'sub': where[model], 'icon': 'sparkles',
                        'model': model, 'field': name, 'type': field.type,
                        'codes': tuple(c.upper() for c in codes),
                        'limited': bool(meta and meta.country_ids)}
                if field.type == 'date':
                    for grain in GRAINS:
                        out[make_key(model, name, grain)] = dict(
                            base, grain=grain, order='key',
                            label=_("%(field)s, %(grain)s", field=spec['label'],
                                    grain=grain_words[grain]),
                            ask=spec['label'] if grain == 'month' else '')
                else:
                    out[make_key(model, name)] = dict(base, grain=None, ask=spec['label'])
        cache[memo_key] = out
        return out

    @api.model
    def _pbx_extra_dims(self):
        return dict(super()._pbx_extra_dims(), **self._pbfx_fields())

    @api.model
    def _pbx_extra_group(self):
        out = dict(super()._pbx_extra_group() or {})
        if not self._pbfx_fields():
            return out
        _ = self.env._
        return {
            'title': _("Your own fields"),
            'note': _("Employee fields show each person's value as it is today. "
                      "Contract fields show the value on the contract each payslip "
                      "was made with. People in a country a field is not used in "
                      "show as —."),
        }

    @api.model
    def _pbx_extra_gone(self, keys):
        """A key whose field no longer exists at all (deleted in the Form
        builder) — not one that is merely hidden from this reader."""
        out = list(super()._pbx_extra_gone(keys) or [])
        for key in keys or []:
            parsed = parse_key(key)
            if not parsed:
                continue
            model, name, _grain = parsed
            if model not in self.env or name not in self.env[model]._fields:
                out.append(key)
        return out

    # ------------------------------------------------------------ values
    @staticmethod
    def _pbfx_value_sql(desc, column):
        """The text a fact row is grouped by, from one column."""
        kind = desc['type']
        if kind == 'boolean':
            return "CASE WHEN %s THEN 'true' ELSE 'false' END" % column
        if kind == 'many2one':
            return "%s::text" % column
        if kind == 'char':
            return "NULLIF(btrim(%s), '')" % column
        if kind == 'date':
            fmt = {'month': 'YYYY-MM', 'quarter': 'YYYY-"Q"Q', 'year': 'YYYY'}[desc['grain']]
            return "to_char(%s, '%s')" % (column, fmt)
        return "NULLIF(%s, '')" % column                    # selection

    @api.model
    def _pbfx_flush(self, descs):
        """The values are read with SQL: anything written earlier in the same
        transaction must reach the table first."""
        by_model = {}
        for desc in descs:
            by_model.setdefault(desc['model'], set()).add(desc['field'])
        if by_model:
            Emp = self.env[EMPLOYEE]
            if 'payroll_country' in Emp._fields:
                by_model.setdefault(EMPLOYEE, set()).add('payroll_country')
        for model, names in by_model.items():
            self.env[model].flush_model(sorted(names))
        if CONTRACT in by_model:
            self.env['hr.payslip'].flush_model(
                ['contract_id', 'employee_id', 'payslip_run_id', 'state'])

    @api.model
    def _pbx_extra_source(self, keys, run_ids, alias):
        known = self._pbfx_fields()
        mine = [k for k in keys if k in known]
        if not mine or len(mine) != len(keys):
            return super()._pbx_extra_source(keys, run_ids, alias)
        if not re.match(r'^[a-z_]{1,20}$', alias or ''):
            return None
        cols, params = [], []
        need_emp = need_contract = False
        self._pbfx_flush([known[k] for k in mine])
        for key in mine:
            desc = known[key]
            table = 'pbx_e' if desc['model'] == EMPLOYEE else 'pbx_k'
            need_emp |= desc['model'] == EMPLOYEE
            need_contract |= desc['model'] == CONTRACT
            value = "COALESCE(%s, '%s')" % (
                self._pbfx_value_sql(desc, '%s."%s"' % (table, desc['field'])), NONE)
            if desc['limited']:
                # R10 — the person's Country of Work decides; nobody recorded,
                # or a country the field is not used in, reads "—".
                need_emp = True
                if desc['codes']:
                    value = ("CASE WHEN UPPER(COALESCE(pbx_e.payroll_country, '')) IN %%s "
                             "THEN %s ELSE '%s' END" % (value, NA))
                    params.append(desc['codes'])
                else:
                    value = "'%s'" % NA
            cols.append('%s AS %s' % (value, _extra_col(key)))
        sql = 'SELECT f.*, %s FROM pb_fact_emp f' % ', '.join(cols)
        if need_emp:
            sql += ' LEFT JOIN hr_employee pbx_e ON pbx_e.id = f.employee_id'
        if need_contract:
            # The contract EACH payslip of the run was made with, one per
            # person and run (the newest contract if a person had two
            # payslips in one run). One hash-grouped read over the runs in
            # scope, hash-joined: `hr_payslip` is indexed on the run, not on
            # the employee (FS8_FACTS §1); a sort here cost a third more.
            sql += (" LEFT JOIN (SELECT p.payslip_run_id AS run_id, p.employee_id,"
                    "        MAX(p.contract_id) AS contract_id"
                    "   FROM hr_payslip p"
                    "  WHERE p.state != 'cancel' AND p.payslip_run_id IN %s"
                    "  GROUP BY 1, 2) pbx_p"
                    "   ON pbx_p.run_id = f.run_id AND pbx_p.employee_id = f.employee_id"
                    " LEFT JOIN hr_contract pbx_k ON pbx_k.id = pbx_p.contract_id")
            params.append(tuple(int(r) for r in run_ids or []) or (0,))
        sql = '(%s) %s' % (sql, alias)
        return self.env.cr.mogrify(sql, params).decode()

    # ------------------------------------------------------------ words
    @api.model
    def _pbfx_value_words(self, desc, values):
        _ = self.env._
        out = {NONE: _("Not filled in"), NA: "—"}
        kind = desc['type']
        Model = self.env[desc['model']]
        field = Model._fields.get(desc['field'])
        if field is None:
            return out
        raw = [str(v) for v in values if v not in (None, '', NONE, NA)]
        if kind == 'selection':
            out.update({str(k): l for k, l in field._description_selection(self.env)})
        elif kind == 'boolean':
            out.update({'true': _("Yes"), 'false': _("No")})
        elif kind == 'many2one':
            ids = [int(v) for v in raw if v.isdigit()]
            recs = self.env[field.comodel_name].sudo().with_context(
                active_test=False).browse(ids).exists()
            names = {str(r.id): r.display_name or '' for r in recs}
            out.update({v: names.get(v) or _("(removed)") for v in raw if v.isdigit()})
        elif kind == 'date':
            for v in raw:
                out[v] = self._pbfx_date_word(desc['grain'], v)
        else:
            out.update({v: v for v in raw})
        return out

    def _pbfx_date_word(self, grain, value):
        try:
            if grain == 'month':
                year, month = value.split('-')
                return self._month_words(date(int(year), int(month), 1))
            if grain == 'quarter':
                year, quarter = value.split('-Q')
                return self.env._("Q%(n)s %(year)s", n=int(quarter), year=int(year))
        except (TypeError, ValueError):
            return value
        return value

    @api.model
    def _pbx_extra_labels(self, key, values):
        desc = self._pbfx_fields().get(key)
        if not desc:
            return super()._pbx_extra_labels(key, values)
        return self._pbfx_value_words(desc, values)

    @api.model
    def _pbx_extra_options(self, key):
        """What a filter on an own field may pick from: every choice of a
        choice list, yes / no, and for text, links and dates the values the
        records in scope actually hold (never a guess, at most 200)."""
        desc = self._pbfx_fields().get(key)
        if not desc:
            return super()._pbx_extra_options(key)
        _ = self.env._
        kind = desc['type']
        if kind == 'boolean':
            return [{'value': 'true', 'label': _("Yes")},
                    {'value': 'false', 'label': _("No")}]
        if kind == 'selection':
            field = self.env[desc['model']]._fields[desc['field']]
            opts = [{'value': str(k), 'label': l}
                    for k, l in field._description_selection(self.env)]
            return opts + [{'value': NONE, 'label': _("Not filled in")}]
        table = 'hr_employee' if desc['model'] == EMPLOYEE else 'hr_contract'
        self._pbfx_flush([desc])
        value = self._pbfx_value_sql(desc, '"%s"' % desc['field'])
        self.env.cr.execute(
            "SELECT DISTINCT %s AS v FROM %s WHERE company_id IN %%s AND %s IS NOT NULL "
            "ORDER BY 1 %s LIMIT %d" % (value, table, value,
                                         'DESC' if kind == 'date' else '', OPTIONS_CAP),
            (self._co_ids(),))
        values = [r[0] for r in self.env.cr.fetchall() if r[0]]
        words = self._pbfx_value_words(desc, values)
        opts = [{'value': v, 'label': words.get(v) or v} for v in values]
        if kind == 'many2one':
            opts.sort(key=lambda o: (o['label'] or '').casefold())
        return opts + [{'value': NONE, 'label': _("Not filled in")}]
