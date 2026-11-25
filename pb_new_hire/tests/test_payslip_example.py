# -*- coding: utf-8 -*-
"""NEWHIRE P4 Part B — "A month's payslip · example". Test numbers match the
handover (B.4: P1 no trace, P2 equals a real payslip, P3 a usual answer
flipped, P4 errors, P5 two at once, P6 time and the cache)."""
from datetime import date
from unittest.mock import patch

import odoo
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.pb_hr_payroll_formula.models.scheme_proposal import (
    SCHEME_APPLY_KEY, SCHEME_APPLY_TOKEN,
)

from .test_new_hire import NewHireCommon

TABLES = ('hr_employee', 'hr_contract', 'hr_payslip', 'hr_payslip_line', 'hr_payslip_worked_days',
          'hr_contract_advantage', 'mail_message', 'mail_followers', 'mail_mail', 'ir_attachment',
          'resource_calendar', 'resource_resource', 'res_partner', 'res_users', 'bus_bus',
          'pb_shift_pattern_member', 'pb_new_hire_ask', 'pb_journey_case', 'pb_newhire_proposal',
          'biz_approval_request', 'mail_activity')


@tagged('post_install', '-at_install', 'newhire')
class TestPayslipExample(NewHireCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env(context=dict(cls.env.context, **{SCHEME_APPLY_KEY: SCHEME_APPLY_TOKEN}))
        Cat = env['hr.salary.rule.category']
        for code in ('BASIC', 'ALW', 'GROSS', 'DED', 'NET', 'COMP', 'OTH'):
            if not Cat.search([('code', '=', code)], limit=1):
                Cat.create({'name': code.title(), 'code': code})
        other = Cat.search([('code', '=', 'OTH')], limit=1)
        scheme = cls.sg_scheme.with_env(env)
        Rule = env['hr.formula.rule']
        scheme.rule_ids.write({'category_id': other.id})
        # the usual answers of NewHireCommon: CPF yes/no (a flag, not a line),
        # meal 150 (an earning), levy and zero (no pay role: never a line)
        cls.r_cpf.with_env(env).write({'appears_on_payslip': False})
        cls.r_meal.with_env(env).write({'net_role': 'earning'})

        def rule(code, name, ctype, role, seq, formula=False):
            made = Rule.create({'config_id': scheme.id, 'code': code, 'name': name,
                                'column_type': ctype, 'sequence': seq, 'category_id': other.id,
                                'appears_on_payslip': True, 'excel_formula': formula or False})
            made.write({'net_role': role})
            return made
        basic = rule('BASIC', 'DEMO NH Basic wage', 'input', 'earning', 10)
        b, c, m = basic.column_letter, cls.r_cpf.column_letter, cls.r_meal.column_letter
        rule('DEMONHCPFE', 'DEMO NH CPF employee', 'formula', 'deduction', 11,
             '=IF(%s5=1,ROUND((%s5+%s5)*0.2,2),0)' % (c, b, m))
        cpfe = Rule.search([('config_id', '=', scheme.id), ('code', '=', 'DEMONHCPFE')]).column_letter
        rule('DEMONHNET', 'DEMO NH Take-home', 'formula', 'net', 12,
             '=%s5+%s5-%s5' % (b, m, cpfe))
        rule('DEMONHCPFR', 'DEMO NH CPF employer', 'formula', 'employer_cost', 13,
             '=IF(%s5=1,ROUND((%s5+%s5)*0.17,2),0)' % (c, b, m))
        cls.env['pb.new.hire']._cache().clear()

    def setUp(self):
        super().setUp()
        self.env['pb.new.hire']._cache().clear()

    def example(self, user=None, **kw):
        return self.studio(user).payslip_example(self.draft(**kw))

    def counts(self):
        out = {}
        for table in TABLES:
            self.env.cr.execute("SELECT to_regclass(%s)", (table,))
            if not self.env.cr.fetchone()[0]:
                continue
            self.env.cr.execute('SELECT count(*) FROM %s' % table)     # noqa: S608 — fixed names
            out[table] = self.env.cr.fetchone()[0]
        self.env.cr.execute("SELECT count(*) FROM hr_employee WHERE pb_paid_by_stale")
        out['stale'] = self.env.cr.fetchone()[0]
        self.env.cr.execute("SELECT count(*), max(write_date) FROM hr_formula_rule WHERE config_id = %s",
                            (self.sg_scheme.id,))
        out['rules'] = tuple(self.env.cr.fetchone())
        self.env.cr.execute("SELECT write_date FROM hr_formula_config WHERE id = %s", (self.sg_scheme.id,))
        out['config'] = self.env.cr.fetchone()[0]
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'salary.slip')], limit=1)
        out['slip_number'] = seq.number_next_actual if seq else None
        return out

    # ------------------------------------------------------------------ P1
    def test_p1_no_trace(self):
        # the fixtures' own tracking waits in the precommit hooks: run it now
        # (a savepoint runs them on entry — NH50), so only the example counts
        # a manager who signs in: the stock time-off create would add them to
        # the approvers group and clear every worker's caches (NH51)
        self.boss.user_id = self.approver
        self.env.cr.flush()
        before = self.counts()
        self.env.registry.cache_invalidated.clear()
        hooks = (len(self.env.cr.precommit._funcs), len(self.env.cr.postcommit._funcs))
        answers = [self.example(wage=5000 + i, usual=[{'code': 'DEMONHCPF', 'amount': i % 2}])
                   for i in range(20)]
        self.assertTrue(all(a['ok'] for a in answers), answers[0])
        self.assertFalse(any(a['cached'] for a in answers), 'twenty different drafts, twenty real runs')
        self.env.cr.flush()
        self.env.invalidate_all()
        after = self.counts()
        self.assertEqual(before, after, 'the example left a trace')
        self.assertEqual(hooks, (len(self.env.cr.precommit._funcs), len(self.env.cr.postcommit._funcs)),
                         'no commit-time work is left behind')
        self.assertFalse(self.hires(), 'no employee of that name exists')
        self.assertFalse(self.env.registry.cache_invalidated, 'no worker is told to drop its caches')
        # the real payslip number is still the next one
        seq = self.env['ir.sequence'].sudo().search([('code', '=', 'salary.slip')], limit=1)
        if seq:
            self.assertEqual(seq.number_next_actual, before['slip_number'])

    # ------------------------------------------------------------------ P2
    def test_p2_equals_a_real_payslip(self):
        example = self.example(date_start='2026-12-07')
        self.assertTrue(example['ok'], example)
        self.assertEqual(example['month_label'], 'December 2026')
        self.assertEqual(example['currency']['symbol'], self.env.ref('base.SGD').symbol)
        self.assertEqual(sorted(l['name'] for l in example['lines']),
                         ['DEMO NH Basic wage', 'DEMO NH CPF employee', 'DEMO NH Meal'],
                         'zero lines and lines with no pay role hidden')
        self.assertEqual({l['band'] for l in example['lines']}, {'earning', 'deduction'})
        # the same person, made for real through the studio, paid the normal way
        self.fast_lane()
        sent = self.studio().send(self.draft(date_start='2026-12-07'))
        self.assertTrue(sent.get('applied'), sent)
        emp = self.hires()
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        Slip = self.env['hr.payslip'].sudo()
        change = Slip.onchange_employee_id('2026-12-01', '2026-12-31', emp.id, contract.id)['value']
        slip = Slip.create({'employee_id': emp.id, 'contract_id': contract.id,
                            'date_from': '2026-12-01', 'date_to': '2026-12-31',
                            'company_id': self.company.id, 'name': change.get('name') or 'DEMO NH slip',
                            'formula_config_id': self.sg_scheme.id, 'calculation_method': 'formula'})
        slip.compute_sheet()
        real = slip.pb_pay_totals()
        printed = [l.name for l in slip.line_ids.sorted(lambda l: (l.sequence, l.code or ''))
                   if l.name in {x['name'] for x in example['lines']}]
        self.assertEqual([l['name'] for l in example['lines']], printed, 'the payslip order')
        self.assertAlmostEqual(example['gross'], real['gross'], places=2)
        self.assertAlmostEqual(example['deductions'], real['deductions'], places=2)
        self.assertAlmostEqual(example['net'], real['net'], places=2)
        self.assertAlmostEqual(example['employer_cost'], real['employer_cost'], places=2)
        self.assertAlmostEqual(example['gross'], 5200.50 + 150.0, places=2)
        self.assertAlmostEqual(example['deductions'], round(5350.50 * 0.2, 2), places=2)

    # ------------------------------------------------------------------ P3
    def test_p3_a_usual_answer_flipped(self):
        on = self.example()
        off = self.example(usual=[{'code': 'DEMONHCPF', 'amount': 0}])
        self.assertTrue(on['ok'] and off['ok'], (on, off))
        self.assertGreater(on['deductions'], 0)
        self.assertEqual(off['deductions'], 0.0, 'CPF off: nothing taken off')
        self.assertAlmostEqual(off['net'], off['gross'], places=2)
        self.assertEqual(off['employer_cost'], 0.0)
        self.assertNotIn('DEMO NH CPF employee', [l['name'] for l in off['lines']], 'zero line hidden')
        meal = self.example(usual=[{'code': 'DEMONHMEAL', 'amount': 300}])
        self.assertAlmostEqual(meal['gross'], on['gross'] + 150, places=2)

    # ------------------------------------------------------------------ notes
    def test_p3b_words(self):
        mid = self.example(date_start='2026-12-07')
        self.assertEqual(mid['notes'][0], "Worked out by DEMO NH Singapore monthly for a full December, "
                                          "from the scheme's usual values.")
        self.assertIn('DEMO starts on 7 December. Whether the first pay is reduced', mid['notes'][1])
        whole = self.example(date_start='2027-01-01')
        self.assertEqual(whole['month_label'], 'January 2027')
        self.assertFalse(any('starts on' in n for n in whole['notes']), 'a first of the month: no part-month note')
        mismatch = self.example(payroll_country='VN')
        self.assertTrue(mismatch['ok'], mismatch)
        self.assertTrue(any('a Singapore scheme, but you chose Vietnam' in n for n in mismatch['notes']))
        self.assertEqual(mismatch['currency']['symbol'], self.env.ref('base.VND').symbol,
                         'the money is the country of work, as the contract')
        # an input the scheme reads from the pay data file falls to its usual value
        self.env['hr.formula.rule.source'].sudo().create({
            'rule_id': self.r_levy.id, 'kind': 'excel', 'key': 'DEMO LEVY'}) \
            if 'hr.formula.rule.source' in self.env else None
        if 'hr.formula.rule.source' in self.env:
            filed = self.example(wage=5300)
            self.assertIn("Some values on this scheme come from the monthly pay data file; the example "
                          "uses the usual ones.", filed['notes'])
        for word in ('odoo', 'Odoo'):
            self.assertNotIn(word, repr(mid))

    # ------------------------------------------------------------------ P4
    def test_p4_errors(self):
        none = self.example(department_id=self.lonely.id)
        self.assertEqual((none['ok'], none['reason'], none['step']),
                         (False, 'No pay scheme pays this team yet.', 'role'))
        missing = self.studio().payslip_example(self.draft(wage=''))
        self.assertEqual((missing['ok'], missing['step']), (False, 'pay'))
        nameless = self.studio().payslip_example(self.draft(name='  '))
        self.assertEqual(nameless['step'], 'who')
        Sample = type(self.env['hr.formula.sample.data'])
        real = Sample._evaluate_rules_with_dependencies

        def broken(this, inputs, readonly=False, errors=None):
            out = real(this, inputs, readonly=readonly, errors=errors)
            if errors is not None:
                errors['DEMONHCPFE'] = 'float division by zero'
            return out
        with patch.object(Sample, '_evaluate_rules_with_dependencies', broken):
            bad = self.example(wage=5111)
        self.assertFalse(bad['ok'])
        self.assertEqual(bad['reason'], 'DEMO NH Singapore monthly could not work out an example: '
                                        'the formula for DEMO NH CPF employee divides by zero.')
        self.assertEqual(bad['fix'], 'The hire is not affected. Check the scheme in Mapping.')
        with self.assertRaises(AccessError):
            self.example(user=self.outsider)

    def test_p4b_seat_limit_and_what_a_send_does(self):
        Emp = type(self.env['hr.employee'])
        if not hasattr(Emp, '_pb_check_seats'):
            self.skipTest('no employee limit on this build')

        def full(this, adding=1):
            raise UserError('DEMO limit reached.')
        before = self.counts()
        with patch.object(Emp, '_pb_check_seats', full):
            seat = self.example(wage=5222)
            self.assertFalse(seat['ok'])
            self.assertEqual(seat['reason'], 'An example cannot be shown because your plan has no '
                                             'free employee place.')
            self.assertEqual(seat['fix'], 'You can still send the hire: once it is approved, it '
                                          'waits in Approvals until a place is free.')
            # …and that is true: the send goes, the approved hire is held with the reason
            sent = self.studio().send(self.draft())
            self.assertTrue(sent.get('pending'), sent)
            self.approve(sent)
            request = self.env['biz.approval.request'].sudo().browse(sent['request_id'])
            self.assertEqual(request.state, 'approved')
            self.assertIn('DEMO limit reached', request.block_reason or '')
            self.assertFalse(self.hires())
        self.Engine.with_user(self.maker).with_context(
            allowed_company_ids=[self.company.id]).retry_apply(request.id)
        self.env.invalidate_all()
        self.assertEqual(len(self.hires()), 1, 'once a place is free it can be added from Approvals')
        self.assertEqual(before['hr_employee'] + 1, self.counts()['hr_employee'])

    # ------------------------------------------------------------------ P5
    def test_p5_two_at_once(self):
        company = self.company
        calendar = company.resource_calendar_id
        self.assertTrue(calendar)
        other = odoo.sql_db.db_connect(self.env.cr.dbname).cursor()
        try:
            other.execute('SET lock_timeout = 2000')
            other.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', (company.id, calendar.id))
            self.assertTrue(other.fetchone()[0])
            busy = self.example(wage=5333)
            self.assertEqual((busy['ok'], busy.get('busy')), (False, True),
                             'a second example answers busy at once instead of waiting')
        finally:
            other.rollback()
            other.close()
        fine = self.example(wage=5333)
        self.assertTrue(fine['ok'], fine)

    # ------------------------------------------------------------------ P6
    def test_p6_time_and_cache(self):
        first = self.example(wage=5444)
        again = self.example(wage=5444)
        renamed = self.example(wage=5444, name='DEMO NH Other Name')
        self.assertTrue(first['ok'] and again['ok'])
        self.assertIsInstance(first['took_ms'], int)
        self.assertFalse(first['cached'])
        self.assertTrue(again['cached'], 'the same draft within 5 minutes is not worked out again')
        self.assertTrue(renamed['cached'], 'the name changes only the words')
        self.assertIn('DEMO starts on', ' '.join(renamed['notes']).replace('DEMO NH Other', 'DEMO'))
        self.assertEqual(again['net'], first['net'])
        # a change to the scheme makes the cached numbers stale
        self.r_meal.with_context(**{SCHEME_APPLY_KEY: SCHEME_APPLY_TOKEN}).write({'default_value': 200.0})
        self.env.flush_all()
        changed = self.example(wage=5444)
        self.assertFalse(changed['cached'])
        self.assertAlmostEqual(changed['gross'], first['gross'] + 50, places=2)
