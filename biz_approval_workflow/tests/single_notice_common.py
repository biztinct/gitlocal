# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared helpers for WORKFLOW-2 P2b ("one message per event") area tests.

Every area test proves the same three things the same way:

* with a live route, the approver hears it once — the engine's "your turn" —
  and the area's own to-do / email is not created for them;
* without a route, the area sends exactly what it sent before;
* with the switch `biz_approval.single_notice` off, the area's message is back.

Nothing here sends real mail: area emails are only queued (`mail.mail` rows
inside the test transaction, rolled back), the engine's outbox is never
delivered.
"""

from .common import build, people_step

PARAM = 'biz_approval.single_notice'


class SingleNoticeMixin:
    """Mixed into an area's TransactionCase."""

    # ------------------------------------------------------------ switches
    def sn_switch(self, on=True):
        self.env['ir.config_parameter'].sudo().set_param(
            PARAM, '1' if on else '0')

    def sn_outbox_job(self, on=True):
        cron = self.env.ref('biz_approval_workflow.cron_outbox')
        cron.sudo().active = on

    def sn_settle(self):
        """Flush the transaction the way a commit would (pre-commit hooks
        included): the guards must not depend on it."""
        self.env.flush_all()
        self.env.cr.flush()

    # ---------------------------------------------------------------- route
    def sn_route(self, process_key, users, company=None, title='Check'):
        """Replace a company's route for `process_key` with one step that asks
        exactly `users` (any one of them) — or, given a list of recordsets,
        one such step per entry, in order. Returns the binding."""
        company = company or self.env.company
        engine = self.env['biz.approval.engine']
        process = self.env['biz.approval.process']._by_key(process_key)
        self.assertTrue(process, 'process %s is registered' % process_key)
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([('company_id', '=', company.id),
                        ('process_id', '=', process.id)]).write(
            {'active': False})
        flow = self.env['biz.approval.workflow'].sudo().create({
            'name': 'P2b %s' % process_key, 'company_id': company.id,
            'process_id': process.id, 'owner_user_id': self.env.user.id,
        })
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': flow.id, 'revision': 1, 'status': 'draft',
            'definition': build([
                people_step('s%s' % (n + 1), group.ids, all_required=False,
                            title='%s %s' % (title, n + 1))
                for n, group in enumerate(
                    users if isinstance(users, (list, tuple)) else [users])]),
        })
        checks = engine.validate_for_publish(version.id)
        engine.publish(version.id, version.draft_revision, None, 'p2b test',
                       [w['code'] for w in checks['warnings']])
        return Binding.create({
            'company_id': company.id, 'process_id': process.id,
            'scope_key': '', 'scope_label': company.name, 'kind_key': 'any',
            'workflow_id': flow.id, 'mode': 'follow',
        })

    def sn_no_route(self, process_key, company=None):
        company = company or self.env.company
        process = self.env['biz.approval.process']._by_key(process_key)
        self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id)]).write({'active': False})

    # ------------------------------------------------------------- counting
    def sn_todos(self, record, person, summary=None):
        domain = [('res_model', '=', record._name), ('res_id', '=', record.id),
                  ('user_id', '=', person.id)]
        if summary:
            domain.append(('summary', '=', summary))
        return self.env['mail.activity'].sudo().search(domain)

    def sn_your_turn(self, record, person):
        requests = self.env['biz.approval.request'].sudo().search([
            ('res_model', '=', record._name), ('res_id', '=', record.id)])
        return self.env['biz.approval.outbox'].sudo().search([
            ('request_id', 'in', requests.ids), ('kind', '=', 'your_turn'),
            ('user_id', '=', person.id)])

    def sn_requester(self, record, kind):
        requests = self.env['biz.approval.request'].sudo().search([
            ('res_model', '=', record._name), ('res_id', '=', record.id)])
        return self.env['biz.approval.outbox'].sudo().search([
            ('request_id', 'in', requests.ids), ('kind', '=', kind)])

    def sn_mails(self, record, template_xmlid=None, to=None):
        """Queued emails about `record` (optionally from one template /
        to one address)."""
        mails = self.env['mail.mail'].sudo().search([
            ('model', '=', record._name), ('res_id', '=', record.id)])
        if template_xmlid:
            template = self.env.ref(template_xmlid)
            subject = template._render_field(
                'subject', record.ids)[record.id]
            mails = mails.filtered(lambda m: m.subject == subject)
        if to:
            mails = mails.filtered(lambda m: to in (m.email_to or ''))
        return mails
