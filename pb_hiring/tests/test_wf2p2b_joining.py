# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T13 — a new joiner is prepared once, split by the start date.

Hiring's "Before they join" owns everything before day one; the joining
checklist (opened when Hiring confirms they joined) owns day one onward. The
buddy the manager named in Hiring ticks the checklist's buddy step — never a
second ask — and the step now says where it came from; the laptop answers
reach the equipment request the checklist raised. A joiner who did not come
through Hiring is untouched.
"""

from datetime import timedelta

from odoo.tests import tagged

from .test_joining_p6 import JoiningCase


@tagged('post_install', '-at_install')
class TestWf2p2bJoining(JoiningCase):

    def test_wf2p2b_t13_buddy_and_laptop_carried_once(self):
        offer = self._signed()
        buddy = self.env['hr.employee'].sudo().create(
            {'name': 'DEMO P2b Buddy', 'company_id': self.company.id,
             'parent_id': self.boss.id, 'work_email': 'demo.p2b.buddy@example.com'})
        self._item(offer, 'buddy').submit_buddy([buddy.id], why='Same desk',
                                                by_name='DEMO P2b Boss')
        self._item(offer, 'laptop').submit_laptop(
            {'kind': 'mac', 'keyboard': 'us', 'screen': 'small', 'extras': [],
             'note': ''})
        self.facade.act('doc_add', {
            'offer_id': offer.id, 'kind': 'employment_agreement',
            'data': 'JVBERi0xLjQgYWdyZWVtZW50', 'filename': 'agreement.pdf',
            'mimetype': 'application/pdf'})
        self.facade.act('confirm_joined', {
            'offer_id': offer.id,
            'joined_on': str(offer.expected_join_date + timedelta(days=1))})
        case = offer.case_id.sudo()
        if not case or 'buddy_id' not in offer.employee_id._fields:
            self.skipTest('the joining checklist is not installed here')
        step = case.task_ids.filtered(lambda t: t.automation_key == 'buddy_invite')
        if not step:
            self.skipTest('this checklist has no buddy step')
        self.assertEqual(step.state, 'done', 'never asked twice')
        self.assertIn('Chosen in Hiring by DEMO P2b Boss on', step.note or '')
        # idempotent: a second hand-over writes nothing more
        offer._say_buddy_chosen_in_hiring()
        self.assertEqual((step.note or '').count('Chosen in Hiring by'), 1)
        laptop = case.task_ids.filtered(lambda t: t.automation_key == 'asset_laptop')
        if laptop:
            self.assertIn('Mac', laptop.note or '')
            if 'pb.asset.request' in self.env:
                request = self.env['pb.asset.request'].sudo().search(
                    [('journey_task_id', 'in', laptop.ids)])
                self.assertEqual(len(request), 1, 'one request, raised once')
                self.assertIn('Mac', request.justification or '')
        # nothing in Hiring's own list is dated on or after the start date:
        # day one onward belongs to the checklist
        for item in offer.prejoin_ids:
            if item.due_date:
                self.assertLess(item.due_date, offer.expected_join_date + timedelta(days=1))
