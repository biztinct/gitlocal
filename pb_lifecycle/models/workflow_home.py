"""WF2 P4a (R5) — workflow tasks and notices on the employee home.

Clone of `pb_me_expense/models/pb_me_home.py`: a "Needs you" row per waiting
task (linking to `/my/todo/<id>`), and a small "For you" card with notices
a workflow sent. Facts are read under sudo keyed on the session's own login
(the controller passes it; never an id from a URL).
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.misc import format_date


class WorkflowMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    def _wf_person(self, emp):
        login = emp.sudo().user_id if emp else self.env['res.users']
        return login if login and login.id == self.env.uid else None

    @api.model
    def _wf_needs_rows(self, emp):
        """[(key, n, url, words)] — one "Needs you" row per waiting task."""
        person = self._wf_person(emp)
        if not person:
            return []
        _ = self.env._
        studio = self.env['pb.workflow.studio'].sudo()
        now = fields.Datetime.now()
        rows = []
        for step in studio._home_tasks(person):
            verb = {'input': _('Fill in'), 'confirm': _('Read and confirm')}.get(step.kind, _('To do'))
            late = bool(step.due_at and step.due_at < now)
            due = (step.due_at - timedelta(days=1)).date() if step.due_at else None
            due_words = format_date(self.env, due) if due else ''
            if late:
                sub = _('Late — it was due %s', due_words)
            elif due_words:
                sub = _('Due %s', due_words)
            else:
                sub = step.run_id.name
            rows.append(('wf_task_%s' % step.id, 1, '/my/todo/%s' % step.id, {
                'label': '%s: %s' % (verb, step.name), 'sub': sub,
                'icon': 'check-circle' if step.kind == 'confirm' else 'clipboard-list',
                'tone': 'rose' if late else 'amber',
                'sentence': _('%(verb)s: %(what)s', verb=verb, what=step.name)}))
        return rows

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        for key, n, url, words in self._wf_needs_rows(emp):
            put(key, n, url, **words)

    @api.model
    def _wf_notice_card(self, emp):
        """The "For you" card, or None when nothing unread is waiting."""
        person = self._wf_person(emp)
        if not person:
            return None
        notices = self.env['pb.workflow.studio'].sudo()._home_notices(person, unread_only=True)
        if not notices:
            return None
        return {'key': 'workflow_notices', 'template': 'pb_lifecycle.pbme_card_workflow_notices',
                'data': {'rows': [{'id': n.id, 'subject': n.subject or '', 'body': n.body or '',
                                   'when': format_date(self.env, n.create_date.date())}
                                  for n in notices[:3]],
                         'more': max(0, len(notices) - 3)}}

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        card = self._wf_notice_card(emp)
        if card:
            cards.append(card)
        return cards
