# -*- coding: utf-8 -*-
"""WDGAP S2-D — tax details proposed on My Payobook, approved by HR.

Numbers follow the handover's test list (T1 … T10). Every employee-side call
is made as a real PORTAL login (`with_user(portal)`), the way /my/tax calls
it.
"""
import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import PNG, TaxCase, decide


@tagged('post_install', '-at_install', 'wdgap_s2d')
class TestS2dTaxFlow(TaxCase):

    # ---------------------------------------------------------------- T1
    def test_t1_own_employee_only(self):
        # somebody else's employee record is refused before anything is made
        with self.assertRaises(AccessError):
            self._ask('tax_number', {'t_number': '0312345678'},
                      upload=self._pdf(), emp=self.other)
        # a draft of somebody else cannot be re-sent through request_id
        theirs = self._ask('tax_number', {'t_number': '0398765432'},
                           upload=self._pdf(), emp=self.other, user=self.portal2)
        decide(self.env, theirs, 'return', 'Wrong file')
        with self.assertRaises(AccessError):
            self._ask('tax_number', {'t_number': '0312345678'},
                      upload=self._pdf(), request_id=theirs.id)
        # the form cannot set the employee, the state or the country
        req = self._ask('tax_number', {'t_number': '0312345678',
                                       'employee_id': self.other.id,
                                       'state': 'approved', 't_country': 'IN'},
                        upload=self._pdf())
        self.assertEqual(req.employee_id, self.emp)
        self.assertEqual(req.state, 'hr_review')
        self.assertEqual(req.t_country, 'VN')
        # a portal login has no right on the model itself
        with self.assertRaises(AccessError):
            self.Req.with_user(self.portal).search([])
        with self.assertRaises(AccessError):
            self.Req.with_user(self.portal).sudo(False).create({
                'employee_id': self.emp.id, 'company_id': self.company.id,
                'kind': 'tax_number'})

    # ---------------------------------------------------------------- T2
    def _approve_cycle(self, kind, values, field, expected, upload=True):
        before = self.emp.sudo()[field]
        req = self._ask(kind, values, upload=self._pdf() if upload else None)
        self.assertEqual(req.state, 'hr_review')
        self.assertEqual(req.approval_request_id.process_id.key, 'me_details')
        self.emp.invalidate_recordset()
        self.assertEqual(self.emp.sudo()[field], before,
                         '%s: nothing changes before HR approves' % kind)
        decide(self.env, req)
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self.emp.sudo()[field], expected)
        return req

    def test_t2a_vietnam_tax_code(self):
        self._approve_cycle('tax_number', {'t_number': '03-1234 5678'},
                            'vietnam_tax_code', '0312345678')

    def test_t2b_indonesia_npwp_ptkp_and_nik(self):
        self._pay_by(self.emp, 'ID')
        self._approve_cycle('tax_number', {'t_number': '09.254.294.3-407.000'},
                            'pb_npwp_number', '092542943407000')
        self._approve_cycle('tax_status', {'t_ptkp': 'K/1'},
                            'pb_id_ptkp_status', 'K/1')
        # the NIK on record used as NPWP
        req = self._approve_cycle('tax_number', {'t_use_nik': '1'},
                                  'pb_npwp_number', '3174012345678901')
        self.assertTrue(req.t_use_nik)

    def test_t2c_india_pan_and_regime(self):
        self._pay_by(self.emp, 'IN')
        self._approve_cycle('tax_number', {'t_number': 'abcde1234f'},
                            'pb_in_pan_number', 'ABCDE1234F')
        self._approve_cycle('tax_regime', {'t_regime': 'old'},
                            'pb_in_tax_regime', 'old')

    def test_t2d_singapore_fund_without_proof(self):
        self._pay_by(self.emp, 'SG')
        self._approve_cycle('tax_fund', {'t_fund': 'cdac'}, 'pb_sg_shg_fund',
                            'cdac', upload=False)

    def test_t2e_refuse_and_send_back_write_nothing(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        decide(self.env, req, 'reject', 'Not your number')
        self.assertEqual(req.state, 'refused')
        self.assertEqual(req.decision_note, 'Not your number')
        self.assertFalse(self.emp.sudo().vietnam_tax_code)
        req2 = self._ask('tax_number', {'t_number': '0312345678'},
                         upload=self._pdf())
        decide(self.env, req2, 'return', 'Unreadable scan')
        self.assertEqual(req2.pb_portal_state(), 'sent_back')
        self.assertFalse(self.emp.sudo().vietnam_tax_code)
        # changed and sent again: the same request, the old proof kept
        again = self._ask('tax_number', {'t_number': '0312345679'},
                          request_id=req2.id)
        self.assertEqual(again, req2)
        self.assertEqual(again.state, 'hr_review')
        self.assertTrue(again.attachment_id)
        decide(self.env, again)
        self.assertEqual(self.emp.sudo().vietnam_tax_code, '0312345679')

    def test_t2f_one_open_request_per_kind_and_checks(self):
        self._ask('tax_number', {'t_number': '0312345678'}, upload=self._pdf())
        with self.assertRaises(UserError):
            self._ask('tax_number', {'t_number': '0312345670'},
                      upload=self._pdf())
        # a kind the country does not offer
        with self.assertRaises(UserError):
            self._ask('tax_regime', {'t_regime': 'old'}, upload=self._pdf())
        # bad numbers, in plain words
        self._pay_by(self.emp, 'IN')
        with self.assertRaisesRegex(UserError, 'PAN'):
            self._ask('tax_number', {'t_number': '12345'}, upload=self._pdf())
        self._pay_by(self.emp, 'ID')
        with self.assertRaisesRegex(UserError, 'NPWP'):
            self._ask('tax_number', {'t_number': '1234'}, upload=self._pdf())
        self.emp.sudo().pb_id_ptkp_status = 'TK/0'
        with self.assertRaises(UserError):
            self._ask('tax_status', {'t_ptkp': 'TK/0'}, upload=self._pdf())
        with self.assertRaises(UserError):
            self._ask('tax_status', {'t_ptkp': 'nonsense'}, upload=self._pdf())

    def test_t2g_withdraw_writes_nothing(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        req.with_user(self.portal).pb_portal_withdraw()
        self.assertEqual(req.state, 'draft')
        self.assertFalse(self.emp.sudo().vietnam_tax_code)

    # ---------------------------------------------------------------- T3
    def test_t3_proof_required_stored_once_one_savepoint(self):
        Att = self.env['ir.attachment'].sudo()
        for code, kind, values in (('VN', 'tax_number', {'t_number': '0312345678'}),
                                   ('ID', 'tax_status', {'t_ptkp': 'K/2'}),
                                   ('IN', 'tax_regime', {'t_regime': 'old'})):
            self._pay_by(self.emp, code)
            with self.assertRaisesRegex(UserError, 'scan'):
                self._ask(kind, values)
        self.assertFalse(self.Req.search_count([('employee_id', '=', self.emp.id)]))
        # a failure after the file was made leaves neither request nor file
        self._pay_by(self.emp, 'VN')
        n_att = Att.search_count([('res_model', '=', 'pb.me.detail.request')])
        with patch.object(type(self.Req), '_pb_send',
                          side_effect=UserError('boom')):
            with self.assertRaises(UserError):
                self._ask('tax_number', {'t_number': '0312345678'},
                          upload=self._pdf())
        self.assertFalse(self.Req.search_count([('employee_id', '=', self.emp.id)]))
        self.assertEqual(Att.search_count([('res_model', '=', 'pb.me.detail.request')]),
                         n_att)
        # wrong file kind refused
        with self.assertRaises(UserError):
            self._ask('tax_number', {'t_number': '0312345678'},
                      upload=(b'MZ\x90', 'x.exe', 'application/x-msdownload'))
        # approved: the SAME file moves into the person's documents, verified
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        att = req.attachment_id
        checksum = att.checksum
        decide(self.env, req)
        doc = req.document_id
        self.assertTrue(doc.verified)
        self.assertEqual(doc.attachment_id, att)
        self.assertEqual(doc.category_id, self.env.ref('pb_me_tax.cat_tax_paper'))
        self.assertEqual((att.res_model, att.res_id), ('pb.employee.document', doc.id))
        self.assertEqual(Att.search_count([('checksum', '=', checksum)]), 1,
                         'the proof is stored once')

    def test_t3b_resend_with_a_new_file_replaces_the_old(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        old = req.attachment_id
        decide(self.env, req, 'return', 'Unreadable')
        self._ask('tax_number', {'t_number': '0312345678'},
                  upload=(PNG, 'new.png', 'image/png'), request_id=req.id)
        self.assertFalse(old.exists())
        self.assertEqual(req.attachment_id.name, 'new.png')

    # ---------------------------------------------------------------- T4
    def test_t4_masking(self):
        self._pay_by(self.emp, 'ID')
        self.emp.sudo().write({'pb_npwp_number': '092542943407000',
                               'pb_bpjs_employment_number': '12345678901',
                               'pb_bpjs_health_number': '0001234567890'})
        data = self.emp.with_user(self.portal).sudo()._pbtx_portal_data()
        by_key = {r['key']: r for r in data['rows']}
        self.assertEqual(by_key['number']['value'], '•••• 7000')
        self.assertEqual(by_key['pb_bpjs_employment_number']['value'], '•••• 8901')
        self.assertEqual(by_key['pb_bpjs_health_number']['value'], '•••• 7890')
        self.assertIsNone(by_key['pb_bpjs_health_number']['kind'], 'BPJS is view only')
        text = json.dumps(data, default=str)
        for full in ('092542943407000', '12345678901', '0001234567890'):
            self.assertNotIn(full, text)
        req = self._ask('tax_number', {'t_number': '092542943407001'},
                        upload=self._pdf())
        self.assertNotIn('092542943407001', req.pb_label())
        rows = req._pb_rows(full=False)
        self.assertEqual(rows[0][1:], ('•••• 7000', '•••• 7001'))
        # HR, in the inbox, sees the whole number to compare with the proof
        detail = req._approval_detail(req.approval_request_id)
        self.assertEqual(detail['rows'][0]['cells'],
                         ['092542943407000', '092542943407001'])
        # My requests: masked title, tax label, tax page link
        rows = self.env['pb.me.home'].with_user(self.portal).get_my_requests(
            self.emp)['rows']
        mine = [r for r in rows if r['id'] == req.id and r['model'] == self.Req._name]
        self.assertEqual(mine[0]['url'], '/my/tax/request/%s' % req.id)
        self.assertEqual(mine[0]['kind'], 'Tax details')
        self.assertNotIn('092542943407001', mine[0]['title'])

    # ---------------------------------------------------------------- T5
    def test_t5_country_follows_the_scheme(self):
        Emp = self.emp.with_user(self.portal).sudo()
        expect = {'VN': {'number'}, 'ID': {'number', 'ptkp',
                                           'pb_bpjs_employment_number',
                                           'pb_bpjs_health_number'},
                  'IN': {'number', 'regime', 'uan'},
                  'SG': {'nric', 'residency', 'fund'}}
        for code, keys in expect.items():
            self._pay_by(self.emp, code)
            data = Emp._pbtx_portal_data()
            self.assertEqual(data['country'], code)
            self.assertTrue(data['supported'])
            self.assertEqual({r['key'] for r in data['rows']}, keys, code)
        self._pay_by(self.emp, 'MY')
        data = Emp._pbtx_portal_data()
        self.assertFalse(data['supported'])
        self.assertEqual(data['rows'], [])
        # nobody's scheme: a plain message, no rows
        Config = type(self.env['hr.formula.config'])
        with patch.object(Config, 'schemes_for_employee',
                          lambda self, employee: self.browse()):
            data = Emp._pbtx_portal_data()
            self.assertEqual(data['country'], '')
            self.assertFalse(data['supported'])
            with self.assertRaises(UserError):
                self._ask('tax_number', {'t_number': '0312345678'},
                          upload=self._pdf())

    # ---------------------------------------------------------------- T6
    def test_t6_approver_without_payroll_group(self):
        self.assertFalse(self.hr.has_group('om_hr_payroll.group_hr_payroll_user'))
        self._pay_by(self.emp, 'IN')
        req = self._ask('tax_regime', {'t_regime': 'old'}, upload=self._pdf())
        user = decide(self.env, req)
        self.assertEqual(user, self.hr)
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self.emp.sudo().pb_in_tax_regime, 'old')
        self.assertEqual(req.document_id.verified_by, self.hr)

    # ---------------------------------------------------------------- T7
    def _vn_contract(self, registered):
        Template = self.env['hr.contract.advantage.template'].sudo()
        tpl = Template.search([('code', '=', 'VNREGISTER')], limit=1) or \
            Template.create({'name': 'Registered tax dependents',
                             'code': 'VNREGISTER', 'lower_bound': 0,
                             'upper_bound': 20, 'default_value': 0})
        contract = self.env['hr.contract'].sudo().create({
            'name': 'DEMO S2D contract', 'employee_id': self.emp.id,
            'company_id': self.company.id, 'wage': 10_000_000.0,
            'state': 'open', 'date_start': '2026-01-01'})
        contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id == tpl).unlink()
        line = self.env['hr.contract.advantage'].sudo().create({
            'contract_id': contract.id, 'advantage_template_id': tpl.id,
            'amount': registered})
        return contract, line

    def test_t7_vietnam_dependants_mismatch_note(self):
        contract, line = self._vn_contract(1)
        self._pay_by(self.emp, 'VN')
        Dep = self.env['vietnam.employee.dependent'].sudo()
        for name in ('DEMO Child A', 'DEMO Child B'):
            Dep.create({'employee_id': self.emp.id, 'name': name,
                        'relationship': 'child', 'status': 'eligible',
                        'effective_from': '2025-01-01'})
        self.emp.invalidate_recordset()
        note = self.emp.with_user(self.hr).pb_vn_dependants_check
        self.assertTrue(note)
        self.assertIn('2', note)
        self.assertIn('1', note)
        # HR's Full details shows it; the inbox shows it on a VN tax request
        details = self.env['pb.people'].with_user(self.hr)._e360_details(
            self.emp.with_user(self.hr), True)
        keys = [g['key'] for g in details['pay']]
        self.assertIn('vn_deps', keys)
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        chips = req._approval_detail(req.approval_request_id)['chips']
        self.assertIn('Tax dependants', [c['label'] for c in chips])
        decide(self.env, req)
        # never changes the contract component
        self.assertEqual(line.amount, 1)
        self.assertEqual(len(contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id.code == 'VNREGISTER')), 1)
        # the employee page lists the dependants, not the note
        data = self.emp.with_user(self.portal).sudo()._pbtx_portal_data()
        self.assertEqual(len(data['dependants']), 2)
        self.assertNotIn('Does not match', json.dumps(data, default=str))
        # equal numbers: no note, no group
        line.amount = 2
        self.emp.invalidate_recordset()
        self.assertFalse(self.emp.with_user(self.hr).pb_vn_dependants_check)
        details = self.env['pb.people'].with_user(self.hr)._e360_details(
            self.emp.with_user(self.hr), True)
        self.assertNotIn('vn_deps', [g['key'] for g in details['pay']])

    def test_t7b_full_details_india_and_singapore_groups(self):
        self._pay_by(self.emp, 'IN')
        self.emp.sudo().write({'pb_in_pan_number': 'ABCDE1234F',
                               'pb_in_tax_regime': 'new'})
        details = self.env['pb.people'].with_user(self.hr)._e360_details(
            self.emp.with_user(self.hr), True)
        groups = {g['key']: g for g in details['pay']}
        self.assertIn('in', groups)
        self.assertNotIn('sg', groups)
        self._pay_by(self.emp, 'SG')
        details = self.env['pb.people'].with_user(self.hr)._e360_details(
            self.emp.with_user(self.hr), True)
        groups = {g['key']: g for g in details['pay']}
        self.assertIn('sg', groups)
        self.assertIn('in', groups, 'a typed-in PAN still opens the India group')

    # ---------------------------------------------------------------- T8
    def test_t8_sources_registered_unused_and_readable(self):
        cfg = self.schemes['ID']
        catalogue = cfg._application_source_catalogue()
        for key in ('tax.id_ptkp_status', 'tax.in_pan_number', 'tax.in_tax_regime',
                    'tax.sg_shg_fund', 'tax.vn_confirmed_dependants'):
            self.assertIn(key, catalogue)
            self.assertFalse(catalogue[key]['writable'])
        Rule = self.env['hr.formula.rule'].sudo().with_context(active_test=False)
        self.assertFalse(Rule.search_count([('application_source_key', '=like', 'tax.%')]),
                         'no scheme is wired to a tax detail')
        # a scheme with no rule mapped asks nothing of this module
        self.assertFalse({k for k in cfg._application_domain_values(
            self.emp, self.env['hr.contract'], '2026-06-01', '2026-06-30')
            if k.startswith('tax.')})
        # a scheme that IS mapped reads the approved value (code, not label)
        self._pay_by(self.emp, 'ID')
        Rule.create({'config_id': cfg.id, 'name': 'PTKP', 'code': 'STWODPTKP',
                     'column_type': 'input', 'value_kind': 'text',
                     'application_source_key': 'tax.id_ptkp_status',
                     'category_id': self.env['hr.salary.rule.category'].search(
                         [], limit=1).id,
                     'sequence': 1})
        cfg.invalidate_recordset()
        got = cfg.with_user(self.pay_formula)._application_domain_values(
            self.emp.with_user(self.pay_formula), self.env['hr.contract'],
            '2026-06-01', '2026-06-30')
        self.assertEqual(got['tax.id_ptkp_status']['status'], 'missing')
        req = self._ask('tax_status', {'t_ptkp': 'K/1'}, upload=self._pdf())
        got = cfg.with_user(self.pay_formula)._application_domain_values(
            self.emp.with_user(self.pay_formula), self.env['hr.contract'],
            '2026-06-01', '2026-06-30')
        self.assertEqual(got['tax.id_ptkp_status']['status'], 'missing',
                         'a waiting change is not read')
        decide(self.env, req)
        got = cfg.with_user(self.pay_formula)._application_domain_values(
            self.emp.with_user(self.pay_formula), self.env['hr.contract'],
            '2026-06-01', '2026-06-30')
        self.assertEqual((got['tax.id_ptkp_status']['status'],
                          got['tax.id_ptkp_status']['value']), ('resolved', 'K/1'))

    # ---------------------------------------------------------------- T9
    def test_t9_silent_install(self):
        Data = self.env['ir.model.data'].sudo()
        made = Data.search([('module', '=', 'pb_me_tax')])
        self.assertFalse(made.filtered(lambda d: d.model in (
            'ir.cron', 'mail.template', 'ir.ui.menu', 'biz.approval.process',
            'biz.approval.binding', 'hr.formula.rule', 'hr.formula.config')))
        self.assertTrue(made.filtered(lambda d: d.model == 'pb.employee.document.category'))
        # nothing waiting, nothing asked, nothing set on anybody
        Req = self.env['pb.me.detail.request'].sudo()
        self.assertFalse(Req.search_count([('kind', 'in', ['tax_number', 'tax_status',
                                                            'tax_regime', 'tax_fund']),
                                           ('employee_id', 'not in', (self.emp | self.other).ids)]))
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        for field in ('pb_id_ptkp_status', 'pb_in_pan_number', 'pb_in_tax_regime',
                      'pb_in_uan_number', 'pb_sg_tax_residency', 'pb_sg_shg_fund'):
            self.assertFalse(Emp.search_count([(field, '!=', False)]), field)
        # the home shows no tax row for a person with nothing sent back
        put = []
        self.env['pb.me.home'].with_user(self.portal).sudo()._pbme_needs_extra(
            self.emp.sudo(), lambda key, n, url, **kw: put.append((key, n)))
        self.assertNotIn('tax_sent_back', [k for k, n in put if n])

    # --------------------------------------------------------------- T10
    def test_t10_privacy_of_requests_and_proofs(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        att = req.attachment_id
        self.env.flush_all()
        self.env.invalidate_all()
        for user in (self.portal2, self.manager_user, self.pay_only):
            with self.assertRaises(AccessError, msg=user.login):
                self.Req.with_user(user).browse(req.id).read(['t_number'])
            with self.assertRaises(AccessError, msg=user.login):
                self.env['ir.attachment'].with_user(user).browse(att.id).read(['datas'])
        # an internal login a route did not ask finds nothing at all
        for user in (self.manager_user, self.pay_only):
            self.assertFalse(self.Req.with_user(user).search_count([]), user.login)
        # HR reads the request and the proof
        self.assertEqual(self.Req.with_user(self.hr).browse(req.id).t_number,
                         '0312345678')
        self.assertTrue(self.Req.with_user(self.hr).browse(req.id).t_proof_file)
        # after approval the proof sits in the documents: still not theirs
        decide(self.env, req)
        self.env.flush_all()
        self.env.invalidate_all()
        for user in (self.portal2, self.manager_user, self.pay_only):
            with self.assertRaises(AccessError, msg=user.login):
                self.env['ir.attachment'].with_user(user).browse(att.id).read(['datas'])
        # the tax fields themselves are HR-only
        for user in (self.manager_user, self.pay_only):
            with self.assertRaises(AccessError, msg=user.login):
                self.env['hr.employee'].with_user(user).browse(self.emp.id).read(
                    ['vietnam_tax_code', 'pb_in_pan_number'])

    # ------------------------------------------------- the My details seams
    def test_t13_my_details_page_and_home_stay_their_own(self):
        req = self._ask('tax_number', {'t_number': '0312345678'},
                        upload=self._pdf())
        decide(self.env, req, 'return', 'Please send a clearer scan')
        # My details' own sent-back row does not count the tax change …
        put = {}
        self.env['pb.me.home'].with_user(self.portal).sudo()._pbme_needs_extra(
            self.emp.sudo(), lambda key, n, url, **kw: put.setdefault(key, (n, url)))
        self.assertNotIn('details_sent_back', put)
        # … the tax row does, and links to the tax page
        self.assertEqual(put['tax_sent_back'], (1, '/my/tax'))
        self.assertIn(('kind', 'not in', ['tax_number', 'tax_status', 'tax_regime',
                                          'tax_fund']), self.Req._pb_page_domain())
        # the family flow is untouched: a family change still counts there
        fam = self.Req.with_user(self.portal).pb_portal_create(
            self.emp, 'marital', {'marital': 'married'})
        decide(self.env, fam, 'return', 'Which date?')
        put = {}
        self.env['pb.me.home'].with_user(self.portal).sudo()._pbme_needs_extra(
            self.emp.sudo(), lambda key, n, url, **kw: put.setdefault(key, (n, url)))
        self.assertEqual(put['details_sent_back'][0], 1)
        self.assertEqual(fam.pb_label(), 'Marital status')
        # the fingerprint of a non-tax request carries no tax key
        self.assertNotIn('tax', fam._chain_revision_values())
        self.assertIn('tax', req._chain_revision_values())
