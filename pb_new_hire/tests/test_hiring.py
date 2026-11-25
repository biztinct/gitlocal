# -*- coding: utf-8 -*-
"""NEWHIRE P4 Part A — From Hiring, Many at once and "Confirm they joined".
Test numbers match the handover (A.5: H1-H9)."""
import base64
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import new_test_user, tagged

from odoo.addons.pb_new_hire.models.hiring import PbNewHireHiring

from .test_welcome import WelcomeCommon

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
START = date(2026, 12, 7)


@tagged('post_install', '-at_install', 'newhire')
class TestFromHiring(WelcomeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param('pb_hiring.offer_mail', '0')
        env['ir.config_parameter'].sudo().set_param('pb_hiring.docreq_trigger', 'on_accept')
        # the HR people of this company may read offers (Hiring's own roles)
        recruit = env.ref('pb_hiring.group_hiring_user')
        (cls.maker | cls.approver).write({'group_ids': [(4, recruit.id)]})
        cls.offer = cls._signed_offer('DEMO NH Candidate One', 'demo.nh.one@example.net',
                                      receive=('passport', 'qualification', 'bank', 'photograph'))
        cls.bare = cls._signed_offer('DEMO NH Candidate Two', 'demo.nh.two@example.net', receive=())
        # P5a: a second colleague who can be a buddy (HR's own choice in step 6)
        cls.mentor2 = env['hr.employee'].create({
            'name': 'DEMO NH Mentor Two', 'company_id': cls.company.id,
            'department_id': cls.finance.id, 'employee_type': 'employee'})
        env['hr.contract'].create({'name': 'DEMO NH Mentor Two', 'employee_id': cls.mentor2.id,
                                   'wage': 4000.0, 'date_start': date(2019, 3, 4),
                                   'company_id': cls.company.id, 'state': 'open'})

    def setUp(self):
        super().setUp()
        # P4's tests read the bank paper (a document reader is set up); the
        # P5a tests below switch it off where they need to
        self.reader_on = True
        Studio = type(self.env['pb.new.hire'])
        self.patch(Studio, '_bank_reader_on', lambda this: self.reader_on)

    @classmethod
    def _signed_offer(cls, name, email, receive=()):
        env = cls.env
        co = cls.company
        app = env['hr.applicant'].sudo().create({'partner_name': name, 'email_from': email,
                                                 'job_id': cls.accountant.id, 'company_id': co.id})
        req = env['pb.hiring.requisition'].sudo().create({
            'title': 'DEMO NH Accountant', 'department_id': cls.finance.id, 'company_id': co.id,
            'requested_by_id': cls.boss.id, 'reporting_manager_id': cls.boss.id, 'headcount': 1,
            'budget_cost': 100.0, 'requirements': 'Able to do the job.', 'job_id': cls.accountant.id,
            'opened_on': START - timedelta(days=40), 'state': 'open', 'request_state': 'agreed',
            'selected_applicant_id': app.id})
        app.write({'pb_requisition_id': req.id})
        bgv = env['pb.hiring.bgv'].sudo().with_company(co).open_for(req.id)
        bgv.item_ids.write({'result': 'ok'})
        offer = env['pb.hiring.offer'].sudo().with_company(co).draft_for(req.id)
        offer.write({'currency_id': env.ref('base.SGD').id, 'start_date': START,
                     'job_title': 'DEMO NH Accountant'})
        offer.action_add_line({'name': 'Basic pay', 'kind': 'earning', 'amount': 5200.5,
                               'period': 'monthly'})
        offer.write({'state': 'hr_ok', 'buddy_employee_ids': [(6, 0, cls.mentor.ids)]})
        docreq = env['pb.hiring.docreq'].sudo().open_for(offer.id)
        docreq.write({'sent_on': fields.Datetime.now(), 'deadline': START})
        for item in docreq.item_ids:
            low = item.name.lower()
            if any(k in low for k in receive):
                if 'photo' in low:
                    docreq.receive(item.id, 'photo.png', PNG, mimetype='image/png')
                else:
                    docreq.receive(item.id, 'paper.pdf', PDF, mimetype='application/pdf')
        try:
            with env.cr.savepoint():
                offer.action_send_to_candidate()
                offer.record_decision('accepted')
                offer.action_record_signed(filename='signed.pdf', content=PDF,
                                           mimetype='application/pdf')
        except Exception:                       # noqa: BLE001 — no PDF tool: sign by hand
            offer.write({'state': 'signed', 'signed_on': START - timedelta(days=10)})
        offer.write({'join_status': 'pending', 'expected_join_date': START})
        return offer

    def draft_from(self, offer, **kw):
        out = self.studio().offer_draft(offer.id)
        self.assertTrue(out['ok'], out)
        d = self.welcome_draft(**dict(out['draft'], login_mode='none', clock_on=False, clock_code='',
                                      equipment=[self.laptop.id]))
        d.pop('parent_name', None)
        d.pop('buddy_name', None)
        d.setdefault('wage', 5200.5)
        d['work_email'] = ''
        d.update(kw)
        return d

    # ------------------------------------------------------------------ H1
    def test_h1_offers_list(self):
        res = self.studio().hiring_offers()
        self.assertTrue(res['on'])
        rows = {r['offer_id']: r for r in res['rows']}
        self.assertIn(self.offer.id, rows)
        row = rows[self.offer.id]
        self.assertEqual(row['name'], 'DEMO NH Candidate One')
        self.assertEqual((row['team_id'], row['job_id'], row['manager_id']),
                         (self.finance.id, self.accountant.id, self.boss.id))
        self.assertEqual(row['first_day'], '2026-12-07')
        self.assertAlmostEqual(row['wage'], 5200.5)
        self.assertEqual(row['wage_currency']['name'], 'SGD')
        self.assertEqual({c['key'] for c in row['received']}, {'identity', 'degree', 'bank', 'photo'})
        self.assertEqual({c['key'] for c in row['missing']}, {'payslip', 'tax'})
        self.assertIn('Identity card', [c['label'] for c in row['received']])
        self.assertTrue(row['bgv']['ok'])
        # a background check with a line still open: amber, never a gate
        self.offer.bgv_id.item_ids[:1].sudo().write({'result': 'pending'})
        self.offer.bgv_id.invalidate_recordset()
        row = {r['offer_id']: r for r in self.studio().hiring_offers()['rows']}[self.offer.id]
        self.assertFalse(row['bgv']['ok'])
        self.assertIn('background check is not finished', row['bgv']['sentence'])
        # rights: somebody without Hiring's roles sees none of them
        hr_only = new_test_user(self.env, login='nh_hr_only', groups='base.group_user,hr.group_hr_user',
                                company_id=self.company.id, company_ids=[(6, 0, self.company.ids)])
        seen = self.studio(hr_only).hiring_offers()
        self.assertNotIn(self.offer.id, [r['offer_id'] for r in seen['rows']])
        # joined or dropped offers are not waiting; another company's neither
        self.bare.sudo().write({'join_status': 'dropped'})
        self.assertNotIn(self.bare.id, [r['offer_id'] for r in self.studio().hiring_offers()['rows']])
        self.assertEqual(self.studio().load()['hiring']['on'], True)

    # ------------------------------------------------------------------ H2
    def test_h2_bring_across(self):
        out = self.studio().offer_draft(self.offer.id)
        self.assertTrue(out['ok'])
        d = out['draft']
        self.assertEqual(d['name'], 'DEMO NH Candidate One')
        self.assertEqual(d['personal'], 'demo.nh.one@example.net')
        self.assertEqual((d['department_id'], d['job_id'], d['parent_id']),
                         (self.finance.id, self.accountant.id, self.boss.id))
        self.assertEqual(d['date_start'], '2026-12-07')
        self.assertAlmostEqual(d['wage'], 5200.5, msg='same money as the team\'s country (SGD)')
        self.assertEqual(d['buddy_id'], self.mentor.id)
        self.assertEqual(d['offer_id'], self.offer.id)
        # an offer in another money: no wage, a sentence instead
        self.offer.sudo().currency_id = self.env.ref('base.VND')
        other = self.studio().offer_draft(self.offer.id)
        self.assertNotIn('wage', other['draft'])
        self.assertIn("The offer's pay is in VND. Type the monthly wage in SGD.", other['wage_note'])
        # step 5 knows what came across
        docs = self.studio().details_options({'payroll_country': 'SG', 'name': d['name'],
                                              'offer_id': self.offer.id})
        items = {i['key']: i for i in docs['items']}
        self.assertEqual(items['bank']['default'], 'hiring')
        self.assertIn('Received in Hiring', items['bank']['received']['line'])
        received = [k for k, i in items.items() if i.get('received')]
        self.assertIn('bank', received)
        self.assertTrue(len(received) >= 2, received)
        gone = self.studio().offer_draft(self.offer.id + 9999)
        self.assertFalse(gone['ok'])

    # ------------------------------------------------------------------ H3 / H4 / H5 / H6
    def _approved(self, offer, ocr=None, **kw):
        sent = self.studio().send(self.draft_from(offer, **kw))
        self.assertTrue(sent.get('pending'), sent)
        Req = type(self.env['pb.bank.change.request'])
        reader = ocr or (lambda this: None)
        with patch.object(Req, 'action_run_ocr', reader):
            self.approve(sent)
        emp = self.hires('DEMO NH Candidate One') if offer == self.offer else self.hires('DEMO NH Candidate Two')
        self.assertEqual(len(emp), 1)
        return sent, emp

    def test_h3_h5_apply_and_close(self):
        def readable(this):
            this.write({'x_bank_name': 'DEMO Bank', 'x_account_number': '123456789012',
                        'x_account_name': 'DEMO NH Candidate One'})
        before = {m: self.env[m].sudo().search_count([]) for m in ('hr.contract', 'pb.journey.case')}
        originals = self.offer.docreq_ids.item_ids.mapped('attachment_id')
        sent, emp = self._approved(self.offer, ocr=readable, login_mode='email',
                                   personal='demo.nh.one@example.net')
        legs = self.legs(sent)
        # the identity card needs a valid-until date Hiring never asked for:
        # amber, said plainly, the rest filed (never an invented date)
        id_cat = self.env.ref('pb_employee_vault.cat_id_document')
        if id_cat.requires_expiry:
            self.assertFalse(legs['hiring']['ok'])
            self.assertIn('Identity card needs a valid-until date, so it was not filed.',
                          legs['hiring']['message'])
            self.assertIn('bank account from the Hiring paper, waiting for a second approval',
                          legs['hiring']['message'])
        else:
            self.assertTrue(legs['hiring']['ok'], legs['hiring'])
        self.assertTrue(legs['hiring_close']['ok'], legs['hiring_close'])
        # H3: copies in the mapped categories, unverified; originals untouched; photo set
        docs = self.env['pb.employee.document'].sudo().search([('employee_id', '=', emp.id)])
        cats = {d.category_id for d in docs}
        self.assertIn(self.env.ref('pb_employee_vault.cat_certificate'), cats)
        if 'verified' in docs._fields:
            self.assertFalse(any(docs.mapped('verified')))
        self.assertTrue(all(a.exists() and a.res_model == 'pb.hiring.docreq' for a in originals))
        self.assertTrue(emp.image_1920, 'the photo became the picture')
        # H4 readable: a bank request waiting for a second person
        bank = self.env['pb.bank.change.request'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(bank), 1)
        self.assertIn(bank.state, ('hr_review', 'finance_review'))
        # H5: offer joined, applicant hired, ONE of everything, Hiring's own legs ran
        offer = self.offer.sudo()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, 'joined')
        self.assertEqual(offer.employee_id, emp)
        self.assertEqual(offer.joined_on, START)
        self.assertTrue(offer.applicant_id.stage_id.hired_stage or offer.applicant_id.date_closed)
        contracts = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(contracts), 1)
        self.assertEqual(offer.contract_id, contracts)
        users = self.env['res.users'].sudo().with_context(active_test=False).search(
            ['|', ('login', '=', 'demo.nh.one@example.net'), ('employee_ids', 'in', emp.ids)])
        self.assertLessEqual(len(users), 1, 'one sign-in')
        cases = self.case_of(emp)
        self.assertEqual(len(cases), 1, 'one joining checklist')
        self.assertEqual(offer.case_id, cases)
        laptops = self.env['pb.asset.request'].sudo().search(
            [('employee_id', '=', emp.id), ('category_id', '=', self.laptop.id),
             ('state', 'not in', ('cancelled', 'refused'))])
        self.assertEqual(len(laptops), 1, 'one laptop request')
        self.assertTrue(offer.comp_id, "Hiring's pay package leg ran")
        self.assertEqual(offer.comp_id.employee_id, emp)
        if offer.document_ids:
            self.assertTrue(all(offer.document_ids.mapped('vault_doc_id')), 'signed papers filed')
        self.assertEqual(emp.buddy_id, self.mentor, "step 6's buddy (brought across from the offer)")
        self.assertEqual(self.env['hr.contract'].sudo().search_count([]), before['hr.contract'] + 1)

    def test_h4_unreadable_bank_paper(self):
        sent, emp = self._approved(self.offer, ocr=None, open_case=False, equipment=None)
        legs = self.legs(sent)
        self.assertFalse(legs['hiring']['ok'])
        self.assertIn('The bank paper came across but could not be read. Open it in Bank requests '
                      'to finish.', legs['hiring']['message'])
        bank = self.env['pb.bank.change.request'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank.state, 'draft', 'never invented, never sent')
        docs = self.env['pb.employee.document'].sudo().search([('employee_id', '=', emp.id)])
        self.assertTrue(docs, 'the other papers still came across')
        self.assertFalse(self.case_of(emp), "HR said no checklist: Hiring's close does not open one")

    def test_h6_asks_skip_received(self):
        sent = self.studio().send(self.draft_from(self.offer))
        proposal = self.env['pb.newhire.proposal'].sudo().browse(sent['proposal_id'])
        values = proposal.payload()['values']
        asked = {a['key']: a for a in values['pb_nh_asks']}
        self.assertNotIn('bank', asked, 'the bank paper came across')
        self.assertTrue(values.get('pb_nh_hiring_bank'))
        for key, item in asked.items():
            self.assertNotIn('Received in Hiring', item['label'])
        # the merged ID row: only the number is asked for, if the country merges it
        if 'id_number' in asked:
            self.assertNotIn('card', asked['id_number']['label'].lower())
        self.assertIn(('From Hiring', '', self.offer.name), proposal._proposal_rows())

    # ------------------------------------------------------------------ H7
    def test_h7_offer_dropped_before_approval(self):
        sent = self.studio().send(self.draft_from(self.offer, login_mode='none', open_case=False,
                                                  equipment=None))
        self.offer.sudo().write({'state': 'dropped', 'join_status': 'dropped'})
        with patch.object(type(self.env['pb.bank.change.request']), 'action_run_ocr', lambda this: None):
            self.approve(sent)
        emp = self.hires('DEMO NH Candidate One')
        self.assertEqual(len(emp), 1, 'the hire stands')
        legs = self.legs(sent)
        self.assertFalse(legs['hiring']['ok'])
        self.assertFalse(legs['hiring_close']['ok'])
        self.assertIn('is no longer signed', legs['hiring_close']['message'])
        self.assertEqual(self.offer.sudo().state, 'dropped')

    # ------------------------------------------------------------------ H8
    def test_h8_no_hiring(self):
        Studio = type(self.env['pb.new.hire'])
        with patch.object(Studio, '_hiring_on', lambda self: False):
            load = self.studio().load()
            self.assertFalse(load['hiring']['on'])
            self.assertFalse(load['features']['hiring'])
            self.assertEqual(self.studio().hiring_offers(), {'on': False, 'rows': []})
            self.assertFalse(self.studio().offer_draft(self.offer.id)['ok'])
            docs = self.studio().details_options({'payroll_country': 'SG', 'name': 'x',
                                                  'offer_id': self.offer.id})
            self.assertFalse(any(i.get('received') for i in docs['items']))

    # ------------------------------------------------------------------ H9
    def test_h9_many_at_once(self):
        out = self.studio().many_at_once()
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['action'], 'pb_updates.action_pb_updates_desk')
        self.assertTrue(self.env.ref(out['action']))
        self.assertTrue(out['context']['pb_nh_joiners_sheet'])
        Desk = type(self.env['pb.updates.desk'])
        with patch.object(Desk, '_hire_route', lambda self: 'none'):
            off = self.studio().many_at_once()
        self.assertFalse(off['ok'])
        self.assertIn('approves new people', off['message'])

    # ------------------------------------------------------------------ the close itself
    def test_h5b_close_reuses(self):
        """What `action_confirm_joined` really reuses when the studio made the
        person first (FACTS_ONBOARD §K1 correction)."""
        self.fast_lane()
        sent = self.studio().send(self.draft_from(self.offer, login_mode='email',
                                                  personal='demo.nh.one@example.net'))
        self.assertTrue(sent.get('applied'), sent)
        emp = self.hires('DEMO NH Candidate One')
        offer = self.offer.sudo()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, 'joined')
        self.assertEqual(offer.login_user_id, emp.pb_portal_user_id, 'the studio sign-in, linked')
        self.assertEqual(len(self.case_of(emp)), 1)
        # a second press is idempotent
        self.assertTrue(offer.action_confirm_joined())
        self.assertEqual(len(self.case_of(emp)), 1)
        # Hiring's own path, untouched, for an offer the studio did not see
        self.bare.sudo().action_confirm_joined(joined_on=START)
        self.assertEqual(self.bare.sudo().state, 'joined')
        self.assertTrue(self.bare.sudo().employee_id)
        self.assertFalse(self.studio().offer_draft(self.offer.id)['ok'], 'no longer waiting')

    # ------------------------------------------------------------------ P5a §6
    def test_f1_buddy_hr_choice_wins(self):
        """HR changed the buddy in step 6: HR's choice stands; Hiring's own
        hand-over (the offer's first buddy) stands aside at the close."""
        sent, emp = self._approved(self.offer, buddy_id=self.mentor2.id)
        self.assertTrue(self.legs(sent)['buddy']['ok'], self.legs(sent)['buddy'])
        self.assertEqual(emp.buddy_id, self.mentor2)
        self.assertEqual(self.offer.sudo().state, 'joined')
        Nom = self.env['pb.buddy.nomination'].sudo()
        self.assertEqual(Nom.search([('employee_id', '=', emp.id)]).mapped('chosen_id'), self.mentor2,
                         "Hiring's buddy was not chosen over HR's")

    def test_f1b_buddy_left_empty_hiring_applies(self):
        """Step 6 left the buddy empty: Hiring's hand-over chooses the offer's buddy."""
        sent, emp = self._approved(self.offer, buddy_id=False)
        self.assertEqual(self.offer.sudo().state, 'joined')
        self.assertEqual(emp.buddy_id, self.mentor, "Hiring's buddy, from the offer")

    def test_f2_bank_paper_without_a_reader(self):
        """No document reader here: the bank row defaults to asking the
        person, says so, and the paper is filed on the record."""
        self.reader_on = False
        docs = self.studio().details_options({'payroll_country': 'SG', 'name': 'DEMO NH Candidate One',
                                              'offer_id': self.offer.id})
        bank = {i['key']: i for i in docs['items']}['bank']
        self.assertTrue(bank['received'])
        self.assertFalse(bank.get('can_hiring'))
        self.assertEqual(bank['default'], 'ask')
        self.assertEqual(bank['received']['note'], "DEMO's bank paper will be on their record. The account "
                                                   "details are asked for in the welcome link.")
        sent = self.studio().send(self.draft_from(self.offer))
        values = self.env['pb.newhire.proposal'].sudo().browse(sent['proposal_id']).payload()['values']
        self.assertFalse(values.get('pb_nh_hiring_bank'))
        self.assertIn('bank', [a['key'] for a in values['pb_nh_asks']], 'the account is asked')
        self.approve(sent)
        emp = self.hires('DEMO NH Candidate One')
        self.assertFalse(self.env['pb.bank.change.request'].sudo().search([('employee_id', '=', emp.id)]),
                         'nothing to read, so no bank request')
        papers = self.env['pb.employee.document'].sudo().search([('employee_id', '=', emp.id)])
        self.assertIn('Bank paper', papers.mapped('name'), 'the paper is on the record')
        asks = self.env['pb.new.hire.ask'].sudo().search([('employee_id', '=', emp.id)])
        self.assertIn('bank', asks.mapped('key'))

    def test_f2b_bank_paper_with_a_reader(self):
        """With a reader set up, P4 behaviour stays (the real check reads the
        same setting the bank screens read)."""
        self.reader_on = True
        docs = self.studio().details_options({'payroll_country': 'SG', 'name': 'DEMO NH Candidate One',
                                              'offer_id': self.offer.id})
        bank = {i['key']: i for i in docs['items']}['bank']
        self.assertTrue(bank['can_hiring'])
        self.assertEqual(bank['default'], 'hiring')
        self.assertNotIn('note', bank['received'])
        # the probe itself, unpatched: the setting the bank screens read
        if 'payroll.ai.config' not in self.env:
            self.skipTest('no document reader model on this database')
        Cfg = self.env['payroll.ai.config'].sudo()
        Cfg.search([]).write({'is_active': False})
        probe = lambda: PbNewHireHiring._bank_reader_on(self.studio())  # noqa: E731
        self.assertFalse(probe(), 'no active reader')
        Cfg.create({'provider_type': 'tesseract', 'purpose': 'doc_ocr', 'is_active': True,
                    'company_id': self.company.id})
        self.assertTrue(probe(), 'a reader is set up for the company')

    def test_f3_identity_card_valid_until(self):
        """The identity card from Hiring: with a valid-until date it is filed
        in its own kind of paper; without one P4's amber sentence stays; a
        date that has passed is refused in step 5."""
        id_cat = self.env.ref('pb_employee_vault.cat_id_document')
        if not id_cat.requires_expiry:
            self.skipTest('the identity card needs no date on this database')
        docs = self.studio().details_options({'payroll_country': 'SG', 'name': 'DEMO NH Candidate One',
                                              'offer_id': self.offer.id})
        item = {i['key']: i for i in docs['items']}['id_number']
        self.assertTrue(item.get('received_until'), item)
        past = self.studio().send(self.draft_from(self.offer, hiring_valid_until='2020-01-01'))
        self.assertFalse(past['ok'])
        self.assertEqual((past['step'], past['field']), ('docs', 'hiring_valid_until'))
        self.assertIn('That date has passed', past['message'])
        bad = self.studio().send(self.draft_from(self.offer, hiring_valid_until='not a date'))
        self.assertEqual(bad['field'], 'hiring_valid_until')

        def readable(this):
            this.write({'x_bank_name': 'DEMO Bank', 'x_account_number': '123456789012',
                        'x_account_name': 'DEMO NH Candidate One'})
        sent, emp = self._approved(self.offer, ocr=readable, hiring_valid_until='2031-05-31')
        leg = self.legs(sent)['hiring']
        self.assertTrue(leg['ok'], leg)
        card = self.env['pb.employee.document'].sudo().search(
            [('employee_id', '=', emp.id), ('category_id', '=', id_cat.id)])
        self.assertEqual(len(card), 1, 'filed in its own kind of paper')
        self.assertEqual(card.expiry_date, date(2031, 5, 31))
