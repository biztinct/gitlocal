# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Ask HR on the employee home: a "Needs you" row when HR has answered, and a
source for "My requests" (pb_me_portal's two T3a hooks, D5)."""

from odoo import api, models


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pb_ask_hr_answered(self, emp):
        """The person's questions HR has answered and that now wait on them:
        state ``answered`` and the last public word is HR's. Read under sudo,
        keyed on the employee (T-R11)."""
        tickets = self.env['pb.ask.hr.ticket'].sudo().search(
            [('employee_id', '=', emp.id), ('state', '=', 'answered')])
        return tickets.filtered(lambda t: t.last_public_by == 'hr')

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        answered = self._pb_ask_hr_answered(emp)
        n = len(answered)
        if not n:
            return
        if n == 1:
            label = _('HR answered your question')
            sentence = _('HR answered your question.')
            url = '/my/ask-hr/%s' % answered.id
        else:
            label = _('HR answered %s of your questions', n)
            sentence = _('HR answered %s of your questions.', n)
            url = '/my/ask-hr'
        put('ask_hr_answered', n, url, label=label,
            sub=_('Read the answer, then reply or mark it solved'),
            icon='message-circle-question', tone='indigo', sentence=sentence)

    @api.model
    def _my_requests_sources(self):
        sources = super()._my_requests_sources()
        _ = self.env._
        sources.append({
            'key': 'ask_hr', 'model': 'pb.ask.hr.ticket', 'label': _('Ask HR'),
            'icon': 'message-circle-question', 'employee_field': 'employee_id',
            'date_field': 'last_activity_on', 'state_field': 'state',
            'states': {
                'new': (_('Sent'), 'wait'),
                'with_hr': (_('With HR'), 'wait'),
                'answered': (_('Answered — your turn'), 'act'),
                'closed': (_('Closed'), 'off'),
            },
            'url': lambda rec: '/my/ask-hr/%s' % rec.id,
            'title': lambda rec: rec.name or rec.number or '',
        })
        return sources
