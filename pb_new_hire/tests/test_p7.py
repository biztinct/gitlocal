# -*- coding: utf-8 -*-
"""NEWHIRE P7 — the Country of work leads step 2; the bank row follows the
account's country. Numbers match the P7 handover (C1–C6, B3, B5 through the
studio; B1/B2/B4/B6 are in pb_bank_ocr's test_p7_bank_formats.py)."""
import json
import statistics
import time

from odoo.tests import tagged

from .test_docs import DocsCommon


@tagged('post_install', '-at_install', 'newhire')
class TestP7Places(DocsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Emp = env['hr.employee']
        Dept = env['hr.department'].with_company(cls.company)
        cls.mixed = Dept.create({'name': 'DEMO NH Mixed', 'company_id': cls.company.id})
        # rule (b): the farm's people work in India; the mixed team in India and Singapore
        cls.farmer = Emp.create({'name': 'DEMO NH Farmer', 'company_id': cls.company.id,
                                 'department_id': cls.farm.id, 'payroll_country': 'IN',
                                 'job_id': cls.agronomist.id})
        for name, code in (('DEMO NH Mixed A', 'IN'), ('DEMO NH Mixed B', 'SG'), ('DEMO NH Mixed C', 'SG')):
            Emp.create({'name': name, 'company_id': cls.company.id, 'department_id': cls.mixed.id,
                        'payroll_country': code})

    def places(self, code, **kw):
        return self.studio().places(code, kw.get('team', False), kw.get('job', False), '2026-12-07',
                                    'permanent', kw.get('clear', False))

    # ================================================================ C1
    def test_c1_which_teams_belong(self):
        sg = self.places('SG')['teams']
        self.assertIn(self.finance.id, sg['mine'], '(a) paid by a Singapore scheme')
        self.assertIn(self.mixed.id, sg['mine'], '(b) somebody works in Singapore')
        self.assertIn(self.ops.id, sg['other'], 'paid by a Vietnam scheme')
        self.assertIn(self.farm.id, sg['other'], 'its people work in India')
        self.assertIn(self.lonely.id, sg['unknown'], 'no signal: always offered')
        india = self.places('IN')
        self.assertEqual({self.farm.id, self.mixed.id} & set(india['teams']['mine']), {self.farm.id, self.mixed.id})
        self.assertIn(self.finance.id, india['teams']['other'])
        self.assertIn(self.agronomist.id, india['jobs'], 'a job held by somebody working in India')
        self.assertEqual(india['team_people'][str(self.mixed.id)], 1)
        self.assertIn(self.farmer.id, [m['id'] for m in india['managers']])
        every = set().union(*india['teams'].values())
        self.assertTrue({self.finance.id, self.ops.id, self.lonely.id, self.farm.id, self.mixed.id} <= every,
                        'never stuck: every team is in one of the three lists')

    def test_c1b_only_scheme_and_no_links(self):
        """A company paid by ONE scheme and with nobody's country set (rize
        before its map): nothing is hidden — every team is "Other teams"."""
        env = self.env
        company = env['res.company'].create({'name': 'DEMO NH Bare', 'country_id': self.vn.id})
        env['hr.formula.config'].create({'name': 'DEMO NH Only', 'code': 'DEMONHONLY', 'country_code': 'VN',
                                         'state': 'active', 'company_id': company.id})
        teams = env['hr.department'].create([{'name': 'DEMO NH Bare %s' % i, 'company_id': company.id}
                                             for i in range(3)])
        self.maker.sudo().write({'company_ids': [(4, company.id)]})
        out = self.env['pb.new.hire'].with_user(self.maker).with_context(
            allowed_company_ids=[company.id]).with_company(company).places('VN')
        self.assertFalse(out['teams']['mine'], '"the only scheme" says nothing about a team')
        self.assertFalse(out['teams']['other'])
        self.assertTrue(set(teams.ids) <= set(out['teams']['unknown']))
        self.assertEqual(out['decides']['currency']['name'], 'VND')

    # ================================================================ C2
    def test_c2_country_change_clears_with_reason(self):
        out = self.places('IN', team=self.finance.id, job=self.accountant.id, clear=True)
        self.assertIs(out['team_fits'], False)
        self.assertIs(out['job_fits'], False, "the job is the team's own")
        self.assertEqual(out['team_reason'], 'DEMO NH Finance has no one in India.')
        self.assertFalse(out['decides']['scheme'], 'worked out without the cleared team')
        self.assertFalse(out['decides']['problem'])
        self.assertEqual(out['decides']['currency']['name'], 'INR')
        # Undo / a team picked from "other countries": kept, the mismatch says so
        kept = self.places('IN', team=self.finance.id, job=self.accountant.id)
        self.assertEqual(kept['decides']['scheme']['id'], self.sg_scheme.id)
        self.assertIn('India', kept['decides']['problem'])
        # a team that fits stays
        fits = self.places('IN', team=self.mixed.id, clear=True)
        self.assertIs(fits['team_fits'], True)
        unknown = self.places('IN', team=self.lonely.id, clear=True)
        self.assertIs(unknown['team_fits'], True, 'a team with no signal is never cleared')

    # ================================================================ C3
    def test_c3_default_country(self):
        s = self.studio()
        # the company's people: India 2 (farmer, mixed A), Singapore 3 (mixed B, C, one more)
        self.env['hr.employee'].create({'name': 'DEMO NH One More', 'company_id': self.company.id,
                                        'department_id': self.finance.id, 'payroll_country': 'SG'})
        self.assertEqual(s._default_country(), ('SG', 'most'))
        load = s.load(False)
        self.assertEqual(load['draft']['payroll_country'], 'SG')
        self.assertEqual(load['default_country'], {'code': 'SG', 'why': 'most'})
        self.assertEqual(load['places']['country'], 'SG')
        known = {c['code'] for c in load['countries'] if c['known']}
        self.assertTrue({'SG', 'IN', 'VN'} <= known, 'people, schemes')
        self.assertFalse(next(c for c in load['countries'] if c['code'] == 'MY')['known'])
        # a company that works in its own country only: that country
        self.env['hr.employee'].sudo().search([('company_id', '=', self.company.id)]).write(
            {'payroll_country': 'VN'})
        self.assertEqual(s._default_country(), ('VN', 'company'))

    # ================================================================ C4
    def test_c4_prefilled_team_brings_its_country(self):
        s = self.studio()
        self.assertEqual(s.load({'department_id': self.farm.id})['draft']['payroll_country'], 'IN',
                         'where most of the team works')
        self.assertEqual(s.load({'department_id': self.finance.id})['draft']['payroll_country'], 'SG',
                         'the scheme that pays the team')
        self.assertEqual(s.load({'department_id': self.ops.id})['draft']['payroll_country'], 'VN')
        self.assertEqual(s.team_defaults(self.farm.id)['country_code'], 'IN')
        self.assertFalse(s.team_defaults(self.lonely.id)['country_code'])

    # ================================================================ C5
    def test_c5_any_pair_is_still_accepted(self):
        """Filtering is guidance: a Vietnam-paid team with India as the
        country is still sent and applied; an old payload (no bank country)
        keeps the old bank check."""
        self.fast_lane()
        out = self.studio().send(self.draft(department_id=self.ops.id, job_id=self.agronomist.id,
                                            payroll_country='IN', wage=50000))
        self.assertTrue(out.get('applied'), out)
        emp = self.hires()
        self.assertEqual((emp.department_id, emp.payroll_country), (self.ops, 'IN'))
        Wizard = self.env['pb.people.onboard.wizard']
        old = Wizard._pb_bank_entered({'bank_name': 'BIDV', 'account_number': '12345'})
        self.assertNotIn('bank_format', old)
        self.assertIn('6 to 19 digits', Wizard._pb_bank_problem(old))
        new = Wizard._pb_bank_entered({'bank_name': 'HDFC', 'account_number': '123456789012',
                                       'bank_format': 'IN'})
        self.assertIn('IFSC', Wizard._pb_bank_problem(new))

    # ================================================================ C6
    def test_c6_places_is_quick_on_a_rize_sized_company(self):
        env = self.env
        Dept = env['hr.department'].with_company(self.company)
        teams = Dept.create([{'name': 'DEMO NH Perf %02d' % i, 'company_id': self.company.id}
                             for i in range(32)])
        codes = ('VN', 'ID', 'IN', 'SG')
        env['hr.employee'].create([{'name': 'DEMO NH Perf person %03d' % i, 'company_id': self.company.id,
                                    'department_id': teams[i % 32].id, 'payroll_country': codes[i % 4]}
                                   for i in range(320)])
        env.flush_all()
        s = self.studio()
        s.places('IN')                                  # warm
        times = []
        for code in ('IN', 'SG', 'VN', 'ID', 'MY'):
            env.invalidate_all()
            t0 = time.perf_counter()
            out = s.places(code, self.finance.id, False, '2026-12-07')
            times.append(time.perf_counter() - t0)
            self.assertTrue(out['teams'])
        self.assertLess(statistics.median(times), 0.3, times)


@tagged('post_install', '-at_install', 'newhire')
class TestP7Bank(DocsCommon):

    def bank_item(self, code):
        items, _o = self.items(code)
        return items['bank']

    # ================================================================ B3
    def test_b3_one_definition_everywhere(self):
        Format = self.env['pb.bank.format']
        bank = self.bank_item('IN')
        self.assertEqual(bank['bank']['default'], 'IN')
        boxes = bank['bank']['fields']['IN']
        spec = Format.spec('IN')
        self.assertEqual([b['label'] for b in boxes if b['kind'] == 'code'], [c['label'] for c in spec['codes']])
        account = next(b for b in boxes if b['name'] == 'account_number')
        self.assertEqual(account['hint'], spec['account']['hint'])
        self.assertEqual(bank['fields'], boxes, 'the row starts in the country of work')
        self.assertEqual(sorted(bank['bank']['fields']),
                         sorted(c['code'] for c in Format.choices()), 'every country can be picked')
        au = bank['bank']['fields']['AU']
        self.assertIn('BSB', [b['label'] for b in au])
        self.assertTrue(json.dumps(bank), 'JSON-plain')
        # My Payobook and the Bank Verification screen read the same table
        emp = self.env['hr.employee'].create({'name': 'DEMO NH India', 'company_id': self.company.id,
                                              'payroll_country': 'IN'})
        att = self.env['ir.attachment'].create({'name': 'l.pdf', 'datas': 'JVBERi0=',
                                                'mimetype': 'application/pdf'})
        req = self.env['pb.bank.change.request'].sudo().create(
            {'employee_id': emp.id, 'attachment_id': att.id, 'company_id': self.company.id})
        self.assertEqual(req.pb_portal_view()['format'], spec)
        defs = self.env['pb.bank.ocr']._pb_field_defs(req)
        self.assertIn(spec['codes'][0]['label'], [d['label'] for d in defs])

    def test_b3b_studio_checks_and_carries_the_codes(self):
        if 'pb.records.apply' not in self.env:
            self.skipTest('the bank second-person path is not installed')
        from odoo.addons.pb_records.tests.bank_second import ensure_second_person
        ensure_second_person(self.env, self.company)
        bank = {'bank_format': 'IN', 'bank_name': 'HDFC', 'account_number': '1234 5678 9012'}
        bad = self.studio().send(self.docs_draft(items={'bank': 'have'}, have=bank))
        self.assertEqual((bad['step'], bad['field']), ('docs', 'have-branch_code'))
        self.assertIn('IFSC', bad['message'])
        bad = self.studio().send(self.docs_draft(items={'bank': 'have'},
                                                 have=dict(bank, branch_code='HDFC1001234')))
        self.assertIn('11 characters', bad['message'])
        out = self.studio().send(self.docs_draft(items={'bank': 'have'},
                                                 have=dict(bank, branch_code='hdfc0001234')))
        self.assertTrue(out['pending'], out)
        prop = self.proposal(out)
        values = prop._pb_nh_values()
        self.assertEqual((values['bank_format'], values['branch_code']), ('IN', 'HDFC0001234'))
        rows = {str(r[0]): str(r[2]) for r in prop._proposal_rows()}
        self.assertEqual(rows.get('IFSC code'), 'HDFC0001234', 'the approver sees the code')
        self.assertEqual(rows.get('Bank account in'), 'India')
        self.approve(out)
        emp = self.hires()
        req = self.env['pb.bank.change.request'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(req), 1)
        self.assertEqual((req.pb_bank_format, req.x_branch_code, req.x_account_number),
                         ('IN', 'HDFC0001234', '123456789012'))
        self.assertIn(req.state, ('hr_review', 'finance_review'), 'sent for the second person')

    def test_b3c_singapore_bank_code_from_the_bank(self):
        values = self.studio()._bank_values('SG', {'bank_name': 'DBS', 'account_number': '0123456789'},
                                            'DEMO NH Sari')
        self.assertEqual(values['bank_code'], '7171')
        self.assertEqual(values['bank_format'], 'SG')
        self.assertEqual(values['account_holder'], 'DEMO NH Sari')
