# -*- coding: utf-8 -*-
"""GROUP P2 — who is paid by what.

T1  the resolver's rungs, in order, with the kind of run beating "any"
T2  `resolve_many` is fast and agrees with `resolve` one at a time
T3  one scheme per (team, kind of run), in a sentence, and the canvas replaces
    only the same kind of run
T4  "Paid by" is worked out again when anything that could change it changes,
    in bulk and never per record
T5  the map drafted from what was actually paid — and it writes nothing
T6  coverage names the people nobody pays
T7  LEDGER RULE 8: one scheme, no map → the identical pay-run population
T8  the payslip ladder consults the map, and a mixed run gets two answers
T9  the pay run refuses without a scheme, stamps it, and stays in one company
T10 the demo re-run is unchanged (rehearsed against the live division path)
T11 "Paid by" for one person, for the chip on their card

THE FIXTURE IS A COMPANY OF ITS OWN. Every test that asserts a rung builds its
own company, teams and schemes rather than leaning on whatever the database
happens to hold, because "the ladder reached rung 5" and "this database has one
scheme" look identical from the outside. The tests that need SCALE (T2, T5, T6)
use the demo company when it is there and say so when it is not.
"""

import time

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeMap(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Map = cls.env['pb.scheme.map']
        cls.Assign = cls.env['hr.formula.scheme.assignment']
        cls.Config = cls.env['hr.formula.config']
        cls.company = cls.env['res.company'].create({
            'name': 'P2 Fixture Co',
            'currency_id': cls.env.ref('base.VND').id,
        })
        cls.other = cls.env['res.company'].create({
            'name': 'P2 Fixture Co Two',
            'currency_id': cls.env.ref('base.VND').id,
        })
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.other.id)]

        Department = cls.env['hr.department']
        cls.top = Department.create({'name': 'P2 Bakery',
                                     'company_id': cls.company.id})
        cls.child = Department.create({'name': 'P2 Bread',
                                       'parent_id': cls.top.id,
                                       'company_id': cls.company.id})
        cls.loose = Department.create({'name': 'P2 Nobody',
                                       'company_id': cls.company.id})

        cls.end = cls._config('P2 End', 'P2END', 'end_cycle', cls.company)
        cls.mid = cls._config('P2 Mid', 'P2MID', 'mid_cycle', cls.company)
        cls.spare = cls._config('P2 Spare', 'P2SPARE', 'end_cycle', cls.company)

        cls.people = cls.env['hr.employee']
        for name, department in (('P2 Baker One', cls.child),
                                 ('P2 Baker Two', cls.child),
                                 ('P2 Boss', cls.top),
                                 ('P2 Stray', cls.loose)):
            cls.people |= cls._person(name, department, cls.company)

    # ------------------------------------------------------------- fixtures
    @classmethod
    def _config(cls, name, code, cycle, company):
        return cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle,
            'country_code': 'VN', 'company_id': company.id,
            'state': 'active',
        })

    @classmethod
    def _person(cls, name, department, company):
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id,
        })
        # The team lives on the version on this build (WFPLAN WF7); write it
        # wherever the field really is rather than assuming.
        version = employee.current_version_id
        if version and 'department_id' in version._fields:
            version.department_id = department.id
        elif 'department_id' in employee._fields:
            employee.department_id = department.id
        return employee

    @classmethod
    def _contract(cls, employee, company):
        """A running contract, with the two fields this build makes required.

        `resource_calendar_id` has no default on a company created inside a
        test, and `type_id` defaults to "the first one on the database", which
        is only there because some other module installed one.
        """
        calendar = company.resource_calendar_id or cls.env[
            'resource.calendar'].create({'name': 'P2 Hours',
                                         'company_id': company.id})
        kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P2 Kind'})
        return cls.env['hr.contract'].create({
            'name': 'P2 contract %s' % employee.id,
            'employee_id': employee.id,
            'company_id': company.id,
            'wage': 1000000.0,
            'state': 'open',
            'date_start': '2020-01-01',
            'resource_calendar_id': calendar.id,
            'type_id': kind.id,
        })

    def _resolve(self, employee, cycle='any'):
        return self.Map.resolve(employee.id, cycle)

    # =================================================================== T1
    def test_t1_the_ladder_climbs_in_order(self):
        """Every rung, tried in order, with a named kind of run beating "any"."""
        baker = self.people.filtered(lambda e: e.name == 'P2 Baker One')

        # Rung 5 first, because it is the one that has to answer BEFORE
        # anything is drawn — that is ledger rule 8's whole guarantee. Three
        # active schemes here, so it must NOT answer.
        answer = self._resolve(baker)
        self.assertEqual(answer['rung'], 'none')

        # …and with exactly one, it does.
        self.mid.state = 'draft'
        self.spare.state = 'draft'
        answer = self._resolve(baker)
        self.assertEqual(answer['rung'], 'only')
        self.assertEqual(answer['config_id'], self.end.id)
        self.mid.state = 'active'
        self.spare.state = 'active'

        # Rung 4 — a rule.
        rule = self.Assign.create({
            'config_id': self.spare.id,
            'domain': "[('name', '=', 'P2 Baker One')]",
            'cycle_type': 'any',
        })
        answer = self._resolve(baker)
        self.assertEqual(answer['rung'], 'rule')
        self.assertEqual(answer['config_id'], self.spare.id)

        # Rung 3 — the division the team belongs to.
        division = self.env['pb.division'].create({'name': 'P2 Food'})
        self.env['pb.division.link'].create({
            'division_id': division.id, 'department_id': self.top.id,
            'date_from': fields.Date.subtract(fields.Date.today(), days=1),
        })
        self.Assign.create({'config_id': self.end.id,
                            'division_id': division.id,
                            'cycle_type': 'any'})
        answer = self._resolve(baker)
        self.assertEqual(answer['rung'], 'division')
        self.assertEqual(answer['config_id'], self.end.id)

        # Rung 2 — the team ABOVE this one. An attachment at the top of a
        # branch covers everything under it.
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        answer = self._resolve(baker)
        self.assertEqual(answer['rung'], 'department')
        self.assertIn('P2 Bakery', answer['via'])

        # …and the team itself beats the team above it.
        self.Assign.create({'config_id': self.spare.id,
                            'department_id': self.child.id,
                            'cycle_type': 'any'})
        answer = self._resolve(baker)
        self.assertEqual(answer['config_id'], self.spare.id)
        self.assertIn('P2 Bread', answer['via'])

        # A named kind of run beats "any" for that kind, and leaves the others
        # exactly where they were.
        self.Assign.create({'config_id': self.mid.id,
                            'department_id': self.child.id,
                            'cycle_type': 'mid_cycle'})
        self.assertEqual(self._resolve(baker, 'mid_cycle')['config_id'],
                         self.mid.id)
        self.assertEqual(self._resolve(baker, 'end_cycle')['config_id'],
                         self.spare.id)
        rule.unlink()

    # =================================================================== T2
    def test_t2_resolving_thousands_is_one_answer_and_it_is_fast(self):
        """`resolve_many` agrees with `resolve`, and it is fast at scale."""
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        ids = self.people.ids
        bulk = self.Map.resolve_many(ids, 'any')
        for employee in self.people:
            one = self._resolve(employee)
            self.assertEqual(bulk[employee.id]['config_id'], one['config_id'])
            self.assertEqual(bulk[employee.id]['rung'], one['rung'])

        # Scale, where the database has it. The demo company is 4,533 people.
        big = self.env['res.company'].search(
            [], order='id').filtered(
            lambda c: self.env['hr.employee'].sudo().search_count(
                [('company_id', '=', c.id)]) > 500)[:1]
        if not big:
            return
        crowd = self.env['hr.employee'].sudo().search(
            [('company_id', '=', big.id)]).ids
        started = time.time()
        answers = self.Map.resolve_many(crowd, 'any')
        took = int((time.time() - started) * 1000)
        self.assertEqual(len(answers), len(crowd))
        self.assertLess(took, 3000,
                        'resolving %s people took %s ms' % (len(crowd), took))
        # A 200-person sample must agree, one at a time, with the bulk answer.
        for employee_id in crowd[:200]:
            one = self.Map.resolve(employee_id, 'any')
            self.assertEqual(one['config_id'], answers[employee_id]['config_id'])

    # =================================================================== T3
    def test_t3_one_scheme_per_team_per_kind_of_run(self):
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'end_cycle'})
        # The same team, the same kind of run, a second scheme: refused, and
        # the refusal is a sentence a person can act on.
        with self.assertRaises(ValidationError) as caught:
            self.Assign.create({'config_id': self.spare.id,
                                'department_id': self.top.id,
                                'cycle_type': 'end_cycle'})
        message = str(caught.exception)
        self.assertIn('P2 Bakery', message)
        self.assertIn('P2 End', message)
        self.assertNotIn('unique constraint', message.lower())

        # A DIFFERENT kind of run on the same team is fine — that is the whole
        # point of the field.
        self.Assign.create({'config_id': self.mid.id,
                            'department_id': self.top.id,
                            'cycle_type': 'mid_cycle'})

        # A division, twice, for one kind of run: refused the same way.
        division = self.env['pb.division'].create({'name': 'P2 Line'})
        self.Assign.create({'config_id': self.end.id,
                            'division_id': division.id,
                            'cycle_type': 'end_cycle'})
        with self.assertRaises(ValidationError):
            self.Assign.create({'config_id': self.spare.id,
                                'division_id': division.id,
                                'cycle_type': 'end_cycle'})

        # And the canvas replaces only the SAME kind of run — it used to wipe
        # every line the team had.
        studio = self.env['pb.formula.studio']
        result = studio.with_company(self.company).scheme_mapping_create(
            False, False, self.top.id, self.spare.id)
        self.assertTrue(result.get('ok'), result)
        rows = self.Assign.search([('department_id', '=', self.top.id),
                                   ('active', '=', True)])
        self.assertEqual(
            sorted(rows.mapped('cycle_type')), ['end_cycle', 'mid_cycle'],
            'attaching an end-of-month scheme deleted the mid-month line')
        self.assertEqual(
            rows.filtered(lambda r: r.cycle_type == 'end_cycle').config_id,
            self.spare)

    # =================================================================== T4
    def test_t4_paid_by_is_worked_out_again_when_it_could_have_changed(self):
        Employee = self.env['hr.employee']
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        Employee._pb_recompute_paid_by(company_ids=[self.company.id])
        baker = self.people.filtered(lambda e: e.name == 'P2 Baker One')
        self.assertEqual(baker.pb_paid_by_id, self.end)
        self.assertFalse(baker.pb_paid_by_stale)
        self.assertIn('P2 Bakery', baker.pb_paid_by_rung or '')

        # A line on the map moves → everybody in that company is stale again.
        row = self.Assign.create({'config_id': self.spare.id,
                                  'department_id': self.child.id,
                                  'cycle_type': 'any'})
        baker.invalidate_recordset()
        self.assertTrue(baker.pb_paid_by_stale)
        changed = Employee._pb_recompute_paid_by(company_ids=[self.company.id])
        self.assertTrue(changed)
        self.assertEqual(baker.pb_paid_by_id, self.spare)

        # A scheme switched off does it too.
        self.spare.state = 'draft'
        baker.invalidate_recordset()
        self.assertTrue(baker.pb_paid_by_stale)
        self.spare.state = 'active'

        # …and so does a division attachment.
        division = self.env['pb.division'].create({'name': 'P2 Wing'})
        Employee._pb_recompute_paid_by(company_ids=[self.company.id])
        self.env['pb.division.link'].create({
            'division_id': division.id, 'department_id': self.loose.id})
        stray = self.people.filtered(lambda e: e.name == 'P2 Stray')
        stray.invalidate_recordset()
        self.assertTrue(stray.pb_paid_by_stale)

        # THE BULK PATH. Working out 4 people must not cost 4 resolutions'
        # worth of queries — the recompute is grouped by the answer, so the
        # writes are counted in answers and not in people.
        row.unlink()
        Employee._pb_recompute_paid_by(company_ids=[self.company.id])
        counter = getattr(self.env.cr, 'sql_log_count', None)
        if counter is not None:
            before = self.env.cr.sql_log_count
            Employee._pb_recompute_paid_by(company_ids=[self.company.id])
            spent = self.env.cr.sql_log_count - before
            self.assertLess(spent, 60,
                            'working "paid by" out again cost %s queries for '
                            '4 people — it is resolving per record' % spent)

        # The nightly job runs, and afterwards there is nothing left to settle
        # in this company. (It is asserted per company on purpose: the job is
        # database-wide and a real database always has somebody else's edits in
        # flight, so "the whole database is settled" is not a fact a test can
        # own.)
        self.assertGreaterEqual(Employee._pb_cron_recompute_paid_by(), 0)
        self.assertEqual(Employee._pb_recompute_paid_by(
            company_ids=[self.company.id], only_stale=True), 0)

    # =================================================================== T5
    def test_t5_the_map_can_be_read_from_what_was_actually_paid(self):
        """A proposal per team, with the numbers behind it, and NO writes."""
        company = self._demo_company()
        if not company:
            self.skipTest('no company on this database has paid anybody under '
                          'a scheme yet')
        before = self.Assign.search_count([])
        draft = self.Map.draft(company.id)
        self.assertEqual(self.Assign.search_count([]), before,
                         'drafting the map wrote something')
        rows = draft['rows']
        self.assertTrue(rows, 'nothing was proposed from real pay history')
        for row in rows:
            self.assertTrue(row['sentence'])
            self.assertTrue(row['config_id'])
            self.assertLessEqual(row['agree'], row['total'])
            self.assertEqual(row['confident'], row['confidence'] >= 0.9)

        # The end-of-month proposals are the ones a person acts on first, and
        # on a company that has been paying divisions for months they agree.
        ends = [r for r in rows if r['cycle_type'] == 'end_cycle']
        if ends:
            self.assertTrue(any(r['confidence'] >= 0.99 for r in ends))

        # Accepting writes exactly what was ticked, and says where it came from.
        picked = [r for r in rows if r['confident']][:1]
        if picked:
            result = self.Map.accept_draft(picked)
            self.assertEqual(result['created'], 1)
            written = self.Assign.search(
                [('department_id', '=', picked[0]['department_id']),
                 ('cycle_type', '=', picked[0]['cycle_type'])], limit=1)
            self.assertEqual(written.source, 'accepted')
            self.assertTrue(written.note)
            written.unlink()

    def _demo_company(self):
        self.env.cr.execute("""
            SELECT company_id, COUNT(*)
              FROM hr_payslip
             WHERE formula_config_id IS NOT NULL
          GROUP BY 1 ORDER BY 2 DESC LIMIT 1
        """)
        row = self.env.cr.fetchone()
        return self.env['res.company'].browse(row[0]) if row else None

    # =================================================================== T6
    def test_t6_the_people_nobody_pays_are_named(self):
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        answer = self.Map.coverage(self.company.id, 'any')
        self.assertEqual(answer['people'], 4)
        self.assertEqual(answer['covered'], 3)
        self.assertEqual(answer['not_covered_total'], 1)
        named = answer['not_covered'][0]
        self.assertEqual(named['name'], 'P2 Stray')
        self.assertEqual(named['department'], 'P2 Nobody')
        self.assertTrue(named['reason'])
        # The queue is the same list, said once.
        queue = self.Map.get_exceptions(self.company.id, 'any')
        self.assertEqual(queue['total'], 1)
        self.assertEqual(queue['people'][0]['name'], 'P2 Stray')

    # =================================================================== T7
    def test_t7_rule_8_one_scheme_and_no_map_changes_nothing(self):
        """LEDGER RULE 8, enforced.

        A company with exactly one live scheme and not a single line on the
        map must produce the IDENTICAL pay-run population it produced before
        this phase existed — which is every person with a running contract.
        """
        solo = self.env['res.company'].create({
            'name': 'P2 One Scheme Co',
            'currency_id': self.env.ref('base.VND').id,
        })
        self.env.user.company_ids = [(4, solo.id)]
        department = self.env['hr.department'].create(
            {'name': 'P2 Solo Team', 'company_id': solo.id})
        people = self.env['hr.employee']
        for n in range(3):
            people |= self._person('P2 Solo %s' % n, department, solo)
        config = self._config('P2 Solo Scheme', 'P2SOLO', 'regular', solo)
        for employee in people:
            self._contract(employee, solo)
        Wizard = self.env['pb.payrun.wizard'].with_company(solo)
        self.assertFalse(self.Assign.search_count([('company_id', '=', solo.id)]))

        # Before: no scheme named at all — the answer that shipped.
        before = set(Wizard._eligible_employees())
        # After: the scheme named — and it is the SAME set, person for person.
        after = set(Wizard._eligible_employees(formula_config_id=config.id))
        self.assertEqual(before, after)
        self.assertEqual(before, set(people.ids))
        # And the resolver agrees, on the "only scheme" rung.
        answers = self.Map.resolve_many(people.ids, 'any')
        for employee_id in people.ids:
            self.assertEqual(answers[employee_id]['rung'], 'only')
            self.assertEqual(answers[employee_id]['config_id'], config.id)

        # One line on the map, and the population narrows to what it covers.
        second = self._config('P2 Solo Two', 'P2SOLO2', 'regular', solo)
        self.Assign.create({'config_id': second.id,
                            'department_id': department.id,
                            'cycle_type': 'any'})
        narrowed = set(Wizard._eligible_employees(formula_config_id=config.id))
        self.assertFalse(narrowed)
        self.assertEqual(
            set(Wizard._eligible_employees(formula_config_id=second.id)),
            set(people.ids))

    # =================================================================== T8
    def test_t8_the_payslip_ladder_asks_the_map(self):
        """A mixed run gets one answer per person, never one for all."""
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        self.Assign.create({'config_id': self.spare.id,
                            'department_id': self.loose.id,
                            'cycle_type': 'any'})
        run = self.env['hr.payslip.run'].create({
            'name': 'P2 mixed run',
            'date_start': fields.Date.today().replace(day=1),
            'date_end': fields.Date.today(),
        })
        Slip = self.env['hr.payslip']
        found = {}
        for employee in self.people:
            slip = Slip.create({
                'employee_id': employee.id,
                'name': 'P2 slip %s' % employee.id,
                'payslip_run_id': run.id,
                'company_id': self.company.id,
                'date_from': run.date_start, 'date_to': run.date_end,
            })
            found[employee.name] = slip._find_formula_config()
        self.assertEqual(found['P2 Baker One'], self.end)
        self.assertEqual(found['P2 Stray'], self.spare)
        self.assertNotEqual(found['P2 Baker One'], found['P2 Stray'],
                            'one person infected the whole run')

        # A run that NAMES a scheme beats everything: that is a person's own
        # choice, made before anything was created.
        run.pb_formula_config_id = self.mid.id
        stray = self.env['hr.payslip'].search(
            [('payslip_run_id', '=', run.id)], limit=1)
        self.assertEqual(stray._find_formula_config(), self.mid)

    # =================================================================== T9
    def test_t9_the_pay_run_asks_which_scheme_and_writes_it_down(self):
        Wizard = self.env['pb.payrun.wizard'].with_company(self.company)
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        for employee in self.people:
            self._contract(employee, self.company)

        # Three live schemes and no answer → a plain refusal, not a guess.
        with self.assertRaises(UserError) as caught:
            Wizard.prepare_run({'name': 'P2 run', 'date_start': '2027-03-01',
                                'date_end': '2027-03-31'})
        self.assertIn('scheme', str(caught.exception).lower())

        # The cards are this company's schemes, and nobody else's.
        cards = Wizard.get_defaults()['schemes']
        self.assertEqual({c['id'] for c in cards},
                         {self.end.id, self.mid.id, self.spare.id})
        self.assertTrue(all(c['cycle_label'] for c in cards))

        # A scheme named: the run carries it and so does every payslip.
        payload = Wizard.prepare_run({
            'name': 'P2 run', 'date_start': '2027-03-01',
            'date_end': '2027-03-31', 'formula_config_id': self.end.id})
        self.assertEqual(payload['formula_config_id'], self.end.id)
        run = self.env['hr.payslip.run'].browse(payload['run_id'])
        self.assertEqual(run.pb_formula_config_id, self.end)
        Wizard.compute_batch(payload)
        slips = self.env['hr.payslip'].search([('payslip_run_id', '=', run.id)])
        self.assertTrue(slips)
        self.assertEqual(slips.mapped('formula_config_id'), self.end)

        # ONE COMPANY. A second allowed company's people are not in the run,
        # however many companies the reader has switched on.
        other_dept = self.env['hr.department'].create(
            {'name': 'P2 Elsewhere', 'company_id': self.other.id})
        stranger = self._person('P2 Stranger', other_dept, self.other)
        self._contract(stranger, self.other)
        eligible = Wizard.with_context(
            allowed_company_ids=[self.company.id, self.other.id]
        )._eligible_employees()
        self.assertNotIn(stranger.id, eligible)

        run.slip_ids.unlink()
        run.unlink()

    # =================================================================== T10
    def test_t10_the_demo_run_still_computes_the_same_way(self):
        """The demo's division path is reconciled, not replaced.

        The scheme picker and the division tag are two statements about one
        run; this asserts they agree — the chosen scheme decides, and where no
        scheme is chosen the division still does exactly what it always did.
        """
        Wizard = self.env['pb.payrun.wizard']
        if not hasattr(Wizard, '_demo_division_for'):
            self.skipTest('the demo module is not installed on this database')
        config = self.env['hr.formula.config'].sudo().search(
            [('pb_division', '!=', False), ('state', '=', 'active'),
             ('cycle_type', '=', 'end_cycle')], limit=1)
        if not config:
            self.skipTest('this database has no demo division schemes')
        wizard = Wizard.with_company(config.company_id)
        # A scheme, no division tag: the division is derived from the scheme.
        self.assertEqual(
            wizard._demo_division_for({'formula_config_id': config.id}),
            config.pb_division)
        # And the scheme that computes is the chosen one, not "the End-cycle
        # scheme for this division" picked again from scratch.
        self.assertEqual(
            wizard._demo_run_config({'formula_config_id': config.id},
                                    config.pb_division), config)
        # A division tag and no scheme: exactly what shipped.
        self.assertEqual(
            wizard._demo_division_for({'division': config.pb_division}),
            config.pb_division)
        # Neither: the generic path, untouched.
        self.assertIsNone(wizard._demo_division_for({}))

    # =================================================================== T11
    def test_t11_paid_by_for_one_person(self):
        Board = self.env['pb.scheme.board']
        self.Assign.create({'config_id': self.end.id,
                            'department_id': self.top.id,
                            'cycle_type': 'any'})
        self.env['hr.employee']._pb_recompute_paid_by(
            company_ids=[self.company.id])
        baker = self.people.filtered(lambda e: e.name == 'P2 Baker One')
        chip = Board.paid_by(baker.id)
        self.assertTrue(chip['allowed'])
        self.assertTrue(chip['found'])
        self.assertEqual(chip['config'], 'P2 End')
        self.assertIn('P2 Bakery', chip['via'])

        stray = self.people.filtered(lambda e: e.name == 'P2 Stray')
        chip = Board.paid_by(stray.id)
        self.assertFalse(chip['config_id'])
        self.assertTrue(chip['label'])
        self.assertNotEqual(chip['label'], '')

    # ------------------------------------------------------------ the board
    def test_the_board_is_one_company_and_refuses_a_reader(self):
        Board = self.env['pb.scheme.board'].with_company(self.company)
        board = Board.get_board(self.company.id)
        self.assertTrue(board['allowed'])
        self.assertEqual(board['company_id'], self.company.id)
        self.assertEqual({s['id'] for s in board['schemes']},
                         {self.end.id, self.mid.id, self.spare.id})
        keys = {s['key'] for s in board['segments']}
        self.assertIn('department-%s' % self.top.id, keys)
        self.assertNotIn('department-%s' % self.child.id, keys,
                         'a child team is reached through its parent, not '
                         'listed beside it')

        # Attaching across a company border is refused in words.
        other_dept = self.env['hr.department'].create(
            {'name': 'P2 Border', 'company_id': self.other.id})
        with self.assertRaises(UserError):
            Board.attach('department-%s' % other_dept.id, self.end.id, 'any',
                         self.company.id)

    def test_a_reader_without_payroll_rights_cannot_change_the_map(self):
        reader = self.env['res.users'].create({
            'name': 'P2 Reader', 'login': 'p2.reader@payobook.test',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        Board = self.env['pb.scheme.board'].with_user(reader).with_company(
            self.company)
        with self.assertRaises(AccessError):
            Board.attach('department-%s' % self.top.id, self.end.id, 'any',
                         self.company.id)
