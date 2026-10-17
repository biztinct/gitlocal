"""Draft, reconcile, then publish holidays to the existing working calendar."""
import json
from pathlib import Path
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

KINDS = [('public', 'Public / festival holiday'), ('collective', 'Collective leave'), ('company', 'Company holiday')]


class CalendarHoliday(models.Model):
    _inherit = 'resource.calendar.leaves'
    pb_holiday_kind = fields.Selection(KINDS, string='Holiday category', default='public')
    pb_holiday_batch_id = fields.Many2one('pb.holiday.batch', string='Published import', readonly=True, ondelete='restrict')


class HolidayBatch(models.Model):
    _name = 'pb.holiday.batch'
    _description = 'Holiday calendar version'
    _inherit = ['mail.thread']
    _order = 'id desc'
    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    year = fields.Integer(required=True)
    source = fields.Char(required=True)
    rows_json = fields.Json(required=True)
    state = fields.Selection([('draft', 'In review'), ('published', 'Published')], default='draft', readonly=True, tracking=True)
    published_by = fields.Many2one('res.users', readonly=True)
    published_on = fields.Datetime(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('state', 'draft') != 'draft' for vals in vals_list):
            raise UserError(_('Create a draft before publishing a calendar version.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            if set(vals) & {'state', 'published_by', 'published_on'}:
                raise AccessError(_('Use Publish to release a calendar version.'))
            if any(b.state == 'published' for b in self):
                raise UserError(_('Published calendar versions are archived evidence. Create a new draft for changes.'))
        return super().write(vals)

    def unlink(self):
        if any(b.state == 'published' for b in self):
            raise UserError(_('Published calendar versions cannot be deleted.'))
        return super().unlink()


class HolidayPolicyNote(models.Model):
    _name = 'pb.holiday.policy.note'
    _description = 'Leave policy reference'
    _order = 'sequence, id'
    name = fields.Char('Leave category', required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    country = fields.Char(required=True)
    entitlement = fields.Text(required=True)
    carry_rule = fields.Text('Carry-forward / policy note')
    source = fields.Char()
    reviewed = fields.Boolean('HR reviewed')


class HolidayJourney(models.AbstractModel):
    _inherit = 'pb.holidays'

    def _company_for_write(self, company_id):
        if int(company_id or 0) not in self.env.companies.ids:
            raise AccessError(_('Switch to an allowed company before changing its calendar.'))
        return super()._company_for_write(company_id)

    def _column(self, company, first, last, today):
        data = super()._column(company, first, last, today)
        if data:
            leaves = self.env['resource.calendar.leaves'].sudo().browse([r['id'] for r in data['rows']])
            info = {r.id: (r.pb_holiday_kind, r.pb_holiday_batch_id.source) for r in leaves}
            for row in data['rows']:
                kind, source = info.get(row['id'], ('public', ''))
                row.update(kind=kind or 'public', source=source or '')
        return data

    @api.model
    def import_workspace(self, year):
        batches = self.env['pb.holiday.batch'].search([('company_id', 'in', self.env.companies.ids), ('year', '=', int(year))], limit=40)
        return {'batches': [{'id': b.id, 'name': b.name, 'company': b.company_id.name, 'state': b.state,
                            'source': b.source, 'rows': b.rows_json or [], 'published_on': str(b.published_on or '')} for b in batches],
                'policies': self.env['pb.holiday.policy.note'].search_read([('company_id', 'in', self.env.companies.ids)],
                    ['name', 'country', 'entitlement', 'carry_rule', 'reviewed', 'source'], limit=300),
                'can_source': self.env.cr.dbname == 'rize'}

    @api.model
    def prepare_import(self, company_id, year, source, lines_text=None, use_source=False):
        company, calendar = self._company_for_write(company_id)
        year = int(year)
        if not 2000 <= year <= 2200 or not str(source or '').strip():
            raise UserError(_('Add a source and a calendar year between 2000 and 2200.'))
        parsed = []
        if use_source:
            if self.env.cr.dbname != 'rize' or year != 2026:
                raise UserError(_('The supplied reference workbook is for Rize’s 2026 review.'))
            original = json.loads((Path(__file__).parent.parent / 'data/holiday_reference.json').read_text())
            countries = {'ID': 'Indonesia', 'VN': 'Vietnam', 'SG': 'Singapore', 'IN': 'India'}
            country = countries.get(company.country_id.code)
            for row in original:
                if row['country'] == country:
                    parsed.append({'name': row['name'], 'date': row['date'], 'date_to': row['date'],
                                   'kind': 'collective' if 'collective' in row['type'].lower() else 'public',
                                   'conflict': bool(row['conflict']),
                                   'issue': 'Missing from the combined sheet; review against the country sheet.' if row['conflict'] else ''})
        else:
            if len(lines_text or '') > 200000:
                raise UserError(_('Import up to 500 holidays at a time.'))
            for number, raw in enumerate((lines_text or '').splitlines(), 1):
                if not raw.strip():
                    continue
                bits = [b.strip() for b in raw.split('|')]
                if len(bits) < 2 or not bits[0]:
                    raise UserError(_('Line %s: use Name | YYYY-MM-DD | optional end date | public, collective or company.', number))
                start = self._parse_day(bits[1])
                end = self._parse_day(bits[2]) if len(bits) > 2 and bits[2] else start
                kind = bits[3].lower() if len(bits) > 3 and bits[3] else 'public'
                if end < start or start.year != year or end.year != year or kind not in dict(KINDS):
                    raise UserError(_('Line %s: check dates, selected year and holiday category.', number))
                parsed.append({'name': bits[0][:200], 'date': str(start), 'date_to': str(end), 'kind': kind, 'conflict': False, 'issue': ''})
        if not parsed or len(parsed) > 500:
            raise UserError(_('Provide between 1 and 500 holidays for this company and year.'))
        seen = set()
        for index, row in enumerate(parsed):
            row['id'] = index
            key = (row['date'], row['date_to'])
            if key in seen:
                row.update(conflict=True, issue='Another imported row uses these dates. Include only the intended holiday.')
            seen.add(key)
            lower, upper = self._bounds(self._parse_day(row['date']), self._parse_day(row['date_to']), self._tz(calendar, company))
            existing = self.env['resource.calendar.leaves'].sudo().search([
                ('company_id', '=', company.id), ('resource_id', '=', False),
                ('date_from', '<=', upper), ('date_to', '>=', lower)], limit=1)
            if existing:
                row.update(conflict=True, issue='Calendar already contains: ' + existing.name)
            row['decision'] = 'review' if row['conflict'] or row['kind'] == 'collective' else 'include'
            if row['kind'] == 'collective' and not row['issue']:
                row['issue'] = 'Confirm whether collective leave should block working time for this entity.'
        batch = self.env['pb.holiday.batch'].create({'name': '%s · %s' % (company.name, year),
            'company_id': company.id, 'year': year, 'source': str(source).strip()[:500], 'rows_json': parsed})
        return {'id': batch.id, 'rows': parsed, 'name': batch.name, 'source': batch.source, 'state': 'draft'}

    @api.model
    def resolve_import(self, batch_id, decisions):
        self.env['pb.timeoff']._require_officer()
        batch = self.env['pb.holiday.batch'].browse(int(batch_id)).exists()
        batch.check_access('write')
        self._company_for_write(batch.company_id.id)
        if batch.state != 'draft':
            raise UserError(_('This version has already been published.'))
        rows = [dict(row) for row in batch.rows_json]
        for row in rows:
            decision = decisions.get(str(row['id']), row['decision'])
            if decision not in ('include', 'skip', 'review'):
                raise UserError(_('Choose Include, Skip or Review.'))
            row['decision'] = decision
        batch.write({'rows_json': rows})
        return {'rows': rows}

    @api.model
    def publish_import(self, batch_id):
        self.env['pb.timeoff']._require_officer()
        batch = self.env['pb.holiday.batch'].browse(int(batch_id)).exists()
        batch.check_access('write')
        company, calendar = self._company_for_write(batch.company_id.id)
        # Serialize publication, so a double click cannot publish a version twice.
        self.env.cr.execute('SELECT id FROM pb_holiday_batch WHERE id=%s FOR UPDATE', [batch.id])
        batch.invalidate_recordset(['state'])
        if batch.state != 'draft':
            raise UserError(_('This version is already published.'))
        if any(row['decision'] == 'review' for row in batch.rows_json):
            raise UserError(_('Resolve every review item before publishing.'))
        included = [r for r in batch.rows_json if r['decision'] == 'include']
        if not included:
            raise UserError(_('Include at least one holiday before publishing.'))
        added = 0
        for row in included:
            made = self._create_row(company, calendar, row['name'], self._parse_day(row['date']), self._parse_day(row['date_to']))
            if made:
                made.write({'pb_holiday_kind': row['kind'], 'pb_holiday_batch_id': batch.id})
                added += 1
        batch.sudo().write({'state': 'published', 'published_by': self.env.uid, 'published_on': fields.Datetime.now()})
        batch.message_post(body=_('%s holidays published to the working calendar. Source and row decisions archived.', added))
        return {'added': added}

    @api.model
    def policy_action(self):
        self.env['pb.timeoff']._require_officer()
        return {'type': 'ir.actions.act_window', 'res_model': 'pb.holiday.policy.note', 'view_mode': 'list,form', 'views': [(False, 'list'), (False, 'form')], 'name': _('Leave policy reference')}

    @api.model
    def _seed_policy_reference(self):
        if self.env.cr.dbname != 'rize':
            return
        source = json.loads((Path(__file__).parent.parent / 'data/leave_reference.json').read_text())
        for company in self.env['res.company'].sudo().search([]):
            if self.env['pb.holiday.policy.note'].sudo().search_count([('company_id', '=', company.id)]):
                continue
            for index, row in enumerate(source):
                for country in ('Singapore', 'Indonesia', 'Vietnam', 'India'):
                    self.env['pb.holiday.policy.note'].sudo().create({'name': row['name'], 'sequence': index * 10,
                        'company_id': company.id, 'country': country, 'entitlement': row[country],
                        'carry_rule': row['rule'], 'source': 'Supplied leave policy workbook · draft reference', 'reviewed': False})
