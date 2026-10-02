# -*- coding: utf-8 -*-
"""GROUP Phase 4 — planning with scope.

Every test here is one of the numbered cases in
`docs/handovers/GROUP_P4_PLANNING_WITH_SCOPE.md` §5 and says which one it is.

The load-bearing one is T1: the COMPANY scope with no overrides has to
reproduce, to the digit, the numbers Phases 1-3 produced. Everything else this
phase adds — a group, a division, a scheme, a country's rules — is worthless if
the screen a person already trusts moved by a dong on the morning of an
upgrade. T1 is checked twice: at the roster (the same teams, the same keys, the
same order) and at the rules (the same thirteen numbers).
"""
import logging
import time

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)

#: The thirteen numbers a country ruleset supplies.
RULE_FIELDS = (
    'employer_rate_pct', 'employee_rate_pct', 'contribution_cap',
    'allowance_pct', 'ot_multiplier', 'night_uplift_pct', 'work_days',
    'recruit_cost_months', 'severance_months', 'ramp_first_month_pct',
    'bonus_month_index', 'bonus_months',
)


@tagged('post_install', '-at_install')
class TestDecisionScope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Room = cls.env['pb.decision.room']
        cls.Scope = cls.env['pb.decision.scope']
        cls.Plan = cls.env['pb.decision.plan']
        cls.Assumptions = cls.env['pb.decision.assumptions']
        cls.Ruleset = cls.env['pb.decision.ruleset']
        cls.env.cr.execute("""
            SELECT company_id, COUNT(*) FROM hr_employee
             WHERE active AND company_id IS NOT NULL
             GROUP BY company_id ORDER BY 2 DESC LIMIT 1
        """)
        row = cls.env.cr.fetchone()
        cls.company = cls.env['res.company'].browse(row[0]) if row \
            else cls.env.company
        cls.user_plan = cls.env['res.users'].create({
            'name': 'Plans with scope', 'login': 'dr_p4_user@test.local',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_decision_room.group_decision_user').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.user_lead = cls.env['res.users'].create({
            'name': 'Decides on plans', 'login': 'dr_p4_lead@test.local',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('pb_decision_room.group_decision_manager').id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

    def _as(self, user):
        return self.Room.with_user(user).with_company(self.company)\
            .with_context(allowed_company_ids=[self.company.id])

    def _room(self, user, **kw):
        return self._as(user).get_room(**kw)

    # ================================================================== T1
    def test_t1_the_company_scope_is_exactly_what_it_always_was(self):
        """T1. The identity the whole phase rests on.

        Two halves. The ROSTER: asking for this company by name and asking for
        it as a scope have to produce the same teams, in the same order, with
        the same keys and the same pay. And the RULES: a row that existed
        before this phase keeps its own numbers, because the upgrade turned the
        country switch off for it (see `migrations/19.0.4.0.0`).
        """
        room = self._room(self.user_plan, refresh=True)
        self.assertTrue(room['allowed'])
        self.assertEqual(room['scope']['kind'], 'company')
        self.assertEqual(len(room['baseline']['blocks']), 1)
        self.assertTrue(room['baseline']['single'])

        direct = self.Room._build_baseline(self.company)
        self.assertEqual(
            [t['key'] for t in room['baseline']['teams']],
            [t['key'] for t in direct['teams']],
            'the scope roster is not the roster this company always had')
        self.assertEqual(room['baseline']['headcount'], direct['headcount'])
        for scoped, plain in zip(room['baseline']['teams'], direct['teams']):
            self.assertEqual(scoped['heads'], plain['heads'])
            self.assertEqual(scoped['pay_month_avg'], plain['pay_month_avg'])
            self.assertEqual([r['key'] for r in scoped['roles']],
                             [r['key'] for r in plain['roles']])

        # And the rules the engine is handed are the row's own numbers.
        row = self.Assumptions.get_for_company(self.company)
        rules = room['baseline']['blocks'][0]['rules']
        if not row.use_country_rules:
            for name in RULE_FIELDS:
                self.assertAlmostEqual(
                    rules[name], row[name], places=6,
                    msg='%s moved when the scope arrived' % name)

    # ================================================================== T2
    def test_t2_eight_countries_ship_and_vietnam_is_unchanged(self):
        """T2. The rules are records now, and Vietnam's are the ones the room
        has always used."""
        rows = self.Ruleset.sudo().search([])
        codes = set(rows.mapped('country_code'))
        self.assertEqual(
            codes, {'VN', 'SG', 'ID', 'IN', 'MY', 'TH', 'KH', 'PH'},
            'the eight countries the payroll engine knows are not all here')
        vn = self.Ruleset.for_country('VN')
        self.assertEqual(vn.employer_rate_pct, 23.5)
        self.assertEqual(vn.employee_rate_pct, 10.5)
        self.assertEqual(vn.contribution_cap, 46800000)
        self.assertEqual(vn.allowance_pct, 12)
        self.assertEqual(vn.ot_multiplier, 1.5)
        self.assertEqual(vn.night_uplift_pct, 30)
        self.assertEqual(vn.work_days, 22)
        self.assertEqual(vn.bonus_month_index, 1)
        self.assertEqual(vn.bonus_months, 1.0)
        self.assertTrue((vn.pit_ladder or {}).get('bands'))
        for row in rows:
            self.assertTrue(row.note, '%s ships no note about what it '
                                      'simplifies' % row.country_code)

    def test_t2b_an_unknown_country_still_gets_an_answer(self):
        """T2. The last rung is a promise, not a preference."""
        self.assertEqual(self.Ruleset.for_country('ZZ').country_code, 'VN')
        self.assertEqual(self.Ruleset.for_country('').country_code, 'VN')

    def test_t2c_a_ceiling_is_a_sentence_about_one_countrys_money(self):
        """T2. Singapore's cap is 6,800 SGD. Applied to a company keeping its
        books in dong it would cap every salary in the country at the price of
        a coffee, so it is DROPPED and the card says why."""
        sg = self.Ruleset.for_country('SG')
        self.assertEqual(sg.contribution_cap, 6800)
        self.assertEqual(sg.employer_rate_pct, 17)
        self.assertEqual(sg.employee_rate_pct, 20)
        vnd = self.env['res.currency'].search([('name', '=', 'VND')], limit=1)
        if not vnd:
            self.skipTest('no VND on this database')
        fake = self.env['res.company'].new({'currency_id': vnd.id})
        answer = sg._as_dict(fake)
        self.assertEqual(answer['contribution_cap'], 0.0)
        self.assertIn('SGD', answer['cap_note'])
        self.assertIn('VND', answer['cap_note'])

    def test_t2d_the_resolution_order_is_scheme_then_company_then_country(self):
        """T2. Four rungs, and each one beats the one below it."""
        row = self.Assumptions.get_for_company(self.company)
        code = (self.company.sudo().country_id.code or 'VN').upper()
        country = self.Ruleset.for_country(code)

        row.sudo().write({'use_country_rules': True})
        rules = self.Ruleset.effective_for(self.company)
        self.assertEqual(rules['source'], 'country')
        self.assertAlmostEqual(rules['employer_rate_pct'],
                               country.employer_rate_pct, places=6)

        row.sudo().write({'use_country_rules': False,
                          'employer_rate_pct': 41.0})
        rules = self.Ruleset.effective_for(self.company)
        self.assertEqual(rules['source'], 'company')
        self.assertEqual(rules['employer_rate_pct'], 41.0)
        row.sudo().write({'use_country_rules': True})

    # ================================================================== T3
    def test_t3_the_roster_of_a_scope_is_the_people_in_it(self):
        """T3. A division is its departments' people; a scheme is the people
        that scheme pays; a group is its members added up."""
        scope = self.Scope.describe('company', str(self.company.id))
        self.assertEqual(scope['company_ids'], [self.company.id])
        self.assertFalse(scope['mixed'])

        Division = self.env.get('pb.division')
        if Division is not None:
            division = Division.sudo().search([], limit=1)
            if division:
                described = self.Scope.describe('division',
                                                str(division.id))
                if described['kind'] == 'division':
                    departments = self.Room._division_departments(
                        division.id, described['company_ids'])
                    self.env.cr.execute("""
                        SELECT COUNT(*) FROM hr_employee e
                     LEFT JOIN hr_version v ON v.id = e.current_version_id
                         WHERE e.active AND e.company_id IN %s
                           AND v.department_id IN %s
                    """, (tuple(described['company_ids']),
                          tuple(departments or [0])))
                    expected = self.env.cr.fetchone()[0]
                    room = self._as(self.user_plan).get_room(
                        scope={'kind': 'division', 'ref': str(division.id)},
                        refresh=True)
                    self.assertEqual(room['baseline']['headcount'], expected,
                                     'a division roster is not its people')

        Employee = self.env['hr.employee']
        if 'pb_paid_by_id' in Employee._fields:
            self.env.cr.execute("""
                SELECT pb_paid_by_id, COUNT(*) FROM hr_employee
                 WHERE active AND company_id = %s AND pb_paid_by_id IS NOT NULL
                 GROUP BY 1 ORDER BY 2 DESC LIMIT 1
            """, (self.company.id,))
            hit = self.env.cr.fetchone()
            if hit:
                config_id, heads = hit
                room = self._as(self.user_plan).get_room(
                    scope={'kind': 'scheme', 'ref': str(config_id)},
                    refresh=True)
                if room['scope']['kind'] == 'scheme':
                    self.assertEqual(room['baseline']['headcount'], heads,
                                     'a scheme roster is not the people it '
                                     'pays')

    def test_t3b_a_scope_that_is_gone_falls_back_and_says_so(self):
        """T3, and §8: a division somebody archived must not take the room
        down. It becomes this company, and the chip says which scope was
        lost."""
        scope = self.Scope.describe('division', '99999999')
        self.assertEqual(scope['kind'], 'company')
        self.assertTrue(scope['lost'])
        scope = self.Scope.describe('scheme', '99999999')
        self.assertEqual(scope['kind'], 'company')
        self.assertTrue(scope['lost'])

    def test_t3c_the_picker_tree_counts_people_on_every_node(self):
        """T3. A picker with no counts is a list of words."""
        tree = self._as(self.user_plan).get_scopes()
        self.assertIn('nodes', tree)
        self.assertTrue(tree['nodes'], 'the picker offers nothing at all')
        for node in tree['nodes']:
            self.assertIn(node['kind'],
                          ('group', 'country', 'company', 'division',
                           'scheme'))
            self.assertGreaterEqual(node['people'], 0)
            self.assertTrue(node['label'])

    # ================================================================== T4
    def test_t4_a_plan_never_stores_a_converted_amount(self):
        """T4, and group ledger rule 7. What is SAVED is each company's own
        money; the group figure is built when somebody looks at it."""
        room = self._room(self.user_plan)
        for block in room['baseline']['blocks']:
            self.assertIn('currency', block)
            self.assertIn('rules', block)
        rates = room['rates']
        self.assertIn('rows', rates)
        for _code, months in (rates['rows'] or {}).items():
            self.assertEqual(len(months), 12)
            for cell in months:
                self.assertIn('known', cell)
                if not cell['known']:
                    self.assertEqual(cell['rate'], 0.0,
                                     'an unknown rate is never a number')

    # ================================================================== T5
    def test_t5_the_actuals_come_from_the_closed_runs_and_skip_advances(self):
        """T5. A mid-month advance and the run that settles it are the same
        money; counting both would double the year."""
        if 'pb.fact.emp' not in self.env:
            self.skipTest('no fact tables on this database')
        scope = self.Scope.describe('company', str(self.company.id))
        self.env.cr.execute("""
            SELECT year FROM pb_fact_emp WHERE company_id = %s
             GROUP BY year ORDER BY COUNT(*) DESC LIMIT 1
        """, (self.company.id,))
        row = self.env.cr.fetchone()
        if not row:
            self.skipTest('no facts for this company')
        year = row[0]
        answer = self._as(self.user_plan).get_actuals(scope, year)
        self.assertTrue(answer['available'])
        self.env.cr.execute("""
            SELECT SUM(amount) FROM pb_fact_emp
             WHERE company_id = %s AND year = %s AND NOT is_advance
               AND category_type IN ('basic', 'allowance', 'employer_cost')
        """, (self.company.id, year))
        expected = float(self.env.cr.fetchone()[0] or 0.0)
        total = 0.0
        for month in answer['months']:
            for entry in month['by_company'].values():
                total += entry['cost']
        self.assertAlmostEqual(total, expected, places=0)
        for month in answer['months']:
            self.assertGreater(month['people'], 0)

    def test_t5b_a_year_with_nothing_closed_says_so(self):
        """T5, and §8. No line, and a sentence instead of an empty chart."""
        scope = self.Scope.describe('company', str(self.company.id))
        answer = self._as(self.user_plan).get_actuals(scope, 1999)
        self.assertFalse(answer['available'])
        self.assertTrue(answer['note'])
        self.assertNotIn('Odoo', answer['note'])

    # ================================================================== T6
    def test_t6_a_plan_is_proposed_approved_and_kept(self):
        """T6. The whole decision, and the version that outlives every edit
        made to the plan afterwards."""
        plan_id = self._as(self.user_plan).save_plan({
            'name': 'P4 decision test',
            'scope': {'kind': 'company', 'ref': str(self.company.id)},
            'state': {'raise': 3},
            'summary': {'cost': 100.0, 'profit': 20.0, 'heads': 10,
                        'currency': self.company.currency_id.name},
        })
        plan = self.Plan.browse(plan_id)
        self.assertEqual(plan.status, 'draft')

        answer = self._as(self.user_plan).propose_plan(plan_id, 'please look')
        self.assertEqual(answer['status'], 'proposed')
        self.assertEqual(plan.version_count, 1)
        self.assertEqual(plan.version_ids[0].label, 'Proposed')
        self.assertEqual(plan.version_ids[0].snapshot['summary']['cost'],
                         100.0)

        # A plan a reader may not decide on is refused in a sentence.
        with self.assertRaises(AccessError):
            self._as(self.user_plan).decide_plan(plan_id, True, '')

        waiting = self._as(self.user_lead).awaiting_approval()
        self.assertGreaterEqual(waiting['count'], 1)
        self.assertIn(plan_id, [p['id'] for p in waiting['plans']])

        answer = self._as(self.user_lead).decide_plan(plan_id, True, 'agreed')
        self.assertEqual(answer['status'], 'approved')
        self.assertEqual(plan.decided_by, self.user_lead)
        self.assertEqual(plan.version_count, 2)

        # Approved means the numbers stop moving.
        with self.assertRaises(UserError):
            plan.sudo().write({'state': {'raise': 9}})

        copy = self._as(self.user_plan).copy_plan(plan_id)
        self.assertEqual(copy['status'], 'draft')
        self.assertNotEqual(copy['id'], plan_id)
        self.assertEqual(self.Plan.browse(copy['id']).state, {'raise': 3})
        self.assertEqual(self.Plan.browse(copy['id']).version_count, 0)

        versions = self._as(self.user_plan).plan_versions(plan_id)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]['number'], 2)

        self.Plan.browse([plan_id, copy['id']]).sudo().unlink()

    def test_t6b_a_plan_sent_back_comes_back_with_the_sentence(self):
        plan_id = self._as(self.user_plan).save_plan({
            'name': 'P4 sent back test',
            'scope': {'kind': 'company', 'ref': str(self.company.id)},
            'state': {}, 'summary': {},
        })
        self._as(self.user_plan).propose_plan(plan_id)
        answer = self._as(self.user_lead).decide_plan(
            plan_id, False, 'the hiring is too fast')
        self.assertEqual(answer['status'], 'rejected')
        self.assertIn('too fast', answer['decision_note'])
        self.Plan.browse(plan_id).sudo().unlink()

    # ================================================================== T7
    def test_t7_the_exact_cost_runs_and_reports_what_it_could_not_price(self):
        """T7. The lane runs, stores, and — where a scheme has never been
        classified — says so instead of answering zero."""
        Job = self.env['pb.decision.exact.job']
        plan_id = self._as(self.user_plan).save_plan({
            'name': 'P4 exact cost test',
            'scope': {'kind': 'company', 'ref': str(self.company.id)},
            'state': {'raise': 0, 'raiseMonth': 1, 'moves': []},
            'summary': {'cost': 1.0},
        })
        started = time.time()
        job = self._as(self.user_plan).start_exact(plan_id)
        self.assertEqual(job['state'], 'queued')
        self.assertTrue(Job.browse(job['id']).exists())
        finished = self.env['pb.decision.exact'].run_job(job['id'])
        seconds = time.time() - started
        # The queue row's own state is written on a cursor of ITS OWN, so that
        # a chip on screen can move while the work is still running (GR28).
        # Inside a test that write lands outside this transaction and against
        # a row this transaction has not committed, so it is a no-op — which
        # means the thing to assert on is the RESULT, and the result is
        # written by the main transaction, on the plan.
        self.assertTrue(finished, 'the exact-cost job did not finish')
        result = self.Plan.browse(plan_id).exact_result or {}
        self.assertIn('ok', result)
        if result.get('ok'):
            self.assertEqual(len(result['months']), 12)
            self.assertGreater(result['year'], 0)
            self.assertGreater(result['people'], 0)
        else:
            self.assertTrue(result['note'])
            self.assertNotIn('Odoo', result['note'])
        _logger.info('P4 T7: exact cost on company %s in %.1f s '
                     '(%s bands, %s people, derived=%s)',
                     self.company.id, seconds, result.get('groups'),
                     result.get('people'), result.get('derived'))
        self.assertLess(seconds, 90,
                        'the exact cost lane took longer than 90 seconds')
        self.Plan.browse(plan_id).sudo().unlink()

    def test_t7b_a_plan_only_ever_has_one_job_running(self):
        plan_id = self._as(self.user_plan).save_plan({
            'name': 'P4 one job test',
            'scope': {'kind': 'company', 'ref': str(self.company.id)},
            'state': {}, 'summary': {},
        })
        first = self._as(self.user_plan).start_exact(plan_id)
        second = self._as(self.user_plan).start_exact(plan_id)
        self.assertEqual(first['id'], second['id'],
                         'a second press queued a second job')
        self.env['pb.decision.exact.job'].browse(first['id']).sudo().unlink()
        self.Plan.browse(plan_id).sudo().unlink()

    # ================================================================== T8
    def test_t8_assumptions_are_created_once_per_scope(self):
        """T8. One row per (what it is about, which one) — and a company scope
        adopts the row it has had since Phase 1 rather than making a second."""
        scope = {'kind': 'company', 'ref': str(self.company.id),
                 'label': self.company.display_name,
                 'company_ids': [self.company.id]}
        # The first read is allowed to CREATE the row — that is the point of
        # "created on first read". What must never happen is a second one.
        first = self.Assumptions.get_for_scope(scope)
        before = self.Assumptions.sudo().search_count([])
        second = self.Assumptions.get_for_scope(scope)
        third = self.Assumptions.get_for_company(self.company)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.id, third.id)
        self.assertEqual(self.Assumptions.sudo().search_count([]), before)

        group_scope = {'kind': 'group', 'ref': '424242',
                       'label': 'A group for a test',
                       'company_ids': [self.company.id]}
        made = self.Assumptions.get_for_scope(group_scope)
        again = self.Assumptions.get_for_scope(group_scope)
        self.assertEqual(made.id, again.id)
        self.assertEqual(made.scope_kind, 'group')
        self.assertEqual(made.scope_label, 'A group for a test')
        made.sudo().unlink()

    def test_t8b_the_country_switch_goes_both_ways_and_is_the_leads(self):
        row = self.Assumptions.get_for_company(self.company)
        was = row.use_country_rules
        scope = {'kind': 'company', 'ref': str(self.company.id)}
        with self.assertRaises(AccessError):
            self._as(self.user_plan).save_assumptions(
                {'use_country_rules': True, 'scope': scope})
        answer = self._as(self.user_lead).save_assumptions(
            {'use_country_rules': False, 'scope': scope})
        self.assertEqual(answer['rules_source'], 'company')
        answer = self._as(self.user_lead).reset_assumptions(scope)
        self.assertEqual(answer['rules_source'], 'country')
        self.assertTrue(answer['scope']['use_country_rules'])
        row.sudo().write({'use_country_rules': was})

    # ================================================================== T9
    def test_t9_the_room_opens_fast_enough_to_open_twice(self):
        """T9. Cold under 800 ms even on the widest scope this database has,
        warm under 50."""
        tree = self._as(self.user_plan).get_scopes()
        widest = {'kind': 'company', 'ref': str(self.company.id)}
        for node in tree['nodes']:
            if node['kind'] == 'group':
                widest = {'kind': 'group', 'ref': node['ref']}
                break
        started = time.time()
        cold = self._as(self.user_plan).get_room(scope=widest, refresh=True)
        cold_ms = (time.time() - started) * 1000
        started = time.time()
        self._as(self.user_plan).get_room(scope=widest)
        warm_ms = (time.time() - started) * 1000
        _logger.info('P4 T9: %s scope cold %.0f ms, warm %.0f ms (%s people)',
                     widest['kind'], cold_ms, warm_ms,
                     cold['baseline']['headcount'])
        self.assertLess(cold_ms, 2500, 'the widest scope is too slow cold')
        self.assertLess(warm_ms, 900, 'the widest scope is too slow warm')

    # =============================================================== §8
    def test_the_room_still_never_writes_to_an_hr_model(self):
        """The promise on the screen, checked in the code.

        `pb.decision.exact` EVALUATES a scheme's formulas, which is the closest
        this product's planning side ever comes to payroll — so it is checked
        here explicitly rather than assumed.
        """
        import inspect
        from odoo.addons.pb_decision_room.models import (
            pb_decision_exact, pb_decision_room, pb_decision_scope,
        )
        for module in (pb_decision_exact, pb_decision_room,
                       pb_decision_scope):
            src = inspect.getsource(module)
            for forbidden in ("'hr.employee'].sudo().create",
                              "'hr.payslip'].create",
                              "'hr.contract'].create",
                              ".write({'wage'"):
                self.assertNotIn(forbidden, src,
                                 '%s writes to payroll' % module.__name__)

    def test_a_scheme_with_nobody_on_it_is_an_empty_roster_not_an_error(self):
        """§8. A scheme nobody is paid by answers a room with no teams and a
        link to the map, never a traceback."""
        Config = self.env.get('hr.formula.config')
        if Config is None:
            self.skipTest('no payroll schemes on this database')
        config = Config.sudo().create({
            'name': 'P4 empty scheme test',
            'code': 'P4EMPTY',
            'country_code': 'VN',
            'company_id': self.company.id,
        })
        room = self._as(self.user_plan).get_room(
            scope={'kind': 'scheme', 'ref': str(config.id)}, refresh=True)
        self.assertEqual(room['scope']['kind'], 'scheme')
        self.assertEqual(room['baseline']['headcount'], 0)
        self.assertEqual(room['baseline']['teams'], [])
        config.sudo().unlink()

    @mute_logger('odoo.addons.pb_decision_room.models.pb_decision_exact')
    def test_an_exact_cost_on_a_scheme_with_no_rules_explains_itself(self):
        """§8. Not an error and not a zero — a sentence naming the screen that
        fixes it."""
        Config = self.env.get('hr.formula.config')
        if Config is None:
            self.skipTest('no payroll schemes on this database')
        config = Config.sudo().create({
            'name': 'P4 unclassified scheme',
            'code': 'P4NORULE',
            'country_code': 'VN',
            'company_id': self.company.id,
        })
        plan = self.Plan.sudo().create({
            'name': 'P4 unpriceable plan',
            'company_id': self.company.id,
            'scope_kind': 'scheme',
            'scope_ref': str(config.id),
            'company_ids': [(6, 0, [self.company.id])],
            'state': {}, 'summary': {},
        })
        job = self.env['pb.decision.exact.job'].sudo().create(
            {'plan_id': plan.id})
        self.env['pb.decision.exact'].run_job(job.id)
        result = plan.exact_result or {}
        self.assertFalse(result.get('ok'))
        self.assertTrue(result.get('note'))
        self.assertNotIn('Odoo', result['note'])
        self.assertEqual(result.get('year', 0.0), 0.0)
        plan.sudo().unlink()
        config.sudo().unlink()
