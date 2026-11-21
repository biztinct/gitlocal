# -*- coding: utf-8 -*-
"""WDGAP S8-D (owner ruling PC1) — Pay › Changes sends new raises to Change job.

PC1  the door: for the person picked on Pay › Changes, Change job opens
     prefilled as a pay change (`pb_start_for_employee(emp, {'reason_kind':
     'pay', 'source': 'pay_changes'})`) — nothing is created by opening it.
PC2  with Change job installed the patch is in the screen's assets (this
     module's own bundle); WITHOUT it nothing of the door exists: pb_pay's own
     files carry no trace of Change job, so a database without `pb_job_change`
     keeps today's form exactly (the patch file is listed in this module's
     manifest only).
PC3  the patch only opens the door for people allowed to change jobs (the
     same gate list as the server), and the old "Write it" path stays in
     place for everybody else.
"""
import os

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as handle:
        return handle.read()


@tagged('post_install', '-at_install', 'wdgap_s8d')
class TestS8dPayChangesDoor(TransactionCase):

    def test_pc1_the_door_opens_change_job_as_a_pay_change(self):
        emp = self.env['hr.employee'].create({'name': 'S8D PC1 person'})
        before = self.env['pb.job.change'].search_count([])
        act = self.env['pb.job.change'].pb_start_for_employee(
            emp.id, {'reason_kind': 'pay', 'source': 'pay_changes'})
        self.assertEqual(act['tag'], 'pb_job_change')
        self.assertEqual(act['params']['employee_id'], emp.id)
        self.assertEqual(act['params']['vals'],
                         {'reason_kind': 'pay', 'source': 'pay_changes'})
        self.assertEqual(self.env['pb.job.change'].search_count([]), before,
                         "opening the door creates nothing")
        flow = self.env['pb.job.change.board'].get_flow(emp.id, 0, act['params']['vals'])
        self.assertEqual(flow['draft']['reason_kind'], 'pay')
        self.assertEqual(flow['draft']['source'], 'pay_changes')

    def test_pc2_only_this_module_carries_the_door(self):
        manifest = _read('pb_job_change', '__manifest__.py')
        self.assertIn('pb_job_change/static/src/js/job_change_patches.js', manifest)
        patches = _read('pb_job_change', 'static', 'src', 'js', 'job_change_patches.js')
        self.assertIn('patch(PbPayChanges.prototype', patches)
        self.assertIn('pb_start_for_employee', patches)
        for path in (('pb_pay', 'static', 'src', 'js', 'pay_review.js'),
                     ('pb_pay', 'static', 'src', 'xml', 'pay_review.xml'),
                     ('pb_pay', '__manifest__.py')):
            text = _read(*path)
            self.assertNotIn('pb_job_change', text, path)
            self.assertNotIn('pb.job.change', text, path)

    def test_pc3_gate_and_fallback(self):
        patches = _read('pb_job_change', 'static', 'src', 'js', 'job_change_patches.js')
        block = patches.split('patch(PbPayChanges.prototype', 1)[1].split('\n});', 1)[0]
        self.assertIn('mayChangeJobs()', block)
        self.assertIn('return super.choosePerson(person)', block,
                      "people who may not change jobs keep the old form")
        from odoo.addons.pb_job_change.models.job_change import GATE_GROUPS
        for group in GATE_GROUPS:
            self.assertIn('"%s"' % group, patches, "the screen gate mirrors the server's")
