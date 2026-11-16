# -*- coding: utf-8 -*-
"""People › Pay › Scales — the screen's server half (`pb.pay.scales`).

Reads: everybody the Pay area lets read bands (`pb.pay.bands._can_read`).
Writes: the people who may set bands (`_can_write`). Every read and write runs
under sudo AFTER that gate, inside the reader's own companies.

THE SAFETY RAIL, AGAIN: nothing on this screen writes `hr.contract` or a pay
line. Cells, grades, versions and allowances are the scale's own records;
placing or pinning somebody writes a `pb.pay.scale.placement` row. The wage
moves only through the contract's own save (the contract drawer's "Bring to
step", which then follows the contract's normal approval).
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.pb_pay.models.pb_pay_band import COUNTRIES, COUNTRY_CURRENCY

from .placement import PIN_REASONS
from .resolver import WAGE_CODES

_logger = logging.getLogger(__name__)

LIVE_STATES = ('draft', 'open')


class PbPayScalesScreen(models.AbstractModel):
    _inherit = 'pb.pay.scales'

    # ================================================================= gates
    @api.model
    def _can_read(self):
        return self._bands()._can_read()

    @api.model
    def _can_write(self):
        return self._bands()._can_write()

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_("You cannot read the pay scales."))

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_("Only the people who set pay bands can change a pay scale."))

    @api.model
    def _companies(self):
        return self._bands()._companies()

    @api.model
    def _scales(self):
        companies = self._companies()
        scales = self.env['pb.pay.scale'].sudo().search([])
        return scales.filtered(
            lambda s: not s.company_ids or any(c in companies for c in s.company_ids))

    @api.model
    def _scale(self, scale_id):
        scale = self.env['pb.pay.scale'].sudo().browse(int(scale_id or 0)).exists()
        if not scale or scale not in self._scales():
            raise UserError(_("That pay scale is no longer there."))
        return scale

    @api.model
    def _version(self, version_id):
        version = self.env['pb.pay.scale.version'].sudo().browse(
            int(version_id or 0)).exists()
        if not version:
            raise UserError(_("That version of the scale is no longer there."))
        self._scale(version.scale_id.id)
        return version

    @api.model
    def _grade(self, grade_id):
        grade = self.env['pb.pay.scale.grade'].sudo().browse(int(grade_id or 0)).exists()
        if not grade:
            raise UserError(_("That grade is no longer there."))
        self._scale(grade.scale_id.id)
        return grade

    @api.model
    def _contract(self, contract_id):
        contract = self.env['hr.contract'].sudo().browse(int(contract_id or 0)).exists()
        if not contract or contract.company_id not in self._companies():
            raise UserError(_("That contract is not one you can see."))
        return contract

    @api.model
    def _currency_dict(self, currency):
        return {'id': currency.id, 'name': currency.name or '',
                'symbol': currency.symbol or currency.name or '',
                'position': currency.position or 'after',
                'decimals': currency.decimal_places
                if currency.decimal_places is not None else 2}

    @api.model
    def _date_label(self, day):
        from odoo.tools.misc import format_date
        return format_date(self.env, day) if day else ''

    @api.model
    def _num(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValidationError(_("'%s' is not a number.", value)) from None

    # ========================================================== populations
    @api.model
    def _live_placements(self, scale):
        companies = self._companies()
        return self.env['pb.pay.scale.placement'].sudo().search([
            ('scale_id', '=', scale.id),
            ('contract_id.state', 'in', LIVE_STATES),
            ('company_id', 'in', companies.ids or [0]),
        ])

    @api.model
    def _unplaced(self, scale, day=None):
        """Running contracts whose job sits on a grade of this scale, with no
        place on any scale yet: ``[(contract, grade)]``."""
        day = self._day(day)
        companies = self._companies()
        links = self.env['pb.pay.band.job'].sudo().search(
            [('pb_scale_grade_id.scale_id', '=', scale.id)])
        by_job = {}
        for link in links:
            band = link.band_id
            if band.active and band.date_from <= day and (not band.date_to or band.date_to >= day):
                by_job.setdefault(link.job_id.id, link.pb_scale_grade_id)
        if not by_job:
            return []
        contracts = self.env['hr.contract'].sudo().search([
            ('state', '=', 'open'),
            ('company_id', 'in', companies.ids or [0]),
            '|', ('job_id', 'in', list(by_job)), ('employee_id.job_id', 'in', list(by_job)),
        ])
        placed = set(self.env['pb.pay.scale.placement'].sudo().search(
            [('contract_id', 'in', contracts.ids)]).mapped('contract_id').ids)
        out = []
        for contract in contracts:
            if contract.id in placed or not scale.serves_company(contract.company_id):
                continue
            job = contract.job_id or contract.employee_id.job_id
            grade = by_job.get(job.id)
            if grade:
                out.append((contract, grade))
        return out

    # ================================================================= board
    @api.model
    def get_scales(self, scale_id=0, version_id=0, on_date=None):
        """The Scales tab in one read."""
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'scales': [], 'scale': None,
                    'reason': _("Pay scales are for the people who look after pay. "
                                "Ask an administrator for access.")}
        scales = self._scales()
        rows = []
        for scale in scales:
            placed = self._live_placements(scale)
            rows.append({
                'id': scale.id, 'name': scale.name,
                'country': dict(COUNTRIES).get(scale.country_code, scale.country_code),
                'currency': scale.currency_id.name or '',
                'grades': len(scale.grade_ids), 'steps': scale.step_count,
                'people': len(placed),
                'drifted': sum(1 for p in placed if p.state == 'drifted'),
            })
        chosen = None
        if scales:
            pick = scales.filtered(lambda s: s.id == int(scale_id or 0))[:1] or scales[:1]
            chosen = self._scale_detail(pick, version_id, on_date)
        return {
            'allowed': True, 'can_write': self._can_write(), 'scales': rows,
            'scale': chosen,
            'countries': [{'code': c, 'name': n} for c, n in COUNTRIES],
            'families': [{'id': f.id, 'name': f.name} for f in
                         self.env['pb.pay.family'].sudo().search([])],
            'companies': [{'id': c.id, 'name': c.name} for c in self._companies()],
            'country_currency': COUNTRY_CURRENCY,
            'pin_reasons': self._pin_reasons(),
            'today': fields.Date.to_string(fields.Date.context_today(self)),
        }

    @api.model
    def _pin_reasons(self):
        labels = dict(self.env['pb.pay.scale.placement']._fields['pin_reason']
                      ._description_selection(self.env))
        return [{'value': v, 'label': labels.get(v, v)} for v, _l in PIN_REASONS]

    @api.model
    def _scale_detail(self, scale, version_id=0, on_date=None):
        today = fields.Date.context_today(self)
        versions = scale.version_ids.sorted('date_from')
        version = versions.filtered(lambda v: v.id == int(version_id or 0))[:1]
        if not version:
            version = scale.version_on(self._day(on_date)) or versions[-1:] if versions else versions
        currency = scale.currency_id
        placed = self._live_placements(scale)
        counts, states = {}, {'on': 0, 'pinned': 0, 'drifted': 0}
        for row in placed:
            key = (row.grade_id.id, row.step_no)
            counts[key] = counts.get(key, 0) + 1
            states[row.state] = states.get(row.state, 0) + 1
        unplaced = self._unplaced(scale)
        match = 0
        current = scale.version_on(today)
        for contract, grade in unplaced:
            if current and any(self._same(current.value_of(grade, s), contract.wage,
                                          scale.decimals())
                               for s in range(1, scale.step_count + 1)):
                match += 1
        grades = []
        for grade in scale.grade_ids.sorted(lambda g: (g.sequence, g.id)):
            cells = []
            for step in range(1, scale.step_count + 1):
                cell = version.cell_for(grade, step) if version else None
                cells.append({
                    'step': step,
                    'id': cell.id if cell else 0,
                    'amount': cell.amount if cell else 0.0,
                    'coefficient': cell.coefficient if cell else 0.0,
                    'value': cell.value if cell else 0.0,
                    'label': self._money(cell.value, currency) if cell and cell.value else '',
                    'people': counts.get((grade.id, step), 0),
                })
            package = []
            if version:
                for line in version.package_ids.filtered(lambda p, g=grade: p.grade_id == g):
                    package.append({'id': line.id, 'template_id': line.template_id.id,
                                    'code': line.template_id.code or '',
                                    'name': line.template_id.name or '',
                                    'amount': line.amount,
                                    'label': self._money(line.amount, currency)})
            grades.append({
                'id': grade.id, 'name': grade.name, 'sequence': grade.sequence,
                'band': {'id': grade.band_id.id, 'name': grade.band_id.name}
                if grade.band_id else None,
                'jobs': [{'link_id': l.id, 'job_id': l.job_id.id,
                          'name': l.job_id.display_name} for l in grade.job_link_ids],
                'people': sum(counts.get((grade.id, s), 0)
                              for s in range(1, scale.step_count + 1)),
                'cells': cells, 'package': package,
            })
        return {
            'id': scale.id, 'name': scale.name, 'country_code': scale.country_code,
            'country': dict(COUNTRIES).get(scale.country_code, scale.country_code),
            'currency': self._currency_dict(currency),
            'mode': scale.mode, 'step_count': scale.step_count,
            'rounding': scale.rounding, 'note': scale.note or '',
            'family_id': scale.family_id.id or 0,
            'company_ids': scale.company_ids.ids,
            'companies_label': ', '.join(scale.company_ids.mapped('name'))
            or _("Every company in %(country)s",
                 country=dict(COUNTRIES).get(scale.country_code, '')),
            'versions': [{
                'id': v.id, 'date_from': fields.Date.to_string(v.date_from),
                'date_to': fields.Date.to_string(v.date_to) if v.date_to else '',
                'label': self._version_label(v),
                'current': bool(current and v == current),
                'ended': v.has_ended(), 'future': v.date_from > today,
            } for v in versions],
            'version': {
                'id': version.id, 'date_from': fields.Date.to_string(version.date_from),
                'label': self._version_label(version),
                'base_rate': version.base_rate, 'ended': version.has_ended(),
                'editable': not version.has_ended(),
                'number': list(versions).index(version) + 1,
            } if version else None,
            'version_count': len(versions),
            'grades': grades,
            'health': {
                'on': states.get('on', 0), 'pinned': states.get('pinned', 0),
                'drifted': states.get('drifted', 0), 'unplaced': len(unplaced),
                'match': match, 'people': len(placed),
            },
            'wire': self._wire(placed),
        }

    @api.model
    def _version_label(self, version):
        if version.date_to:
            return _("%(start)s to %(end)s", start=self._date_label(version.date_from),
                     end=self._date_label(version.date_to))
        return _("In force from %(start)s", start=self._date_label(version.date_from))

    # ============================================================ wire check
    @api.model
    def _wire(self, placements):
        """Does the wage on the contract reach the payslip of each scheme that
        pays people on this scale? One sentence per scheme."""
        Employee = self.env['hr.employee']
        if 'pb_paid_by_id' not in Employee._fields:
            return []
        configs = placements.mapped('employee_id').sudo().mapped('pb_paid_by_id')
        out = []
        for config in configs[:8]:
            out.append(self._wire_one(config))
        return out

    @api.model
    def _wire_one(self, config):
        config = config.sudo()
        name = config.display_name or config.name or ''
        rules = config.rule_ids.filtered(
            lambda r: r.column_type == 'input' and (r.code or '').upper() in WAGE_CODES)
        if not rules:
            return {'scheme': name, 'tone': 'warn', 'sentence': _(
                "%(scheme)s has no basic pay item filled from the contract wage, "
                "so the scale amount does not reach its payslips.", scheme=name)}
        rank = ()
        try:
            rank = config._source_kind_rank()
        except Exception:       # noqa: BLE001 — older engine
            rank = ()
        excel_first = 'excel' in rank and 'contract_field' in rank \
            and rank.index('excel') < rank.index('contract_field') \
            and getattr(config, 'source_excel_enabled', True)
        if excel_first:
            return {'scheme': name, 'tone': 'info', 'sentence': _(
                "%(scheme)s reads basic pay from the contract. When a pay data "
                "file is loaded, the file's basic pay wins over it.", scheme=name)}
        return {'scheme': name, 'tone': 'ok', 'sentence': _(
            "%(scheme)s reads basic pay from the contract, so the scale reaches "
            "the payslip.", scheme=name)}

    # ================================================================ writes
    @api.model
    def save_scale(self, scale_id=0, vals=None):
        self._require_write()
        vals = dict(vals or {})
        out = {}
        for key in ('name', 'note'):
            if key in vals:
                out[key] = (vals.get(key) or '').strip()
        if 'country_code' in vals:
            if vals['country_code'] not in dict(COUNTRIES):
                raise ValidationError(_("Pick a country."))
            out['country_code'] = vals['country_code']
        if vals.get('currency'):
            currency = self.env['res.currency'].sudo().with_context(
                active_test=False).search([('name', '=', vals['currency'])], limit=1)
            if currency:
                out['currency_id'] = currency.id
        for key in ('step_count',):
            if key in vals:
                out[key] = int(vals[key] or 1)
        if 'rounding' in vals:
            out['rounding'] = self._num(vals.get('rounding') or 0)
        if 'mode' in vals and vals['mode'] in ('amount', 'coefficient'):
            out['mode'] = vals['mode']
        if 'family_id' in vals:
            out['family_id'] = int(vals['family_id'] or 0) or False
        if 'company_ids' in vals:
            allowed = self._companies()
            ids = [int(c) for c in (vals.get('company_ids') or [])
                   if int(c) in allowed.ids]
            out['company_ids'] = [(6, 0, ids)]
        Scale = self.env['pb.pay.scale'].sudo()
        if scale_id:
            scale = self._scale(scale_id)
            if 'step_count' in out and out['step_count'] < scale.step_count:
                if self.env['pb.pay.scale.placement'].sudo().search_count([
                        ('scale_id', '=', scale.id), ('step_no', '>', out['step_count'])]):
                    raise UserError(_("People are placed on the steps you are taking "
                                      "away. Move them first."))
                self.env['pb.pay.scale.cell'].sudo().search([
                    ('scale_id', '=', scale.id),
                    ('step_no', '>', out['step_count'])]).unlink()
            scale.write(out)
        else:
            if not out.get('name'):
                raise ValidationError(_("A pay scale needs a name."))
            if not out.get('country_code'):
                raise ValidationError(_("Pick a country."))
            if 'currency_id' not in out:
                code = COUNTRY_CURRENCY.get(out['country_code'])
                currency = self.env['res.currency'].sudo().with_context(
                    active_test=False).search([('name', '=', code)], limit=1)
                out['currency_id'] = (currency or self.env.company.currency_id).id
            scale = Scale.create(out)
            start = self._day(vals.get('date_from')) if vals.get('date_from') \
                else fields.Date.context_today(self).replace(day=1)
            self.env['pb.pay.scale.version'].sudo().create(
                {'scale_id': scale.id, 'date_from': start})
            for index, name in enumerate(vals.get('grades') or []):
                name = (name or '').strip()
                if name:
                    self.env['pb.pay.scale.grade'].sudo().create(
                        {'scale_id': scale.id, 'name': name, 'sequence': (index + 1) * 10})
        return {'ok': True, 'scale_id': scale.id}

    @api.model
    def remove_scale(self, scale_id):
        self._require_write()
        scale = self._scale(scale_id)
        if self.env['pb.pay.scale.placement'].sudo().search_count([('scale_id', '=', scale.id)]):
            raise UserError(_("People are placed on this scale. Take them off it "
                              "first, or keep the scale."))
        scale.unlink()
        return {'ok': True}

    @api.model
    def save_grade(self, scale_id, grade_id=0, vals=None):
        self._require_write()
        scale = self._scale(scale_id)
        vals = dict(vals or {})
        out = {}
        if 'name' in vals:
            out['name'] = (vals.get('name') or '').strip()
        if 'sequence' in vals:
            out['sequence'] = int(vals.get('sequence') or 10)
        if 'band_id' in vals:
            band = self.env['pb.pay.band'].sudo().browse(int(vals['band_id'] or 0)).exists()
            if band and band.country_code != scale.country_code:
                raise ValidationError(_("That band is for another country."))
            out['band_id'] = band.id or False
        if grade_id:
            grade = self._grade(grade_id)
            grade.write(out)
        else:
            if 'sequence' not in out:
                out['sequence'] = (max(scale.grade_ids.mapped('sequence') or [0]) + 10)
            out['scale_id'] = scale.id
            grade = self.env['pb.pay.scale.grade'].sudo().create(out)
        return {'ok': True, 'grade_id': grade.id}

    @api.model
    def remove_grade(self, grade_id):
        self._require_write()
        self._grade(grade_id).unlink()
        return {'ok': True}

    @api.model
    def move_grade(self, grade_id, direction):
        self._require_write()
        grade = self._grade(grade_id)
        grades = grade.scale_id.grade_ids.sorted(lambda g: (g.sequence, g.id))
        order = list(grades)
        index = order.index(grade)
        other = index - 1 if direction == 'up' else index + 1
        if 0 <= other < len(order):
            order[index], order[other] = order[other], order[index]
        for position, row in enumerate(order):
            row.sequence = (position + 1) * 10
        return {'ok': True}

    @api.model
    def save_cells(self, version_id, cells=None, base_rate=None):
        """Write cell amounts (or coefficients). Writes NO contract."""
        self._require_write()
        version = self._version(version_id)
        if version.has_ended():
            raise UserError(_("This version has ended. It is kept exactly as it "
                              "was; make a new version instead."))
        scale = version.scale_id
        Cell = self.env['pb.pay.scale.cell'].sudo()
        if base_rate is not None:
            version.base_rate = self._num(base_rate)
        grades = {g.id: g for g in scale.grade_ids}
        written = 0
        for row in cells or []:
            grade = grades.get(int(row.get('grade_id') or 0))
            step = int(row.get('step') or 0)
            if not grade or not 1 <= step <= scale.step_count:
                continue
            vals = {}
            if scale.mode == 'coefficient':
                vals['coefficient'] = self._num(row.get('coefficient') or 0)
            else:
                vals['amount'] = scale.round_amount(self._num(row.get('amount') or 0))
            cell = version.cell_for(grade, step)
            if cell:
                cell.write(vals)
            else:
                vals.update(version_id=version.id, grade_id=grade.id, step_no=step)
                Cell.create(vals)
            written += 1
        return {'ok': True, 'written': written}

    @api.model
    def new_version(self, scale_id, date_from, grow_pct=0.0):
        """A new dated version, copied from the latest one (optionally grown
        by a percentage). The previous open-ended version ends the day before.
        Writes NO contract: people on the scale read "Drifted" from that day
        until somebody brings their pay to the new step."""
        self._require_write()
        scale = self._scale(scale_id)
        start = self._day(date_from)
        versions = scale.version_ids.sorted('date_from')
        last = versions[-1:] if versions else versions
        if last and start <= last.date_from:
            raise UserError(_("A new version must start after %(day)s, when the "
                              "latest one starts.", day=self._date_label(last.date_from)))
        grow = 1.0 + (self._num(grow_pct or 0) / 100.0)
        if grow <= 0:
            raise ValidationError(_("A scale cannot shrink by that much."))
        Version = self.env['pb.pay.scale.version'].sudo()
        if last and not last.date_to:
            last.date_to = start - timedelta(days=1)
        new = Version.create({'scale_id': scale.id, 'date_from': start,
                              'base_rate': (last.base_rate or 0.0) * (grow if scale.mode == 'coefficient' else 1.0)
                              if last else 0.0})
        if last:
            for cell in last.cell_ids:
                vals = {'version_id': new.id, 'grade_id': cell.grade_id.id,
                        'step_no': cell.step_no, 'coefficient': cell.coefficient}
                vals['amount'] = scale.round_amount(cell.amount * grow) \
                    if scale.mode == 'amount' else cell.amount
                self.env['pb.pay.scale.cell'].sudo().create(vals)
            for line in last.package_ids:
                self.env['pb.pay.scale.package'].sudo().create({
                    'version_id': new.id, 'grade_id': line.grade_id.id,
                    'template_id': line.template_id.id, 'amount': line.amount})
        return {'ok': True, 'version_id': new.id}

    @api.model
    def remove_version(self, version_id):
        self._require_write()
        version = self._version(version_id)
        today = fields.Date.context_today(self)
        if version.date_from <= today:
            raise UserError(_("Only a version that has not started yet can be removed."))
        scale = version.scale_id
        before = scale.version_ids.filtered(lambda v: v.date_from < version.date_from) \
            .sorted('date_from')[-1:]
        version.unlink()
        if before and before.date_to:
            before.date_to = False
        return {'ok': True}

    @api.model
    def save_package(self, version_id, grade_id, lines=None):
        self._require_write()
        version = self._version(version_id)
        if version.has_ended():
            raise UserError(_("This version has ended. It is kept exactly as it was."))
        grade = self._grade(grade_id)
        Package = self.env['pb.pay.scale.package'].sudo()
        Template = self.env['hr.contract.advantage.template'].sudo()
        keep = []
        for row in lines or []:
            template = Template.browse(int(row.get('template_id') or 0)).exists()
            if not template:
                continue
            amount = self._num(row.get('amount') or 0)
            line = Package.search([('version_id', '=', version.id),
                                   ('grade_id', '=', grade.id),
                                   ('template_id', '=', template.id)], limit=1)
            if line:
                line.amount = amount
            else:
                line = Package.create({'version_id': version.id, 'grade_id': grade.id,
                                       'template_id': template.id, 'amount': amount})
            keep.append(line.id)
        Package.search([('version_id', '=', version.id), ('grade_id', '=', grade.id),
                        ('id', 'not in', keep or [0])]).unlink()
        return {'ok': True}

    @api.model
    def lookup_templates(self, term=''):
        self._require_read()
        domain = ['|', ('name', 'ilike', term or ''), ('code', 'ilike', term or '')] \
            if term else []
        rows = self.env['hr.contract.advantage.template'].sudo().search(domain, limit=20)
        return [{'id': r.id, 'code': r.code or '', 'name': r.name or r.code or ''}
                for r in rows]

    # ================================================================== jobs
    @api.model
    def jobs_for_grade(self, grade_id, term=''):
        """Jobs that may sit on this grade: jobs in a band of the scale's
        country (the link the grade is stored on)."""
        self._require_read()
        grade = self._grade(grade_id)
        domain = [('band_id.country_code', '=', grade.scale_id.country_code),
                  ('band_id.active', '=', True)]
        if term:
            domain.append(('job_id.name', 'ilike', term))
        links = self.env['pb.pay.band.job'].sudo().search(domain, limit=40)
        return [{'link_id': l.id, 'name': l.job_id.display_name,
                 'band': l.band_id.name or '',
                 'grade': l.pb_scale_grade_id.name if l.pb_scale_grade_id else '',
                 'here': l.pb_scale_grade_id == grade} for l in links]

    @api.model
    def jobs_without_band(self, grade_id):
        """How many jobs cannot be put on this grade yet (not in any band)."""
        self._require_read()
        self._grade(grade_id)
        companies = self._companies()
        banded = set(self.env['pb.pay.band.job'].sudo().search([]).mapped('job_id').ids)
        jobs = self.env['hr.job'].sudo().search([('company_id', 'in', companies.ids + [False])])
        return {'count': len([j for j in jobs if j.id not in banded])}

    @api.model
    def link_job(self, grade_id, link_id):
        self._require_write()
        grade = self._grade(grade_id)
        link = self.env['pb.pay.band.job'].sudo().browse(int(link_id or 0)).exists()
        if not link:
            raise UserError(_("That job is no longer in a band."))
        link.pb_scale_grade_id = grade.id
        return {'ok': True}

    @api.model
    def unlink_job(self, link_id):
        self._require_write()
        link = self.env['pb.pay.band.job'].sudo().browse(int(link_id or 0)).exists()
        if link and link.pb_scale_grade_id:
            self._grade(link.pb_scale_grade_id.id)
            link.pb_scale_grade_id = False
        return {'ok': True}

    # ============================================== start from what you pay
    @api.model
    def propose_from_wages(self, scale_id):
        """A suggestion for empty cells, from the wages people on each grade's
        jobs are paid today (median for one step; lower to upper quartile
        spread across steps). Saves nothing."""
        self._require_read()
        scale = self._scale(scale_id)
        companies = self._companies()
        cells, people = [], 0
        for grade in scale.grade_ids:
            jobs = grade.job_link_ids.mapped('job_id')
            if not jobs:
                continue
            contracts = self.env['hr.contract'].sudo().search([
                ('state', '=', 'open'), ('company_id', 'in', companies.ids or [0]),
                '|', ('job_id', 'in', jobs.ids), ('employee_id.job_id', 'in', jobs.ids)])
            wages = sorted(c.wage for c in contracts
                           if c.wage and scale.serves_company(c.company_id))
            if not wages:
                continue
            people += len(wages)
            steps = scale.step_count or 1

            def quantile(q):
                pos = (len(wages) - 1) * q
                low = int(pos)
                high = min(low + 1, len(wages) - 1)
                return wages[low] + (wages[high] - wages[low]) * (pos - low)
            if steps == 1:
                points = [quantile(0.5)]
            else:
                lo, hi = quantile(0.25), quantile(0.75)
                if hi <= lo:
                    hi = lo * (1 + 0.04 * (steps - 1))
                points = [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]
            for step, value in enumerate(points, start=1):
                cells.append({'grade_id': grade.id, 'step': step,
                              'amount': scale.round_amount(value)})
        if not cells:
            return {'ok': False, 'cells': [], 'sentence': _(
                "Nobody on these grades' jobs is paid yet, so there is nothing to "
                "start from. Put jobs on the grades first.")}
        return {'ok': True, 'cells': cells, 'sentence': _(
            "Suggested from what %(people)s on these jobs are paid today. Nothing "
            "is saved until you save the table.",
            people=self._bands()._people_phrase(people))}

    # ============================================================ the people
    @api.model
    def people(self, scale_id, grade_id=0, step=0, state=''):
        self._require_read()
        scale = self._scale(scale_id)
        currency = scale.currency_id
        rows = []
        if state == 'unplaced':
            today = fields.Date.context_today(self)
            current = scale.version_on(today)
            for contract, grade in self._unplaced(scale)[:300]:
                if grade_id and grade.id != int(grade_id):
                    continue
                match = 0
                if current:
                    for s in range(1, scale.step_count + 1):
                        if self._same(current.value_of(grade, s), contract.wage,
                                      scale.decimals()):
                            match = s
                            break
                rows.append(self._person_row(contract, grade, match, 'unplaced', currency,
                                             _("Not placed yet") if not match else
                                             _("Paid exactly step %(step)s", step=match)))
            return {'rows': rows, 'state': state}
        placements = self._live_placements(scale)
        if grade_id:
            placements = placements.filtered(lambda p: p.grade_id.id == int(grade_id))
        if step:
            placements = placements.filtered(lambda p: p.step_no == int(step))
        if state:
            placements = placements.filtered(lambda p: p.state == state)
        for row in placements[:300]:
            line = row.label()
            if row.state == 'drifted':
                line = _("Scale says %(scale)s, paid %(paid)s",
                         scale=self._money(row.scale_amount, currency),
                         paid=self._money(row.contract_id.wage, currency))
            rows.append(self._person_row(row.contract_id, row.grade_id, row.step_no,
                                         row.state, currency, line))
        return {'rows': rows, 'state': state}

    @api.model
    def _person_row(self, contract, grade, step, state, currency, line):
        employee = contract.employee_id
        return {
            'contract_id': contract.id, 'employee_id': employee.id,
            'name': employee.name or contract.name or '',
            'job': (contract.job_id or employee.job_id).display_name or '',
            'grade': grade.name, 'step': step, 'state': state,
            'wage': self._money(contract.wage, currency), 'line': line,
        }

    @api.model
    def place_matching(self, scale_id):
        """Place every not-yet-placed person whose wage IS a step today.
        Writes placements only — never a contract."""
        self._require_write()
        scale = self._scale(scale_id)
        current = scale.version_on(fields.Date.context_today(self))
        if not current:
            return {'ok': False, 'placed': 0,
                    'msg': _("The scale has no amounts in force today.")}
        Placement = self.env['pb.pay.scale.placement'].sudo()
        placed = 0
        for contract, grade in self._unplaced(scale):
            for step in range(1, scale.step_count + 1):
                if self._same(current.value_of(grade, step), contract.wage, scale.decimals()):
                    Placement.create({'contract_id': contract.id, 'grade_id': grade.id,
                                      'step_no': step, 'source': 'match'})
                    placed += 1
                    break
        return {'ok': True, 'placed': placed, 'msg': _(
            "%(people)s placed on the step they are already paid. Nobody's pay changed.",
            people=self._bands()._people_phrase(placed))}

    @api.model
    def place(self, contract_id, grade_id, step):
        """Put a contract on (grade, step). Writes the placement only."""
        self._require_write()
        contract = self._contract(contract_id)
        grade = self._grade(grade_id)
        if not grade.scale_id.serves_company(contract.company_id):
            raise UserError(_("This scale is not used by %(company)s.",
                              company=contract.company_id.name))
        Placement = self.env['pb.pay.scale.placement'].sudo()
        row = Placement.search([('contract_id', '=', contract.id)], limit=1)
        vals = {'grade_id': grade.id, 'step_no': int(step or 1), 'pinned': False,
                'pin_reason': False, 'pin_note': False, 'source': 'hand',
                'placed_on': fields.Date.context_today(self),
                'placed_by': self.env.uid}
        if row:
            row.write(vals)
        else:
            vals['contract_id'] = contract.id
            row = Placement.create(vals)
        return {'ok': True, 'state': row.state, 'label': row.label()}

    @api.model
    def keep_unplaced(self, contract_id, grade_id):
        """A person whose pay is no step: put them on step 1 of the grade,
        pinned "Paid this before the scale". Placement only, never the pay."""
        self.place(contract_id, grade_id, 1)
        return self.pin(contract_id, 'legacy')

    @api.model
    def pin(self, contract_id, reason, note=''):
        self._require_write()
        contract = self._contract(contract_id)
        if reason not in dict(PIN_REASONS):
            raise ValidationError(_("Pick why this pay is different from the scale."))
        row = self.env['pb.pay.scale.placement'].sudo().search(
            [('contract_id', '=', contract.id)], limit=1)
        if not row:
            raise UserError(_("Put this person on a grade and step first."))
        row.write({'pinned': True, 'pin_reason': reason, 'pin_note': (note or '').strip() or False})
        return {'ok': True, 'state': row.state, 'label': row.label()}

    @api.model
    def unpin(self, contract_id):
        self._require_write()
        contract = self._contract(contract_id)
        row = self.env['pb.pay.scale.placement'].sudo().search(
            [('contract_id', '=', contract.id)], limit=1)
        if row:
            row.write({'pinned': False, 'pin_reason': False, 'pin_note': False})
        return {'ok': True}

    @api.model
    def unplace(self, contract_id):
        self._require_write()
        contract = self._contract(contract_id)
        self.env['pb.pay.scale.placement'].sudo().search(
            [('contract_id', '=', contract.id)]).unlink()
        return {'ok': True}

    # ====================================================== joiner suggestion
    @api.model
    def joiner_suggest(self, employee_id=0, job_id=0, date_start=None, company_id=0,
                       wage=None):
        """What the hire screen shows under the wage box. Read-only."""
        user = self.env.user
        if not (user.has_group('hr.group_hr_user') or self._can_read()):
            return {'found': False, 'why': ''}
        employee = self.env['hr.employee'].sudo().browse(int(employee_id or 0)).exists()
        job = self.env['hr.job'].sudo().browse(int(job_id or 0)).exists() \
            or (employee.job_id if employee else self.env['hr.job'])
        company = self.env['res.company'].sudo().browse(int(company_id or 0)).exists() \
            or (employee.company_id if employee else self.env.company)
        answer = self.resolve(job, company, date_start, employee or None)
        out = {'found': answer['found'], 'why': answer['why'] or '',
               'amount': answer['amount'], 'sentence': answer['sentence'],
               'steps': answer['steps'], 'reasons': self._pin_reasons(),
               # A job on a grade whose scale cannot be used says why, quietly.
               'show_why': bool(answer['grade']) and not answer['found'],
               'grade': answer['grade'].name if answer['grade'] else '',
               'scale': answer['scale'].name if answer['scale'] else ''}
        if answer['found'] and wage not in (None, '', False):
            try:
                typed = float(wage)
            except (TypeError, ValueError):
                typed = 0.0
            step = self.step_matching(answer, typed)
            out['typed_step'] = step
            out['typed_off'] = bool(typed > 0 and not step)
        return out

    # ===================================================== the contract chip
    @api.model
    def contract_chip(self, contract_id):
        """The chip the contract drawer and the employee panel show, or None."""
        if not self._can_read():
            return None
        contract = self.env['hr.contract'].sudo().browse(int(contract_id or 0)).exists()
        if not contract:
            return None
        row = self.env['pb.pay.scale.placement'].sudo().search(
            [('contract_id', '=', contract.id)], limit=1)
        currency = row.scale_id.currency_id if row else contract.company_id.currency_id
        if row:
            chip = {'key': 'pay_scale', 'icon': 'layers', 'label': row.label(),
                    'tone': {'on': 'ok', 'pinned': 'muted', 'drifted': 'warn'}.get(row.state, 'muted'),
                    'title': _("%(grade)s, step %(step)s of %(scale)s",
                               grade=row.grade_id.name, step=row.step_no,
                               scale=row.scale_id.name)}
            if row.state == 'drifted' and row.scale_amount:
                chip['title'] = _("The scale says %(scale)s; this contract pays %(paid)s.",
                                  scale=self._money(row.scale_amount, currency),
                                  paid=self._money(contract.wage, currency))
                chip['stage_wage'] = row.scale_amount
                chip['stage_label'] = _("Bring to step")
            if row.state == 'pinned' and row.pin_note:
                chip['title'] = row.pin_note
            if self._can_write() and row.state == 'drifted':
                chip['action'] = {'model': 'pb.pay.scales', 'method': 'pin_from_drawer',
                                  'args': [contract.id], 'label': _("Keep this pay")}
            return chip
        # Not placed: say so only when the job is on a grade of a scale.
        job = contract.job_id or contract.employee_id.job_id
        grade = self._grade_for_job(job, None, contract.company_id)
        if not grade:
            return None
        version = grade.scale_id.version_on()
        match = 0
        if version:
            for step in range(1, grade.scale_id.step_count + 1):
                if self._same(version.value_of(grade, step), contract.wage,
                              grade.scale_id.decimals()):
                    match = step
                    break
        chip = {'key': 'pay_scale', 'icon': 'layers', 'tone': 'muted',
                'label': _("Not on the scale yet · %(grade)s", grade=grade.name),
                'title': _("%(job)s sits on %(grade)s of %(scale)s.",
                           job=job.display_name, grade=grade.name,
                           scale=grade.scale_id.name)}
        if match and self._can_write():
            chip['action'] = {'model': 'pb.pay.scales', 'method': 'place',
                              'args': [contract.id, grade.id, match],
                              'label': _("Mark on step %(step)s", step=match)}
        elif version and version.value_of(grade, 1) and self._can_write() \
                and contract.state in LIVE_STATES:
            chip['stage_wage'] = version.value_of(grade, 1)
            chip['stage_label'] = _("Use step 1")
        return chip

    @api.model
    def pin_from_drawer(self, contract_id):
        """"Keep this pay" on a drifted contract: pinned, reason Other."""
        return self.pin(contract_id, 'other', _("Kept from the contract"))

    @api.model
    def employee_chip(self, employee_id):
        employee = self.env['hr.employee'].sudo().browse(int(employee_id or 0)).exists()
        if not employee:
            return {'found': False}
        contract = self.env['hr.contract'].sudo().search(
            [('employee_id', '=', employee.id), ('state', 'in', LIVE_STATES)],
            order='state desc, date_start desc', limit=1)
        chip = self.contract_chip(contract.id) if contract else None
        if not chip:
            return {'found': False}
        chip['found'] = True
        chip['contract_id'] = contract.id
        return chip
