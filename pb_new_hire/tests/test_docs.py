# -*- coding: utf-8 -*-
"""NEWHIRE P3a — step 5, details and documents. Test numbers match the
handover (D1-D10; D11 = the P1 and P2 suites and the static gates)."""
import base64
import json

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .test_new_hire import NewHireCommon

PDF = base64.b64encode(b'%PDF-1.4\n% DEMO NH paper\n').decode()
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n DEMO NH').decode()


@tagged('post_install', '-at_install', 'newhire')
class DocsCommon(NewHireCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Paper = env['pb.new.hire.paper']
        cls.cat_id = env.ref('pb_employee_vault.cat_id_document')
        cls.cat_cert = env.ref('pb_employee_vault.cat_certificate')
        cls.cat_other = env.ref('pb_employee_vault.cat_other')
        cls.cat_permit = env.ref('pb_employee_vault.cat_work_permit')
        cls.cat_tax = env.ref('pb_me_tax.cat_tax_paper')
        # one switched-off required own field of this database would refuse
        # every send (W4) — P1's base already switches them off

    def docs_draft(self, items=None, have=None, **kw):
        kw = dict({'login_mode': 'none', 'open_case': False, 'letter': False}, **kw)
        d = self.draft(**kw)
        d['items'] = items or {}
        d['have'] = have or {}
        return d

    def items(self, code, user=None):
        out = self.studio(user).details_options({'payroll_country': code, 'name': 'DEMO NH Sari'})
        return {i['key']: i for i in out['items']}, out

    def file(self, key, data=PDF, mime='application/pdf', expiry='2031-01-01', name='paper.pdf'):
        return {'key': key, 'name': name, 'mime': mime, 'data': data,
                'issue_date': '2021-01-01', 'expiry_date': expiry}

    def proposal(self, out):
        return self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])

    def held(self, proposal):
        return self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'pb.newhire.proposal'), ('res_id', '=', proposal.id)])


@tagged('post_install', '-at_install', 'newhire')
class TestPapers(DocsCommon):

    def test_d01_seeds_and_overrides(self):
        rows = self.Paper.for_country('ID', self.company)
        self.assertEqual([(r.category_id, r.need, r.display_label()) for r in rows], [
            (self.cat_id, 'first_pay', 'KTP (identity card)'),
            (self.cat_tax, 'joining', 'NPWP card'),
            (self.cat_other, 'optional', 'Family card (Kartu Keluarga)'),
            (self.cat_cert, 'optional', 'Highest certificate')])
        self.assertEqual([r.category_id for r in self.Paper.for_country('SG', self.company)],
                         [self.cat_id, self.cat_cert])
        self.assertEqual(self.Paper.for_country('VN', self.company).mapped('need'),
                         ['first_pay', 'joining', 'optional'])
        india = self.Paper.for_country('IN', self.company)
        self.assertEqual([r.display_label() for r in india][:2], ['Aadhaar card', 'PAN card'])
        # a company row beats the shipped one; an inactive one = not needed here
        self.Paper.create({'category_id': self.cat_tax.id, 'country_code': 'ID', 'need': 'first_pay',
                           'company_id': self.company.id, 'sequence': 20})
        self.Paper.create({'category_id': self.cat_other.id, 'country_code': 'ID', 'need': 'optional',
                           'company_id': self.company.id, 'active': False})
        rows = self.Paper.for_country('ID', self.company)
        self.assertEqual(rows.mapped('category_id'), self.cat_id | self.cat_tax | self.cat_cert)
        self.assertEqual(rows.filtered(lambda r: r.category_id == self.cat_tax).need, 'first_pay')
        self.assertEqual(rows.filtered(lambda r: r.category_id == self.cat_tax).display_label(),
                         'NPWP card', 'no label of its own: the paper name')
        other = self.env['res.company'].create({'name': 'DEMO NH Other company'})
        self.assertEqual(len(self.Paper.for_country('ID', other)), 4, 'another company keeps the usual list')
        # back to the usual list
        self.studio(self.approver).papers_edit_reset('ID')
        self.assertEqual(len(self.Paper.for_country('ID', self.company)), 4)

    def test_d02_editor_gates(self):
        defaults = self.Paper.sudo().search([('company_id', '=', False)])
        before = [(r.id, r.need, r.label, r.active) for r in defaults]
        # an HR officer sees no link and is refused
        _items, out = self.items('ID')
        self.assertFalse(out['papers_editable'])
        with self.assertRaises(AccessError):
            self.studio().papers_edit_load('ID')
        with self.assertRaises(AccessError):
            self.studio().papers_edit_save('ID', [])
        with self.assertRaises(AccessError):
            self.Paper.with_user(self.maker).create({'category_id': self.cat_cert.id, 'country_code': 'MY'})
        # an HR manager changes the company's own list
        boss = self.studio(self.approver)
        _items, out = self.items('ID', self.approver)
        self.assertTrue(out['papers_editable'])
        ed = boss.papers_edit_load('ID')
        self.assertFalse(ed['custom'])
        rows = {r['category_id']: r for r in ed['rows']}
        rows[self.cat_tax.id]['need'] = 'first_pay'            # NPWP card before the first pay
        rows[self.cat_other.id]['need'] = 'none'               # no family card here
        new = [dict(rows[r['category_id']]) for r in ed['rows']]
        new.append({'category_id': self.cat_permit.id, 'need': 'joining', 'label': 'DEMO KITAS'})
        out = boss.papers_edit_save('ID', new)
        self.assertTrue(out['custom'])
        mine = self.Paper.sudo().with_context(active_test=False).search(
            [('company_id', '=', self.company.id), ('country_code', '=', 'ID')])
        self.assertEqual(set(mine.mapped('category_id')), {self.cat_tax, self.cat_other, self.cat_permit},
                         'company rows only where something changed')
        self.assertFalse(mine.filtered(lambda r: r.category_id == self.cat_other).active)
        after = [(r.id, r.need, r.label, r.active) for r in defaults]
        self.assertEqual(before, after, 'the shipped rows are never touched')
        listed = self.Paper.for_country('ID', self.company)
        self.assertIn(self.cat_permit, listed.mapped('category_id'))
        self.assertNotIn(self.cat_other, listed.mapped('category_id'))
        boss.papers_edit_reset('ID')
        self.assertFalse(self.Paper.sudo().with_context(active_test=False).search_count(
            [('company_id', '=', self.company.id)]))


@tagged('post_install', '-at_install', 'newhire')
class TestDetailsOptions(DocsCommon):

    def test_d03_items_per_country(self):
        idn, _o = self.items('ID')
        self.assertEqual(list(idn), ['personal', 'emergency', 'id_number', 'tax_number', 'tax_status',
                                     'insurance', 'bank', 'paper-%s' % self.cat_other.id,
                                     'paper-%s' % self.cat_cert.id])
        self.assertEqual(idn['id_number']['label'], 'KTP (identity card) and number')
        self.assertTrue(idn['id_number']['merged'])
        self.assertEqual(idn['id_number']['upload']['category_id'], self.cat_id.id)
        self.assertTrue(idn['id_number']['upload']['needs_expiry'])
        self.assertEqual(idn['id_number']['fields'][0]['label'], 'NIK (identity number)')
        self.assertEqual(idn['id_number']['ask_url'], '/my/details/papers?kind=national_id')
        self.assertEqual(idn['tax_number']['label'], 'NPWP card and number')
        self.assertEqual(idn['tax_number']['fields'][0]['name'], 'pb_npwp_number')
        self.assertEqual(idn['tax_number']['need'], 'first_pay')
        self.assertEqual(idn['tax_number']['ask_url'], '/my/tax/change/tax_number')
        self.assertEqual(idn['tax_status']['fields'][0]['name'], 'pb_id_ptkp_status')
        self.assertEqual(idn['tax_status']['need'], 'joining')
        ins = idn['insurance']
        self.assertFalse(ins['can_ask'])
        self.assertEqual(ins['default'], 'later')
        self.assertIn('kept by HR', ins['ask_why_not'])
        self.assertEqual({f['name'] for f in ins['fields']},
                         {'pb_bpjs_employment_number', 'pb_bpjs_health_number'})
        self.assertEqual(idn['bank']['need'], 'first_pay')
        self.assertFalse(idn['bank']['can_skip'])
        self.assertEqual([f['name'] for f in idn['bank']['fields']],
                         ['bank_name', 'account_number', 'account_holder'])
        self.assertEqual(idn['bank']['ask_url'], '/my/details/bank')
        self.assertTrue(idn['paper-%s' % self.cat_other.id]['can_ask'])
        # Singapore: few items, a tax fund, no tax number
        sg, _o = self.items('SG')
        self.assertEqual(list(sg), ['personal', 'emergency', 'id_number', 'tax_fund', 'bank',
                                    'paper-%s' % self.cat_cert.id])
        self.assertEqual(sg['id_number']['fields'][0]['label'], 'NRIC or FIN')
        # Vietnam: the tax code is a detail (no tax paper), the health check a paper
        vn, _o = self.items('VN')
        self.assertEqual(vn['tax_number']['group'], 'details')
        self.assertEqual(vn['tax_number']['fields'][0]['name'], 'vietnam_tax_code')
        self.assertEqual(vn['id_number']['label'], 'Citizen ID card and number')
        # India: PAN card merged, regime asked at joining
        ind, _o = self.items('IN')
        self.assertEqual(ind['tax_number']['label'], 'PAN card and number')
        self.assertIn('tax_regime', ind)
        # a paper the person cannot upload themselves
        self.Paper.create({'category_id': self.cat_permit.id, 'country_code': 'VN', 'need': 'joining',
                           'company_id': self.company.id, 'label': 'DEMO Work permit'})
        vn, _o = self.items('VN')
        permit = vn['paper-%s' % self.cat_permit.id]
        self.assertFalse(permit['can_ask'])
        self.assertEqual(permit['ask_why_not'], 'Only HR can add this paper.')
        self.assertEqual(permit['default'], 'later')
        # no country yet: nothing
        self.assertEqual(self.studio().details_options({})['items'], [])
        # the step 2 tile
        self.assertEqual(self.studio().decides(self.finance.id, 'ID')['papers'],
                         {'required': 2, 'optional': 2, 'first_pay': ['KTP (identity card)']})


@tagged('post_install', '-at_install', 'newhire')
class TestSendDocs(DocsCommon):

    def test_d04_send_validation(self):
        s = self.studio()
        out = s.send(self.docs_draft(items={'id_number': 'have'}))
        self.assertEqual((out['ok'], out['step'], out['field']), (False, 'docs', 'have-identification_id'))
        have = {'identification_id': 'S1234567D'}
        out = s.send(self.docs_draft(items={'id_number': 'have'}, have=have))
        self.assertEqual(out['field'], 'file-id_number')
        out = s.send(self.docs_draft(items={'bank': 'skip'}))
        self.assertEqual((out['step'], out['field']), ('docs', 'doc-bank'))
        self.assertIn('needed before the first pay', out['message'])
        out = s.send(self.docs_draft(items={'id_number': 'have'}, have=have),
                     [self.file('id_number', expiry=False)])
        self.assertEqual(out['field'], 'file-id_number')
        self.assertIn('expiry date is required', out['message'])
        out = s.send(self.docs_draft(items={'id_number': 'have'}, have=have),
                     [self.file('id_number', mime='text/plain')])
        self.assertEqual(out['message'], 'Only JPG, PNG or PDF documents are accepted.')
        big = base64.b64encode(b'0' * (10 * 1024 * 1024 + 10)).decode()
        out = s.send(self.docs_draft(items={'id_number': 'have'}, have=have), [self.file('id_number', data=big)])
        self.assertEqual(out['message'], 'Choose a non-empty file up to 10 MB.')
        cert = 'paper-%s' % self.cat_cert.id
        out = s.send(self.docs_draft(items={cert: 'have'}))
        self.assertEqual(out['field'], 'file-%s' % cert)
        # insurance kept by HR: "I have it" with nothing typed
        out = s.send(self.docs_draft(items={'insurance': 'have'}, payroll_country='VN'))
        self.assertEqual(out['step'], 'docs')
        self.assertFalse(self.env['pb.newhire.proposal'].sudo().search_count(
            [('user_id', '=', self.maker.id)]), 'nothing was proposed')

    def test_d05_details_leg(self):
        self.fast_lane()
        have = {'identification_id': '012345678901', 'vietnam_tax_code': '0123456789',
                'birthday': '1995-04-02', 'private_street': '12 Le Loi', 'private_city': 'Hue',
                'private_phone': '+84 90 111 2222', 'emergency_contact': 'DEMO Mother',
                'emergency_phone': '+84 90 333 4444', 'vietnam_social_insurance_number': 'VN-SI-77'}
        out = self.studio().send(self.docs_draft(
            payroll_country='VN', have=have,
            items={'personal': 'have', 'emergency': 'have', 'id_number': 'have', 'tax_number': 'have',
                   'insurance': 'have'}), [self.file('id_number')])
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertEqual(emp.identification_id, '012345678901')
        if 'vietnam_citizen_id' in emp._fields:
            self.assertEqual(emp.vietnam_citizen_id, '012345678901', 'both stores (VN)')
        self.assertEqual(emp.vietnam_tax_code, '0123456789')
        self.assertEqual(str(emp.birthday), '1995-04-02')
        self.assertEqual((emp.private_street, emp.private_city), ('12 Le Loi', 'Hue'))
        self.assertEqual(emp.emergency_phone, '+84 90 333 4444')
        self.assertEqual(emp.vietnam_social_insurance_number, 'VN-SI-77')
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        if 'vietnam_tax_code' in contract._fields:
            self.assertEqual(contract.vietnam_tax_code, '0123456789', 'mirrored to the contract')
        legs = {leg['key']: leg for leg in out['result']['legs']}
        self.assertTrue(legs['details']['ok'], legs)
        self.assertTrue(legs['papers']['ok'], legs)
        # pb_me_tax's own check, at SEND time
        for code, number, words in (('ID', '12.345', 'An NPWP has 15 digits'),
                                    ('IN', 'ABC123', 'A PAN has 10 characters')):
            field = 'pb_npwp_number' if code == 'ID' else 'pb_in_pan_number'
            out = self.studio().send(self.docs_draft(
                name='DEMO NH Tax %s' % code, payroll_country=code,
                items={'tax_number': 'have'}, have={field: number}),
                [self.file('tax_number')])
            self.assertFalse(out['ok'])
            self.assertEqual(out['field'], 'have-%s' % field)
            self.assertIn(words, out['message'])

    def test_d05b_singapore_two_stores(self):
        self.fast_lane()
        out = self.studio().send(self.docs_draft(items={'id_number': 'have'},
                                                 have={'identification_id': 'S1234567D'}),
                                 [self.file('id_number')])
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertEqual(emp.identification_id, 'S1234567D')
        if 'singapore_nric_fin' in emp._fields:
            self.assertEqual(emp.singapore_nric_fin, 'S1234567D')

    def test_d06_bank_through_the_studio(self):
        if 'pb.records.apply' not in self.env:
            self.skipTest('the bank second-person path is not installed')
        from odoo.addons.pb_records.tests.bank_second import ensure_second_person
        ensure_second_person(self.env, self.company)
        bank = {'bank_name': 'DBS', 'account_number': '0123 4567 8901'}
        bad = self.studio().send(self.docs_draft(items={'bank': 'have'},
                                                 have=dict(bank, account_number='12-34')))
        self.assertEqual((bad['step'], bad['field']), ('docs', 'have-account_number'))
        self.assertIn('6 to 19 digits', bad['message'])
        out = self.studio().send(self.docs_draft(items={'bank': 'have'}, have=bank))
        self.assertTrue(out['pending'], out)
        prop = self.proposal(out)
        self.assertTrue(prop.facts()['has_bank']['value'])
        rows = [str(r[2]) for r in prop._proposal_rows()]
        self.assertIn('•••• 8901', rows)
        self.assertNotIn('012345678901', ' '.join(rows))
        self.approve(out)
        emp = self.hires()
        req = self.env['pb.bank.change.request'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(req), 1)
        self.assertIn(req.state, ('hr_review', 'finance_review'), 'waits for a second person')
        self.assertEqual(req.proposed_by_id, self.maker, 'proposed by who typed it')
        self.assertEqual(req.x_account_name, 'DEMO NH Sari Wulandari', 'holder: the name')
        self.assertFalse(emp.pb_bank_on_record, 'not payroll-ready until approved')
        legs = {leg['key']: leg for leg in prop.result()['legs']}
        self.assertTrue(legs['bank']['ok'], legs)


@tagged('post_install', '-at_install', 'newhire')
class TestPapersHeld(DocsCommon):

    def _send_cert(self, **kw):
        cert = 'paper-%s' % self.cat_cert.id
        return self.studio().send(self.docs_draft(items={cert: 'have'}, **kw),
                                  [self.file(cert, data=PNG, mime='image/png', expiry=False,
                                             name='degree.png')])

    def test_d07_papers_wait_with_the_hire(self):
        out = self._send_cert()
        self.assertTrue(out['pending'], out)
        prop = self.proposal(out)
        held = self.held(prop)
        self.assertEqual(len(held), 1)
        self.assertFalse(held.public)
        self.assertEqual(list(prop.pb_nh_files), ['paper-%s' % self.cat_cert.id])
        self.assertFalse(self.env['pb.employee.document'].sudo().search_count(
            [('attachment_id', '=', held.id)]), 'on no employee while it waits')
        self.assertNotIn(PNG, prop.payload_json)
        self.approve(out)
        emp = self.hires()
        doc = self.env['pb.employee.document'].sudo().search(
            [('employee_id', '=', emp.id), ('category_id', '=', self.cat_cert.id)])
        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.name, self.cat_cert.name, 'Singapore lists it by its own name')
        self.assertFalse(doc.verified, 'HR verifies it on the record')
        self.assertEqual(base64.b64decode(doc.attachment_id.datas), base64.b64decode(PNG))
        self.assertFalse(held.exists(), 'the held file is gone')
        self.assertFalse(prop.pb_nh_files)
        self.assertNotIn(PNG, prop.result_json or '')

    def test_d07b_reject_and_withdraw_drop_the_files(self):
        out = self._send_cert()
        held = self.held(self.proposal(out))
        self.assertTrue(held)
        self.approve(out, action='reject')
        self.assertFalse(held.exists(), 'rejected: the file is deleted')
        out = self._send_cert(name='DEMO NH Second')
        held = self.held(self.proposal(out))
        answer = self.studio().withdraw(out['proposal_id'])
        self.assertTrue(answer['ok'], answer)
        self.assertFalse(held.exists(), 'withdrawn: the file is deleted')

    def test_d07c_fast_lane(self):
        self.fast_lane()
        out = self._send_cert()
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertEqual(self.env['pb.employee.document'].sudo().search_count(
            [('employee_id', '=', emp.id), ('category_id', '=', self.cat_cert.id)]), 1)
        self.assertFalse(self.held(self.proposal(out)), 'nothing held in the fast lane')


@tagged('post_install', '-at_install', 'newhire')
class TestAsks(DocsCommon):

    def test_d08_asks_and_refresh(self):
        self.fast_lane()
        out = self.studio().send(self.docs_draft(personal=''))
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        Ask = self.env['pb.new.hire.ask'].sudo()
        rows = {r.key: r for r in Ask.search([('employee_id', '=', emp.id)])}
        cert = 'paper-%s' % self.cat_cert.id
        self.assertEqual(set(rows), {'personal', 'emergency', 'id_number', 'tax_fund', 'bank', cert})
        self.assertEqual(rows['bank'].url, '/my/details/bank')
        self.assertEqual(rows['tax_fund'].url, '/my/tax/change/tax_fund')
        self.assertEqual(rows['id_number'].category_id, self.cat_id, 'the card is asked with the number')
        self.assertEqual(rows['bank'].need, 'first_pay')
        self.assertEqual(rows['bank'].proposal_id, self.proposal(out))
        self.assertTrue(all(r.state == 'open' for r in rows.values()))
        summary = Ask.summary(emp)
        self.assertEqual((summary['total'], summary['open'], summary['done']), (6, 6, 0))
        # waiting: the product's own open requests
        self.env['pb.profile.change.request'].sudo().create(
            {'employee_id': emp.id, 'state': 'hr_review', 'x_phone': '+65 1'})
        self.env['pb.me.detail.request'].sudo().create(
            {'employee_id': emp.id, 'kind': 'id_paper', 'state': 'hr_review', 'company_id': self.company.id})
        self.env['pb.me.detail.request'].sudo().create(
            {'employee_id': emp.id, 'kind': 'tax_fund', 'state': 'hr_review', 'company_id': self.company.id})
        self.env['pb.bank.change.request'].sudo().create(
            {'employee_id': emp.id, 'pb_origin': 'import', 'state': 'hr_review'})
        Ask.search([('employee_id', '=', emp.id)]).refresh()
        state = {r.key: r.state for r in Ask.search([('employee_id', '=', emp.id)])}
        self.assertEqual(state, {'personal': 'waiting', 'emergency': 'waiting', 'id_number': 'waiting',
                                 'tax_fund': 'waiting', 'bank': 'waiting', cert: 'open'})
        # done: the values on the record, the papers in the documents
        emp.sudo().write({'private_phone': '+65 2', 'private_street': '1 Orchard Road',
                          'emergency_contact': 'DEMO Mum', 'emergency_phone': '+65 3',
                          'identification_id': 'S7654321A', 'pb_sg_shg_fund': 'cdac'})
        if 'vietnam_bank_account_number' in emp._fields:
            emp.sudo().vietnam_bank_account_number = '998877665544'
        att = self.env['ir.attachment'].sudo().create({'name': 'x.pdf', 'datas': PDF, 'mimetype': 'application/pdf'})
        Doc = self.env['pb.employee.document'].sudo()
        Doc.create({'employee_id': emp.id, 'category_id': self.cat_cert.id, 'name': 'Degree',
                    'attachment_id': att.id})
        summary = Ask.summary(emp)
        state = {i['key']: i['state'] for i in summary['items']}
        self.assertEqual(state['personal'], 'done')
        self.assertEqual(state['emergency'], 'done')
        self.assertEqual(state['tax_fund'], 'done')
        self.assertEqual(state[cert], 'done')
        self.assertEqual(state['id_number'], 'waiting', 'number there, the card not yet')
        att2 = self.env['ir.attachment'].sudo().create({'name': 'y.pdf', 'datas': PDF, 'mimetype': 'application/pdf'})
        Doc.create({'employee_id': emp.id, 'category_id': self.cat_id.id, 'name': 'ID',
                    'attachment_id': att2.id, 'expiry_date': '2031-01-01'})
        state = {i['key']: i['state'] for i in Ask.summary(emp)['items']}
        self.assertEqual(state['id_number'], 'done')
        if 'vietnam_bank_account_number' in emp._fields:
            self.assertEqual(state['bank'], 'done')
        self.assertTrue(Ask.search([('employee_id', '=', emp.id), ('key', '=', 'personal')]).done_on)
        legs = {leg['key']: leg for leg in out['result']['legs']}
        self.assertTrue(legs['asks']['ok'])
        self.assertIn('6 things to ask', legs['asks']['message'])

    def test_d08b_nothing_asked_when_all_with_hr(self):
        self.fast_lane()
        items = {k: 'skip' for k in ('personal', 'emergency', 'tax_fund', 'paper-%s' % self.cat_cert.id)}
        items.update(id_number='have', bank='have')
        out = self.studio().send(self.docs_draft(
            items=items, have={'identification_id': 'S1234567D', 'bank_name': 'DBS',
                               'account_number': '123456789'}), [self.file('id_number')])
        self.assertTrue(out['applied'], out)
        self.assertFalse(self.env['pb.new.hire.ask'].sudo().search_count(
            [('employee_id', '=', self.hires().id)]))


@tagged('post_install', '-at_install', 'newhire')
class TestLetterAndRows(DocsCommon):

    def test_d09_letter_without_the_pay_right(self):
        payroll_mgr = self.env.ref('om_hr_payroll.group_hr_payroll_manager')
        self.assertNotIn(payroll_mgr, self.approver.all_group_ids)
        letter = self.studio().welcome_options(self.docs_draft())['letter']
        self.assertTrue(letter['available'], 'no fast-lane switch-off any more')
        self.assertNotIn('approver_note', letter)
        out = self.studio().send(self.docs_draft(letter=True))
        self.assertTrue(out['pending'], out)
        self.approve(out)
        emp = self.hires()
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        doc = self.env['pb.employee.document'].sudo().search([('pbdc_contract_id', '=', contract.id)])
        self.assertEqual(len(doc), 1, 'the letter was made for the approver')
        legs = {leg['key']: leg for leg in self.proposal(out).result()['legs']}
        self.assertTrue(legs['letter']['ok'], legs)
        # the gate is open for that one call only
        self.assertFalse(self.env['pb.contracts'].with_user(self.approver)._cd_unmask_wage())

    def test_d10_rows_masked_no_file_in_payload(self):
        have = {'identification_id': 'S1234567D', 'bank_name': 'DBS', 'account_number': '123456789'}
        out = self.studio().send(self.docs_draft(items={'id_number': 'have', 'bank': 'have'}, have=have),
                                 [self.file('id_number')])
        self.assertTrue(out['pending'], out)
        prop = self.proposal(out)
        rows = {str(r[0]): str(r[2]) for r in prop._proposal_rows()}
        self.assertEqual(rows['NRIC or FIN'], '•••• 567D')
        self.assertEqual(rows['Account number'], '•••• 6789')
        self.assertEqual(rows['Papers attached'], 'NRIC or work pass')
        self.assertIn('Bank', rows)
        self.assertIn('Personal details', rows['Will be asked'])
        blob = json.dumps(prop.payload()) + (prop.result_json or '') + (prop.facts_json or '')
        self.assertNotIn(PDF, blob)
        self.assertNotIn('data', json.dumps(prop.payload().get('values', {}).get('pb_nh_papers')))
