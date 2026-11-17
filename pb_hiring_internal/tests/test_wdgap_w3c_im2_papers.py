# -*- coding: utf-8 -*-
"""WDGAP W3-C, owner ruling IM2 (2026-11-17): a person who already works here
is NOT asked for their papers automatically at offer time; HR can still ask
by hand. Outside candidates are asked exactly as before. Numbered IM2-1 …
IM2-7 in the W3-C report. Built on the same fixtures as the S6-B move tests
(pb_hiring's offer world imported as a MODULE, ledger W2BM-3)."""
from odoo.tests import tagged

from odoo.addons.pb_hiring.tests import test_joining_p6 as base

TRIGGER = 'pb_hiring.docreq_trigger'


@tagged('post_install', '-at_install', 'wdgap_w3c')
class TestIm2Papers(base.JoiningCase):

    def setUp(self):
        super().setUp()
        Emp = self.env['hr.employee']
        self.mover = Emp.create({'name': 'DEMO W3C Internal mover',
                                 'company_id': self.company.id,
                                 'work_email': 'demo.w3c.mover@example.com'})
        self.req.sudo().write({'pb_staff_posting': 'both'})
        self.internal_app = self.env['hr.applicant'].sudo()._pbhi_apply(
            self.mover, self.req)
        self.outsider = self.env['hr.applicant'].create({
            'partner_name': 'DEMO W3C Outsider',
            'email_from': 'demo.w3c.outsider@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})

    # ---------------------------------------------------------- helpers
    def _pick(self, app):
        self.req.sudo().write({'selected_applicant_id': app.id})

    def _moment(self, key):
        self.env['ir.config_parameter'].sudo().set_param(TRIGGER, key)

    def _asked(self, offer):
        offer.invalidate_recordset()
        return bool(offer.docreq_id and offer.docreq_id.sent_on)

    def _documents_chip(self):
        journey = self.env['pb.hiring']._journey(self.req)
        return next(c for c in journey['chips'] if c['key'] == 'documents')

    # IM2-1 — "when the offer is drafted": the mover is not asked, the
    # outsider is (today's behaviour)
    def test_im2_1_before_offer(self):
        self._moment('before_offer')
        self._pick(self.internal_app)
        offer = self._offer()
        self.assertTrue(offer.candidate_email, 'the mover has an address, so '
                        'only the ruling can stop the ask')
        self.assertFalse(self._asked(offer), 'IM2: a mover is not asked')
        self.assertFalse(offer.docreq_id, 'IM2: no papers request made at all')

    def test_im2_1b_before_offer_outsider_unchanged(self):
        self._moment('before_offer')
        self._pick(self.outsider)
        offer = self._offer()
        self.assertTrue(self._asked(offer), 'an outside candidate is asked as before')

    # IM2-2 — "when the background check is clear": neither at drafting nor
    # when the check clears later
    def test_im2_2_on_check_clear(self):
        self._moment('on_check_clear')
        self._pick(self.internal_app)
        offer = self.env['pb.hiring.offer'].draft_for(self.req.id)
        self.assertFalse(self._asked(offer))
        bgv = self.env['pb.hiring.bgv'].open_for(self.req.id)
        for item in bgv.item_ids:
            item.action_set('ok')
        self.assertFalse(self._asked(offer), 'IM2: a clear check asks a mover nothing')

    def test_im2_2b_on_check_clear_outsider_unchanged(self):
        self._moment('on_check_clear')
        self._pick(self.outsider)
        offer = self.env['pb.hiring.offer'].draft_for(self.req.id)
        bgv = self.env['pb.hiring.bgv'].open_for(self.req.id)
        for item in bgv.item_ids:
            item.action_set('ok')
        self.assertTrue(self._asked(offer), 'an outside candidate is asked on a clear check')

    # IM2-3 — "when the candidate accepts": the mover is not asked, and the
    # offer is not recorded as "sent before every document was in"
    def test_im2_3_on_accept(self):
        self._moment('on_accept')
        self._pick(self.internal_app)
        offer = self._offer()
        offer.sudo().write({'state': 'hr_ok'})
        self.assertEqual(offer._documents_ready(), (True, ''),
                         'IM2: nothing is missing when nobody was asked')
        offer.action_send_to_candidate()
        note = offer.message_ids.filtered(lambda m: 'Offer sent to' in (m.body or ''))[:1]
        self.assertTrue(note)
        self.assertNotIn('before every document was in', note.body)
        offer.record_decision('accepted')
        self.assertFalse(self._asked(offer), 'IM2: accepting asks a mover nothing')

    def test_im2_3b_on_accept_outsider_unchanged(self):
        self._moment('on_accept')
        self._pick(self.outsider)
        offer = self._offer()
        ok, why = offer._documents_ready()
        self.assertFalse(ok)
        self.assertIn('Nobody has asked', why)
        offer.sudo().write({'state': 'hr_ok'})
        offer.action_send_to_candidate()
        offer.record_decision('accepted')
        self.assertTrue(self._asked(offer), 'an outside candidate is asked on acceptance')

    # IM2-4 — HR can still ask a mover by hand; from then on the usual
    # "what is missing" answer applies
    def test_im2_4_hr_asks_by_hand(self):
        self._moment('before_offer')
        self._pick(self.internal_app)
        offer = self._offer()
        self.assertFalse(offer.docreq_id)
        docreq = offer.action_request_documents()
        self.assertTrue(docreq.sent_on, 'the hand-made request goes out')
        self.assertTrue(self._asked(offer))
        ok, why = offer._documents_ready()
        self.assertFalse(ok, 'once asked, missing papers count again')
        self.assertTrue(why)

    # IM2-5 — the "Documents" chip says why nothing was asked; after a hand
    # request it counts the papers; an outsider's chip is unchanged
    def test_im2_5_documents_chip(self):
        self._moment('before_offer')
        self._pick(self.internal_app)
        offer = self._offer()
        chip = self._documents_chip()
        self.assertEqual(chip['note'], 'Already works here')
        self.assertEqual(chip['tone'], 'done')
        offer.action_request_documents()
        chip = self._documents_chip()
        self.assertNotEqual(chip['note'], 'Already works here')
        self.assertIn(' in', chip['note'])

    def test_im2_5b_documents_chip_outsider_unchanged(self):
        self._moment('on_accept')
        self._pick(self.outsider)
        self._offer()
        chip = self._documents_chip()
        self.assertEqual(chip['note'], 'Not asked for yet')
        self.assertEqual(chip['tone'], 'todo')

    # IM2-6 — the chip's words are translated (vi, id)
    def test_im2_6_chip_words_translated(self):
        import os
        from odoo.tools.translate import PoFileReader
        from odoo.modules.module import get_module_path
        root = get_module_path('pb_hiring_internal')
        for lang in ('vi_VN', 'id_ID'):
            with open(os.path.join(root, 'i18n', '%s.po' % lang), 'rb') as fh:
                rows = {r['src']: r for r in PoFileReader(fh)}
            row = rows.get('Already works here')
            self.assertTrue(row and row['value'], lang)
            self.assertNotIn('odoo', row['value'].lower())
