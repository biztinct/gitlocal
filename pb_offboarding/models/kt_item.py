# -*- coding: utf-8 -*-
"""What the person leaving knows, and who is taking it.

One row per thing that has to be handed over: the topic, who is handing it
over, who is picking it up, where the notes ended up. A leaving checklist step
that says "do the handover" is a box somebody ticks on the last morning; this
is the list that makes the tick mean something.

THE FIFTEEN-DAY PING. While any item on a running exit is still open, the HR
team is told — once every fifteen days, not once a day and not once per item.
The stamp lives on the CASE (`kt_last_ping`), which is what makes "run the job
twice today" send one email: the second run finds today's stamp and stops.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .offboarding_common import KT_STATES

_logger = logging.getLogger(__name__)


class PbKtItem(models.Model):
    _name = 'pb.kt.item'
    _description = 'Knowledge Handover Item'
    _order = 'case_id, sequence, id'

    name = fields.Char(compute='_compute_name', store=True, string='Item')
    case_id = fields.Many2one(
        'pb.journey.case', string='Leaving checklist', required=True,
        index=True, ondelete='cascade')
    employee_id = fields.Many2one(
        related='case_id.employee_id', store=True, index=True,
        string='Employee')
    sequence = fields.Integer(default=10)
    topic = fields.Char(
        string='What is being handed over', required=True,
        help='The system, the client, the report — whatever the next person '
             'has to be able to pick up.')
    from_employee_id = fields.Many2one(
        'hr.employee', string='Handing over',
        help='The person leaving, unless somebody else knows this piece.')
    to_employee_id = fields.Many2one(
        'hr.employee', string='Picking it up')
    doc_link = fields.Char(
        string='Where the notes are',
        help='A link to the document, the folder or the page the notes live '
             'on. Anything a colleague can open.')
    notes = fields.Text(string='Notes')
    state = fields.Selection(
        KT_STATES, string='Status', default='todo', required=True, index=True)
    done_at = fields.Datetime(string='Handed over on', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('topic', 'case_id.employee_id')
    def _compute_name(self):
        for rec in self:
            rec.name = rec.topic or _('Handover item')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Handover item')

    @api.onchange('case_id')
    def _onchange_case_id(self):
        if self.case_id and not self.from_employee_id:
            self.from_employee_id = self.case_id.employee_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('from_employee_id') and vals.get('case_id'):
                case = self.env['pb.journey.case'].sudo().browse(
                    vals['case_id'])
                if case.exists() and case.employee_id:
                    vals['from_employee_id'] = case.employee_id.id
        return super().create(vals_list)

    # --------------------------------------------------------------- actions
    def action_start(self):
        self.filtered(lambda k: k.state == 'todo').write(
            {'state': 'in_progress'})
        return True

    def action_done(self):
        for rec in self:
            if rec.state == 'done':
                continue
            rec.write({'state': 'done', 'done_at': fields.Datetime.now()})
            rec.case_id.message_post(body=_(
                "Handed over: %(what)s%(who)s.", what=rec.topic or '',
                who=(_(' — %s is picking it up', rec.to_employee_id.name)
                     if rec.to_employee_id else '')))
        return True

    def action_reopen(self):
        self.filtered(lambda k: k.state == 'done').write(
            {'state': 'in_progress', 'done_at': False})
        return True

    # ------------------------------------------------------------- the gate
    @api.model
    def open_for(self, employee_id):
        """The handover items still outstanding for somebody who is leaving.

        Sudo for the same reason every other read in this module's gate is: an
        answer that a reader's own access can soften is not an answer.
        """
        return self.sudo().search([
            ('employee_id', '=', int(employee_id or 0)),
            ('case_id.state', 'in', ('draft', 'active', 'on_hold')),
            ('state', '!=', 'done'),
        ])


class PbJourneyCaseKt(models.Model):
    _inherit = 'pb.journey.case'

    kt_item_ids = fields.One2many(
        'pb.kt.item', 'case_id', string='Handover items')
    kt_open_count = fields.Integer(
        compute='_compute_kt_counts', string='Handover items open')
    kt_last_ping = fields.Date(
        string='HR last reminded about the handover', readonly=True,
        copy=False,
        help='Stamped by the daily job. It is what stops a second run on the '
             'same day sending a second email.')

    @api.depends('kt_item_ids.state')
    def _compute_kt_counts(self):
        for rec in self:
            rec.kt_open_count = len(rec.kt_item_ids.filtered(
                lambda k: k.state != 'done'))

    # ---------------------------------------------------------------- the ping
    def _kt_ping_due(self, today, every_days):
        """Whether this case's handover is worth another email today."""
        self.ensure_one()
        if self.case_type != 'offboarding' or self.state != 'active':
            return False
        if not self.kt_item_ids.filtered(lambda k: k.state != 'done'):
            return False
        if not self.kt_last_ping:
            return True
        return self.kt_last_ping + timedelta(days=max(1, every_days)) <= today

    def send_kt_ping(self, today=None):
        """One email to the HR team about this exit's outstanding handover.

        Returns True only when a message was actually queued, so the job's
        count is honest — and the stamp is written ONLY on that path, so a run
        that could not find an address tries again tomorrow instead of going
        quiet for a fortnight.
        """
        self.ensure_one()
        template = self.env.ref('pb_offboarding.mail_template_kt_ping',
                                raise_if_not_found=False)
        if not template:
            _logger.warning('pb_offboarding: the handover reminder email is '
                            'missing')
            return False
        owners = self.kt_item_ids.filtered(
            lambda k: k.state != 'done').mapped('to_employee_id.work_email')
        hr = self._resolve_assignee('hr', self.employee_id)
        addresses = [a for a in ([hr.email] if hr else []) + list(owners) if a]
        # De-duplicated, case-insensitively: the same HR address reached twice
        # is one recipient, and a comma-separated list with a repeat in it is a
        # person receiving the same email twice.
        seen, to = set(), []
        for address in addresses:
            key = address.strip().lower()
            if key and key not in seen:
                seen.add(key)
                to.append(address.strip())
        if not to:
            _logger.info('pb_offboarding: nobody to remind about the handover '
                         'on journey %s', self.id)
            return False
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={'email_to': ','.join(to), 'auto_delete': False})
        except Exception:               # noqa: BLE001
            _logger.exception('pb_offboarding: handover reminder for journey '
                              '%s', self.id)
            return False
        self.sudo().write({'kt_last_ping': today or fields.Date.today()})
        open_now = len(self.kt_item_ids.filtered(lambda k: k.state != 'done'))
        self.message_post(body=_(
            "%(what)s still open — %(who)s have been reminded.",
            what=(_("One handover item is") if open_now == 1
                  else _("%s handover items are", open_now)),
            who=', '.join(to)))
        return True
