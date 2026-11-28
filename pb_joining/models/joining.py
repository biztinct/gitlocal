from datetime import timedelta
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

SYSTEM = 'base.group_system'


class Company(models.Model):
    _inherit = 'res.company'

    pb_joining_day_place = fields.Char(string='First-day place')
    pb_joining_day_bring = fields.Char(string='What to bring on the first day')


class Joining(models.Model):
    _name = 'pb.joining'
    _description = 'Joining'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'first_day, id'
    _check_company_auto = True

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda s: s.env.company)
    origin = fields.Selection([('invited', 'Invited'), ('hiring', 'Hiring')], required=True, default='invited')
    offer_id = fields.Many2one('pb.hiring.offer', ondelete='set null', check_company=True, copy=False)
    applicant_id = fields.Many2one(related='offer_id.applicant_id', store=True)
    job_title = fields.Char(required=True)
    job_id = fields.Many2one('hr.job', check_company=True)
    department_id = fields.Many2one('hr.department', check_company=True)
    manager_id = fields.Many2one('hr.employee', check_company=True)
    payroll_country = fields.Char(size=2, required=True)
    first_day = fields.Date(required=True)
    email = fields.Char()
    phone = fields.Char()
    lang = fields.Char()
    state = fields.Selection([('invited', 'Invited'), ('filling', 'Filling in'),
                              ('to_check', 'Ready for you to check'), ('added', 'Ready for day one'),
                              ('cancelled', 'They are not joining')], default='invited', required=True, index=True)
    token = fields.Char(default=lambda s: secrets.token_urlsafe(32), groups=SYSTEM, required=True, copy=False)
    _offer_unique = models.Constraint('UNIQUE(offer_id)', 'There is already a joining link for this offer.')
    _token_unique = models.Constraint('UNIQUE(token)', 'Please make a new joining link.')
    opened_at = fields.Datetime()
    last_seen_at = fields.Datetime()
    submitted_at = fields.Datetime()
    added_at = fields.Datetime()
    cancelled_at = fields.Datetime()
    link_sent_at = fields.Datetime()
    link_copied_at = fields.Datetime()
    link_mode = fields.Selection([('email', 'Email'), ('pass_on', 'Pass on')], default='pass_on', required=True)
    reminded_at = fields.Datetime()
    remind_count = fields.Integer()
    hr_nudged_at = fields.Datetime()
    actions_at = fields.Json(groups=SYSTEM)
    item_ids = fields.One2many('pb.joining.item', 'joining_id')
    day_time = fields.Char()
    day_place = fields.Char()
    day_ask_for = fields.Char()
    day_bring = fields.Char()
    manager_note = fields.Text()
    day_opened = fields.Boolean()
    welcome_started = fields.Boolean()
    employee_id = fields.Many2one('hr.employee', check_company=True)
    proposal_id = fields.Many2one('pb.newhire.proposal', copy=False)
    cancel_reason = fields.Char()
    progress = fields.Integer(compute='_compute_status', store=True)
    at_risk = fields.Boolean(compute='_compute_status', store=True)
    risk_reason = fields.Char(compute='_compute_status', store=True)
    sent_back_count = fields.Integer(compute='_compute_status', store=True)
    bank_later = fields.Boolean(compute='_compute_status', store=True)

    def _lock(self):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM pb_joining WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset()

    def _param_days(self, key, default):
        return max(0, int(self.env['ir.config_parameter'].sudo().get_param('pb_joining.' + key, default)))

    def _today(self):
        zone = self.company_id.resource_calendar_id.tz or self.company_id.partner_id.tz or 'UTC'
        return fields.Date.context_today(self.with_context(tz=zone))

    def _first(self):
        return self.name.strip().split(' ', 1)[0]

    def _day_label(self, fmt='EEEE d MMMM'):
        return format_date(self.env, self.first_day, date_format=fmt)

    def _contact(self):
        return self.offer_id.requisition_id.recruiter_id or self.create_uid

    def _masked_email(self):
        local, sep, domain = (self.email or '').partition('@')
        return (local[:1] + '•••@' + domain) if sep else ''

    def _url(self):
        return self.company_id.get_base_url().rstrip('/') + '/join/' + self.token

    def _catalogue(self):
        self.ensure_one()
        studio = self.env['pb.new.hire'].sudo().with_company(self.company_id)
        studio = studio._with_received({'offer_id': self.offer_id.id})
        return studio._detail_items(self.payroll_country, self._first())

    @api.model_create_multi
    def create(self, vals_list):
        joinings = super().create(vals_list)
        for j in joinings:
            j.write({'day_place': j.day_place or j.company_id.pb_joining_day_place,
                     'day_bring': j.day_bring or j.company_id.pb_joining_day_bring})
            j._sync_items()
        return joinings

    def _sync_items(self):
        self.ensure_one()
        existing = {r.key: r for r in self.item_ids}
        for item in self._catalogue():
            held = bool(item.get('received'))
            vals = {'available': True, 'from_hiring': held, 'need': item['need']}
            if item['key'] in existing:
                existing.pop(item['key']).write(vals)
            else:
                if held and item['key'].startswith('paper-'):
                    vals['state'] = 'saved'
                self.env['pb.joining.item'].create(dict(vals, joining_id=self.id, key=item['key']))
        for row in existing.values():
            row.available = False

    def _change_country(self, code):
        self._lock()
        if code == self.payroll_country:
            return
        self.write({'payroll_country': code})
        self._sync_items()
        if self.submitted_at and self.state != 'added':
            self.write({'state': 'filling', 'submitted_at': False})
            self.message_post(body=_('Country of work changed.'))

    def _paper_signing_done(self):
        return True

    def _section_info(self):
        return [('personal', _('About you'), 'user', _('1 minute')),
                ('id_number', _('Your identity card'), 'idCard', _('Take a photo and type the number')),
                ('bank', _('Bank account'), 'landmark', _('Where your pay goes')),
                ('tax', _('Tax and social insurance'), 'receipt', _('Numbers you already have')),
                ('emergency', _('Emergency contact'), 'heart', _('Who to call')),
                ('papers', _('Your papers'), 'layers', _('Papers needed before you start')),
                ('sign', _('Sign your papers'), 'pen', _('Read and sign')),
                ('day', _('Your first day'), 'sun', _('When, where, what to bring'))]

    def _section_states(self):
        states = {}
        for row in self.item_ids.filtered('available'):
            states.setdefault(row._section_key(), []).append(row)
        result = {}
        for key, rows in states.items():
            required = [r for r in rows if key != 'papers' or r.need != 'optional']
            if any(r.state == 'returned' for r in rows):
                result[key] = 'returned'
            elif any(r.state == 'empty' for r in required):
                result[key] = 'empty'
            elif any(r.state == 'later' for r in rows):
                result[key] = 'later'
            else:
                result[key] = 'done'
        result['day'] = 'done' if self.day_opened else 'empty'
        return result

    @api.depends('item_ids.state', 'item_ids.key', 'item_ids.available', 'item_ids.need',
                 'day_opened', 'first_day', 'state')
    def _compute_status(self):
        for j in self:
            today = j._today()
            states = j._section_states()
            done = sum(v in ('done', 'later') for v in states.values())
            j.progress = 100 if j.state == 'added' else (100 * done // len(states))
            rows = j.item_ids.filtered('available')
            j.sent_back_count = len(rows.filtered(lambda r: r.state == 'returned'))
            j.bank_later = states.get('bank') == 'later'
            due = j.first_day and (j.first_day - today).days <= j._param_days('risk_days', 7)
            j.at_risk = bool(due and j.state not in ('added', 'cancelled') and (
                j.state != 'to_check' or any(r.need == 'first_pay' and r.state in ('empty', 'later') for r in rows)))
            j.risk_reason = (_('Bank account') if j.bank_later else _('Details still to send')) if j.at_risk else False

    def _send_to_hr(self):
        self._lock()
        if self.state not in ('invited', 'filling') or any(
                v not in ('done', 'later') for v in self._section_states().values()) or not self._paper_signing_done():
            raise UserError(_('Finish the sections first.'))
        self.item_ids.filtered('reopened').write({'reopened': False})
        self.write({'state': 'to_check', 'submitted_at': fields.Datetime.now()})

    @api.model
    def _for_token(self, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            return self.browse(), 'invalid'
        j = self.sudo().search([('token', '=', token)], limit=1)
        if not j:
            return self.browse(), 'invalid'
        today = j._today()
        if today > j.first_day + timedelta(days=j._param_days('link_days_after_start', 14)):
            return self.browse(), 'invalid'
        if j.state == 'cancelled':
            if j.cancelled_at and today > j.cancelled_at.date() + timedelta(days=j._param_days('erase_days', 30)):
                return self.browse(), 'invalid'
            return j, 'closed'
        return j, 'ok'
