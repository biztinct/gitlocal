# -*- coding: utf-8 -*-
"""LEARNING L5 — the outside-course catalogue (owner decision LD6).

`pb.training.outside.course` is OUR OWN LIST: courses somebody else runs — a
college, a licensing body, an online school — that the training team has
looked at and is willing to pay for. HR types the provider, the link, the
cost and the hours; nothing is pulled from a paid connector (LD6: none until
a customer contracts one).

An outside course is never "put on" anybody the way one of ours is: there is
no lesson to track. It is ASKED FOR (a course request, `request.py`), agreed
by the manager and — when it costs money — the HR lead, then taken, then
claimed back with the receipt and the certificate (the E3 claim). The money
is pre-booked against the allowance the moment the request is agreed, so the
same allowance is never promised twice.

Two small additions ride here because they are about the catalogue too:
  * `slide.channel.pb_requestable` — whether people may ask to take one of
    OUR courses (default yes);
  * the claim's links back to the outside course and to the request it came
    from, and the pre-fill that makes "Claim this course back" one press.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .training_common import OUTSIDE_KINDS, as_id, leg, money_words

_logger = logging.getLogger(__name__)


class PbTrainingOutsideCourse(models.Model):
    _name = 'pb.training.outside.course'
    _description = 'Outside course'
    _inherit = ['mail.thread']
    _order = 'name, id'

    name = fields.Char(string='Course', required=True, tracking=True)
    provider = fields.Char(string='Who runs it', tracking=True)
    url = fields.Char(string='Link')
    cost = fields.Monetary(string='What it costs', currency_field='currency_id',
                           tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    hours = fields.Float(string='Hours', digits=(6, 1))
    blurb = fields.Text(string='What it is, in a sentence or two')
    kind = fields.Selection(OUTSIDE_KINDS, string='How it is taught',
                            required=True, default='online')
    country_id = fields.Many2one('res.country', string='Country',
                                 help='Leave empty when it is open to anybody.')
    job_ids = fields.Many2many(
        'hr.job', 'pb_training_outside_course_job_rel', 'course_id', 'job_id',
        string='Good for these jobs',
        help='The jobs it is a good fit for. The catalogue can be filtered '
             'by job.')
    issues_certificate = fields.Boolean(string='Ends with a certificate')
    validity_months = fields.Integer(
        string='Certificate valid for (months)',
        help='0 when the certificate never runs out.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    request_ids = fields.One2many('pb.training.request', 'outside_course_id',
                                  string='Requests')
    requests_count = fields.Integer(compute='_compute_counts',
                                    string='Asked for')
    taken_count = fields.Integer(compute='_compute_counts', string='Taken')

    @api.depends('request_ids.state')
    def _compute_counts(self):
        for rec in self:
            rows = rec.request_ids.sudo()
            rec.requests_count = len(rows.filtered(
                lambda r: r.state != 'cancelled'))
            rec.taken_count = len(rows.filtered(
                lambda r: r.state in ('taken', 'claimed')))

    @api.constrains('cost', 'hours', 'validity_months')
    def _check_numbers(self):
        for rec in self:
            if rec.cost < 0 or rec.hours < 0 or rec.validity_months < 0:
                raise ValidationError(_(
                    "Cost, hours and months cannot be below zero."))

    def cost_words(self):
        """"3,000,000 ₫" — or "Free" — never a bare 0."""
        self.ensure_one()
        if not self.cost:
            return _("Free")
        return money_words(self.env, self.cost, self.currency_id)

    def hours_words(self):
        self.ensure_one()
        if not self.hours:
            return ''
        value = ('%.1f' % self.hours).rstrip('0').rstrip('.')
        return _("1 hour") if value == '1' else _("%s hours", value)


class SlideChannelRequestable(models.Model):
    _inherit = 'slide.channel'

    pb_requestable = fields.Boolean(
        string='People may ask to take it', default=True,
        help='Ticked, the course is offered on "Ask to take a course". The '
             'manager decides, and an agreed request puts the course on the '
             'person at once.')


class PbTrainingClaimRequest(models.Model):
    """The claim's links back to the catalogue and to the request.

    THE PRE-FILL IS A CONVENIENCE, THE CHECK IS NOT: a request id arriving
    from a form buys nothing unless the request is the caller's own, agreed,
    and costs money. Linked, the claim does not count its own request's
    pre-booked amount against itself (`_facts_for`, request.py), and when the
    claim is agreed the request becomes "Claimed back".
    """
    _inherit = 'pb.training.claim'

    outside_course_id = fields.Many2one(
        'pb.training.outside.course', string='Outside course', index=True,
        ondelete='set null')
    request_id = fields.Many2one(
        'pb.training.request', string='From the request', index=True,
        ondelete='set null', copy=False)

    @api.model
    def _own_request(self, employee, request_id):
        row = self.env['pb.training.request'].sudo().browse(
            as_id(request_id)).exists()
        if row and row.employee_id.id == employee.id \
                and row.state in ('approved', 'taken') and row.amount > 0:
            return row
        return self.env['pb.training.request'].sudo().browse()

    @api.model
    def raise_claim(self, values, invoice=None, certificate=None):
        values = dict(values or {})
        request_id = values.pop('request_id', None)
        emp = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        req = self._own_request(emp, request_id) if (emp and request_id) \
            else self.env['pb.training.request'].sudo().browse()
        if req:
            # The request says what the course was; the person still types
            # what they really paid and attaches the two files.
            values.setdefault('course_name', req.course_name)
            if not values.get('course_name'):
                values['course_name'] = req.course_name
            if not values.get('provider'):
                values['provider'] = req.provider or ''
            if not values.get('amount'):
                values['amount'] = req.amount
            values['request_id'] = req.id
            values['outside_course_id'] = req.outside_course_id.id
        res = super().raise_claim(values, invoice=invoice,
                                  certificate=certificate)
        if req and res.get('id'):
            leg(self.env, 'link the request to its claim',
                lambda: req.sudo().write({'claim_id': res['id']}))
        return res

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            for rec in self.filtered('request_id'):
                leg(self.env, 'the request is claimed back',
                    lambda rec=rec: rec.request_id.sudo()._mark_claimed(rec))
        return res

    def _payload(self):
        data = super()._payload()
        data['request_id'] = self.request_id.id
        data['outside_course_id'] = self.outside_course_id.id
        return data


def check_outside_values(env, values):
    """The outside-course drawer's values, checked in one place."""
    name = (values.get('name') or '').strip()[:200]
    if not name:
        raise UserError(_("Give the course a name — what the provider calls "
                          "it."))
    kind = values.get('kind') or 'online'
    if kind not in dict(OUTSIDE_KINDS):
        kind = 'online'
    try:
        cost = float(values.get('cost') or 0)
        hours = float(values.get('hours') or 0)
        months = int(values.get('validity_months') or 0)
    except (TypeError, ValueError):
        raise UserError(_("Cost, hours and months are numbers."))
    if cost < 0 or hours < 0 or months < 0:
        raise UserError(_("Cost, hours and months cannot be below zero."))
    url = (values.get('url') or '').strip()[:500]
    if url and not url.lower().startswith(('http://', 'https://')):
        url = 'https://' + url
    vals = {
        'name': name,
        'provider': (values.get('provider') or '').strip()[:200],
        'url': url,
        'cost': cost,
        'hours': hours,
        'blurb': (values.get('blurb') or '').strip()[:2000],
        'kind': kind,
        'issues_certificate': bool(values.get('issues_certificate')),
        'validity_months': months if values.get('issues_certificate') else 0,
        'country_id': as_id(values.get('country_id')) or False,
        'job_ids': [(6, 0, [as_id(j) for j in (values.get('job_ids') or [])
                            if as_id(j)])],
    }
    return vals
