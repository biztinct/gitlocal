# -*- coding: utf-8 -*-
"""GROUP P6a — what pay bands and fairness promise, tested.

T1  band constraints, and one job in one band at a time
T2  positions: one row per open contract, the right numbers, the one pass
T3  health cards on fixtures with known answers
T4  move_edge: the dry run costs what it says, writes nothing, and undoes
T5  place_hire: a band, a middle, an offer inside the range, and a refusal
T6  import: bad rows flagged, good rows written, export round-trips
T7  fairness: the median gap, the five-person floor, the spread, the names
T8  fairness across two currencies: refused, then converted through pb.fx
T9  the migration from the old Pay Grades, and the legacy left untouched
T10 the contract screens read the new fields and name the old ones nowhere
"""

import base64
import os
import re
import subprocess
import time
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)


@tagged('post_install', '-at_install')
class TestPayBands(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Family = cls.env['pb.pay.family']
        cls.Band = cls.env['pb.pay.band']
        cls.Link = cls.env['pb.pay.band.job']
        cls.Position = cls.env['pb.pay.position']
        cls.Bands = cls.env['pb.pay.bands']
        cls.Fair = cls.env['pb.pay.fairness']

        cls.currency = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.env.company.currency_id
        cls.company = cls.env['res.company'].create({
            'name': 'Pay Test Co', 'currency_id': cls.currency.id})
        cls.env.user.company_ids = [(4, cls.company.id)]

        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Pay Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Pay Type'})

        cls.job = cls.env['hr.job'].create({
            'name': 'Pay Test Operator', 'company_id': cls.company.id})
        cls.job2 = cls.env['hr.job'].create({
            'name': 'Pay Test Engineer', 'company_id': cls.company.id})

        cls.family = cls.Family.create({'name': 'Pay Test Family'})
        cls.band = cls.Band.create({
            'family_id': cls.family.id, 'level': 3, 'country_code': 'VN',
            'currency_id': cls.currency.id,
            'min_amount': 1000.0, 'mid_amount': 2000.0, 'max_amount': 3000.0,
            'date_from': '2020-01-01',
        })
        cls.Link.create({'band_id': cls.band.id, 'job_id': cls.job.id})

    # ------------------------------------------------------------ helpers
    @classmethod
    def _person(cls, name, wage, job=None, sex='female', months=48,
                company=None, manager=None):
        company = company or cls.company
        employee = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id,
            'parent_id': manager.id if manager else False,
        })
        if employee.current_version_id:
            employee.current_version_id.write({
                'sex': sex, 'job_id': (job or cls.job).id})
        start = date.today() - timedelta(days=int(months * 30.4))
        cls.env['hr.contract'].create({
            'name': 'Contract %s' % name,
            'employee_id': employee.id,
            'company_id': company.id,
            'date_start': start,
            'state': 'open',
            'wage': wage,
            'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        return employee

    def _rows(self, employees):
        return self.Position.search([
            ('employee_id', 'in', [e.id for e in employees])])

    # ================================================================== T1
    def test_t01_a_band_reads_lowest_middle_highest(self):
        with self.assertRaises(ValidationError):
            self.Band.create({
                'family_id': self.family.id, 'level': 5,
                'country_code': 'VN', 'currency_id': self.currency.id,
                'min_amount': 3000.0, 'mid_amount': 2000.0,
                'max_amount': 1000.0, 'date_from': '2020-01-01'})

    def test_t01_two_ranges_may_not_cover_the_same_days(self):
        with self.assertRaises(ValidationError) as caught:
            self.Band.create({
                'family_id': self.family.id, 'level': 3,
                'country_code': 'VN', 'currency_id': self.currency.id,
                'min_amount': 1.0, 'mid_amount': 2.0, 'max_amount': 3.0,
                'date_from': '2021-01-01'})
        self.assertIn('same days', str(caught.exception))

    def test_t01_a_range_that_starts_after_the_old_one_ends_is_fine(self):
        self.band.date_to = '2020-12-31'
        later = self.Band.create({
            'family_id': self.family.id, 'level': 3, 'country_code': 'VN',
            'currency_id': self.currency.id, 'min_amount': 1100.0,
            'mid_amount': 2200.0, 'max_amount': 3300.0,
            'date_from': '2021-01-01'})
        self.assertTrue(later.id)
        later.unlink()
        self.band.date_to = False

    def test_t01_a_level_runs_from_one_to_twelve(self):
        with self.assertRaises(ValidationError):
            self.Band.create({
                'family_id': self.family.id, 'level': 44,
                'country_code': 'VN', 'currency_id': self.currency.id,
                'min_amount': 1.0, 'mid_amount': 2.0, 'max_amount': 3.0,
                'date_from': '2020-01-01'})

    def test_t01_a_job_sits_in_one_band_at_a_time(self):
        other = self.Band.create({
            'family_id': self.family.id, 'level': 7, 'country_code': 'VN',
            'currency_id': self.currency.id, 'min_amount': 1.0,
            'mid_amount': 2.0, 'max_amount': 3.0, 'date_from': '2020-01-01'})
        with self.assertRaises(ValidationError) as caught:
            self.Link.create({'band_id': other.id, 'job_id': self.job.id})
        self.assertIn('one band at a time', str(caught.exception))
        other.unlink()

    def test_t01_the_band_name_is_a_sentence(self):
        self.assertIn('level 3', self.band.name)
        self.assertIn('Vietnam', self.band.name)

    # ================================================================== T2
    def test_t02_one_row_per_open_contract_with_the_right_numbers(self):
        low = self._person('Pay Below', 500.0)
        inside = self._person('Pay Inside', 2500.0)
        high = self._person('Pay Above', 4000.0)
        loose = self._person('Pay Unbanded', 900.0, job=self.job2)
        self.Position.recompute_all([self.company.id])

        rows = {r.employee_id.id: r
                for r in self._rows([low, inside, high, loose])}
        self.assertEqual(len(rows), 4, 'one row per open contract')
        self.assertEqual(rows[low.id].state, 'below')
        self.assertEqual(rows[inside.id].state, 'in')
        self.assertEqual(rows[high.id].state, 'above')
        self.assertEqual(rows[loose.id].state, 'no_band')
        # (2500 - 1000) / (3000 - 1000) = 75%
        self.assertAlmostEqual(rows[inside.id].position_pct, 75.0, places=2)
        # 2500 / 2000 = 1.25
        self.assertAlmostEqual(rows[inside.id].compa, 1.25, places=4)
        self.assertEqual(rows[inside.id].band_id, self.band)
        self.assertFalse(rows[loose.id].band_id)

    def test_t02_a_closed_contract_leaves_the_table(self):
        person = self._person('Pay Leaver', 2000.0)
        self.Position.recompute_all([self.company.id])
        self.assertTrue(self._rows([person]))
        person.contract_ids.write({'state': 'close'})
        self.Position.recompute_all([self.company.id])
        self.assertFalse(self._rows([person]))

    def test_t02_the_pass_is_one_statement_and_it_is_fast(self):
        for index in range(60):
            self._person('Pay Bulk %s' % index, 1500.0 + index)
        started = time.time()
        made = self.Position.recompute_all([self.company.id])
        elapsed = time.time() - started
        self.assertGreaterEqual(made, 60)
        # Sixty people is not four thousand, but a pass that is quadratic
        # shows up here long before it shows up on the demo company.
        self.assertLess(elapsed, 2.0,
                        'the position pass took %.2f s for %s rows'
                        % (elapsed, made))

    def test_t02_a_wage_change_queues_a_rebuild(self):
        person = self._person('Pay Riser', 1200.0)
        self.Position.recompute_all([self.company.id])
        self.assertEqual(self._rows([person]).state, 'in')
        person.contract_ids.write({'wage': 9000.0})
        # GR28's cousin: the rebuild is queued on the cursor's precommit so a
        # bulk import pays for it once. A test has to run it by hand, because
        # a test never commits.
        self.env.cr.precommit.run()
        self.assertEqual(self._rows([person]).state, 'above')

    def test_t02_the_cron_names_a_model_every_worker_has(self):
        cron = self.env.ref('pb_pay.cron_pay_positions')
        self.assertEqual(cron.model_id.model, 'res.company')
        self.assertIn("'pb.pay.position' in env", cron.code)

    # ================================================================== T3
    def test_t03_health_cards_answer_what_they_claim(self):
        self._person('Pay H Below', 400.0)
        self._person('Pay H Above', 5000.0)
        # compression: three long-serving people and one brand new one above
        # the middle of them.
        for index, wage in enumerate((1200.0, 1400.0, 1600.0)):
            self._person('Pay Old %s' % index, wage, months=60)
        self._person('Pay New', 2800.0, months=2)
        # inversion: a manager paid less than their own report.
        boss = self._person('Pay Boss', 1100.0)
        self._person('Pay Report', 2900.0, manager=boss)
        self.Position.recompute_all([self.company.id])

        cards = {card['key']: card
                 for card in self.Bands.health_cards([self.company.id])}
        self.assertEqual(set(cards), {'below', 'above', 'compression',
                                      'inversion', 'spread'})
        self.assertGreaterEqual(cards['below']['count'], 1)
        self.assertGreaterEqual(cards['above']['count'], 1)
        self.assertGreaterEqual(cards['compression']['count'], 1)
        self.assertGreaterEqual(cards['inversion']['count'], 1)
        for card in cards.values():
            self.assertTrue(card['method'],
                            '%s prints a number with no method' % card['key'])
        names = [row['name'] for row in cards['compression']['rows']]
        self.assertIn('Pay New', names)
        names = [row['name'] for row in cards['inversion']['rows']]
        self.assertIn('Pay Boss', names)

    def test_t03_spread_is_the_highest_over_the_lowest(self):
        self._person('Pay Sp Low', 1000.0)
        self._person('Pay Sp High', 3000.0)
        self.Position.recompute_all([self.company.id])
        cards = {card['key']: card
                 for card in self.Bands.health_cards([self.company.id])}
        rows = {row['name']: row for row in cards['spread']['rows']}
        self.assertIn(self.band.name, rows)
        self.assertAlmostEqual(rows[self.band.name]['pct'], 200.0, places=0)

    # ================================================================== T4
    def test_t04_a_dry_run_costs_what_it_says_and_writes_nothing(self):
        self._person('Pay Edge A', 1200.0)
        self._person('Pay Edge B', 1400.0)
        self.Position.recompute_all([self.company.id])
        before = (self.band.min_amount, self.band.mid_amount,
                  self.band.max_amount)

        answer = self.Bands.move_edge(self.band.id, 'min', 1500.0, True)
        self.assertTrue(answer['ok'])
        self.assertEqual(answer['count'], 2)
        # (1500 - 1200) + (1500 - 1400) = 400 a month, 4,800 a year
        self.assertAlmostEqual(answer['cost'], 4800.0, places=2)
        self.assertFalse(answer['saved'])
        self.assertEqual((self.band.min_amount, self.band.mid_amount,
                          self.band.max_amount), before,
                         'a dry run wrote to the band')

    def test_t04_a_committed_edge_writes_and_undoes_exactly(self):
        self._person('Pay Edge C', 1200.0)
        self.Position.recompute_all([self.company.id])
        before = {'min': self.band.min_amount, 'mid': self.band.mid_amount,
                  'max': self.band.max_amount}
        answer = self.Bands.move_edge(self.band.id, 'min', 1500.0, False)
        self.assertTrue(answer['saved'])
        self.assertEqual(answer['previous'], before)
        self.assertAlmostEqual(self.band.min_amount, 1500.0, places=2)

        self.Bands.set_band_range(self.band.id, before['min'], before['mid'],
                                  before['max'])
        self.assertAlmostEqual(self.band.min_amount, before['min'], places=2)

    def test_t04_an_edge_that_crosses_the_other_one_is_refused(self):
        answer = self.Bands.move_edge(self.band.id, 'min', 99999.0, True)
        self.assertFalse(answer['ok'])
        self.assertIn('under the highest', answer['sentence'])

    def test_t04_a_refused_move_never_answers_as_though_it_had_moved(self):
        """LOOK L8, the server half. A refusal carries no `saved` and no
        `previous`, so the screen has nothing to build an undo bar out of and
        nothing was written to put back."""
        before = (self.band.min_amount, self.band.max_amount)
        answer = self.Bands.move_edge(self.band.id, 'min', 99999.0, False)
        self.assertFalse(answer['ok'])
        self.assertNotIn('saved', answer)
        self.assertNotIn('previous', answer)
        self.assertEqual((self.band.min_amount, self.band.max_amount), before,
                         'a refused move wrote to the band')

    # ------------------------------------------------ LOOK L7: "1 people"
    def test_look_l7_the_shared_axis_says_1_person_not_1_people(self):
        """The lane's own tail note is built for every count from one frame,
        which is GR42's trap in the one place GR42 did not sweep. Vietnamese
        hides it (there is no plural), so only an English reading finds it."""
        bands = [{'min': 1000.0, 'mid': 2000.0, 'max': 3000.0}]
        wages = [{'wage': 1000.0 + (n * 10)} for n in range(100)]
        one = self.Bands._lane_axis(
            bands, wages + [{'wage': 90_000_000.0}], self.currency)
        self.assertEqual(one['beyond'], 1)
        self.assertIn('1 person is paid more', one['note'])
        self.assertNotIn('1 people', one['note'])

        many = self.Bands._lane_axis(
            bands,
            wages + [{'wage': 90_000_000.0}, {'wage': 91_000_000.0},
                     {'wage': 92_000_000.0}],
            self.currency)
        self.assertEqual(many['beyond'], 3)
        self.assertIn('3 people are paid more', many['note'])

        none = self.Bands._lane_axis(bands, wages, self.currency)
        self.assertEqual(none['beyond'], 0)
        self.assertEqual(none['note'], '')

    # ================================================================== T5
    def test_t05_place_a_hire_lands_inside_the_band(self):
        self._person('Pay P1', 1800.0)
        self._person('Pay P2', 2200.0)
        self.Position.recompute_all([self.company.id])
        answer = self.Bands.place_hire(self.job.id, 0, 50)
        self.assertTrue(answer['ok'])
        self.assertTrue(answer['band'])
        self.assertGreaterEqual(answer['offer'], self.band.min_amount)
        self.assertLessEqual(answer['offer'], self.band.max_amount)
        self.assertAlmostEqual(answer['median'], 2000.0, places=2)
        self.assertTrue(answer['sentence'])

        junior = self.Bands.place_hire(self.job.id, 0, 0)
        senior = self.Bands.place_hire(self.job.id, 0, 100)
        self.assertLess(junior['offer'], senior['offer'])

    def test_t05_a_job_with_no_band_explains_itself(self):
        answer = self.Bands.place_hire(self.job2.id, 0, 50)
        self.assertTrue(answer['ok'])
        self.assertFalse(answer['band'])
        self.assertIn('not in a band yet', answer['sentence'])

    def test_t05_no_job_at_all_asks_for_one(self):
        answer = self.Bands.place_hire(0, 0, 50)
        self.assertFalse(answer['ok'])
        self.assertTrue(answer['sentence'])

    # ================================================================== T6
    def _csv(self, lines):
        return base64.b64encode('\n'.join(lines).encode('utf-8')).decode()

    def test_t06_a_bad_row_is_named_and_the_good_ones_still_land(self):
        content = self._csv([
            'Job family,Level,Country,Currency,Lowest,Middle,Highest,From,Until',
            'Imported Ops,2,VN,VND,1000,2000,3000,,',
            'Imported Ops,99,ZZ,VND,3000,2000,1000,,',
            'Imported Sales,4,VN,VND,5000,6000,7000,,',
        ])
        preview = self.Bands.import_bands(content, True)
        self.assertTrue(preview['ok'])
        self.assertEqual(preview['good'], 2)
        self.assertEqual(preview['bad'], 1)
        bad = [row for row in preview['rows'] if row['problem']]
        self.assertEqual(len(bad), 1)
        self.assertIn('1 to 12', bad[0]['problem'])
        self.assertEqual(self.Band.search_count(
            [('family_id.name', '=', 'Imported Ops')]), 0,
            'a preview wrote a band')

        answer = self.Bands.import_bands(content, False)
        self.assertEqual(answer['made'], 2)
        made = self.Band.search([('family_id.name', '=', 'Imported Ops')])
        self.assertEqual(len(made), 1)
        self.assertAlmostEqual(made.mid_amount, 2000.0, places=2)

    def test_t06_export_round_trips(self):
        dump = self.Bands.export_bands()
        text = base64.b64decode(dump['content']).decode('utf-8')
        self.assertIn('Job family', text)
        self.assertIn(self.family.name, text)
        again = self.Bands.import_bands(
            base64.b64encode(text.encode('utf-8')).decode(), True)
        self.assertEqual(again['bad'], 0,
                         'the export does not read back cleanly: %s'
                         % [r['problem'] for r in again['rows']
                            if r['problem']])

    def test_t06_a_file_that_is_not_a_spreadsheet_says_so(self):
        answer = self.Bands.import_bands('not base 64 at all', True)
        self.assertFalse(answer['ok'])
        self.assertTrue(answer['sentence'])

    # ================================================================== T7
    def _gender_fixture(self):
        for index in range(6):
            self._person('Pay W%s' % index, 1000.0, sex='female')
        for index in range(6):
            self._person('Pay M%s' % index, 1200.0, sex='male')
        self.Position.recompute_all([self.company.id])

    def test_t07_the_gap_is_median_based_and_like_for_like(self):
        self._gender_fixture()
        board = self.Fair.get_board('company', self.company.id)
        self.assertTrue(board['allowed'])
        cards = {card['key']: card for card in board['cards']}
        # (1200 - 1000) / 1200 = 16.67%
        self.assertAlmostEqual(cards['gender']['value'], 16.7, places=1)
        self.assertTrue(cards['gender']['method'])
        self.assertTrue(cards['gender']['population'])
        self.assertTrue(board['headline'])
        self.assertTrue(board['method'])

    def test_t07_fewer_than_five_a_side_refuses_to_answer(self):
        for index in range(3):
            self._person('Pay Few W%s' % index, 1000.0, sex='female')
        for index in range(3):
            self._person('Pay Few M%s' % index, 1500.0, sex='male')
        self.Position.recompute_all([self.company.id])
        board = self.Fair.get_board('company', self.company.id)
        cards = {card['key']: card for card in board['cards']}
        self.assertIsNone(cards['gender']['value'])
        self.assertIn('Not enough people', cards['gender']['sentence'])

    def test_t07_same_job_spread_and_the_lowest_paid(self):
        self._person('Pay S1', 1000.0)
        self._person('Pay S2', 2000.0)
        self._person('Pay S3', 3000.0)
        self.Position.recompute_all([self.company.id])
        board = self.Fair.get_board('company', self.company.id)
        rows = {row['name']: row for row in board['spread']}
        self.assertIn(self.job.display_name, rows)
        self.assertGreaterEqual(rows[self.job.display_name]['people'], 3)
        low = [row for row in board['lowest'] if row['under'] >= 15.0]
        self.assertTrue(low, 'nobody was found paid least for the same work')

    def test_t07_nothing_is_stored(self):
        self._gender_fixture()
        before = self.env['ir.model'].search_count([])
        self.Fair.get_board('company', self.company.id)
        self.assertEqual(self.env['ir.model'].search_count([]), before)
        self.assertFalse(
            [name for name in self.env.registry.models
             if name.startswith('pb.pay.fairness.')],
            'fairness must own no table')

    def test_t07_a_viewer_sees_counts_and_no_names(self):
        self._person('Pay Secret Low', 500.0)
        self._person('Pay Secret A', 2000.0)
        self._person('Pay Secret B', 2100.0)
        self._person('Pay Secret C', 2200.0)
        self.Position.recompute_all([self.company.id])
        viewer = self.env['res.users'].create({
            'name': 'Pay Viewer', 'login': 'pay.viewer.test',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [
                self.env.ref('pb_pay.group_pay_viewer').id,
                self.env.ref('base.group_user').id])],
        })
        board = self.Fair.with_user(viewer).get_board(
            'company', self.company.id)
        self.assertTrue(board['allowed'])
        self.assertFalse(board['can_see_names'])
        for row in board['lowest']:
            self.assertEqual(row['id'], 0)
            self.assertNotIn('Secret', row['name'])

    def test_t07_the_printed_statement_is_self_contained(self):
        self._gender_fixture()
        html = self.Fair.print_statement('company', self.company.id)
        self.assertIn('<!doctype html>', html)
        self.assertNotIn('<script', html.lower())
        self.assertNotIn('<link', html.lower())
        self.assertNotIn('http://', html)
        self.assertNotIn('https://', html)

    # ================================================================== T8
    def test_t08_two_currencies_are_never_added_without_a_rate(self):
        other = self.env['res.currency'].search(
            [('name', '=', 'SGD')], limit=1)
        if not other:
            self.skipTest('this database has no second currency to test with')
        second = self.env['res.company'].create({
            'name': 'Pay Test Co Two', 'currency_id': other.id})
        self.env.user.company_ids = [(4, second.id)]
        self._person('Pay Foreign', 8000.0, company=second)
        self.Position.recompute_all([self.company.id, second.id])

        board = self.Fair.get_board('group', 0, False)
        money = board['money']
        if money.get('one_currency'):
            self.skipTest('the reader can only see one currency')
        self.assertFalse(money['converted'])
        self.assertTrue(money['rate_note'])
        self.assertTrue(money['left_out'])

        # With rates on both sides, the group answer converts and says so.
        today = date.today().replace(day=1)
        for currency in (other, self.currency):
            self.env['res.currency.rate'].create({
                'currency_id': currency.id, 'name': today,
                'rate': 1.0 if currency == self.currency else 0.00005,
                'company_id': self.company.id})
        board = self.Fair.get_board('group', 0, True)
        self.assertTrue(board['money']['rate_note'])

    # ================================================================== T9
    def test_t09_the_old_pay_grades_become_bands(self):
        if 'wfp.pay.grade' not in self.env:
            self.skipTest('the old planning module is not installed here')
        grade = self.env['wfp.pay.grade'].create({
            'name': 'Legacy G9', 'code': 'PAYTESTG9', 'grade_level': 9,
            'company_id': self.company.id, 'country_code': 'VN',
            'range_min': 111.0, 'range_mid': 222.0, 'range_max': 333.0})
        report = self.Band.migrate_legacy()
        self.assertGreaterEqual(report['bands'], 1)
        band = self.Band.search([('note', 'like', 'wfp.pay.grade:%s;'
                                 % grade.id)], limit=1)
        self.assertTrue(band, 'the grade did not become a band')
        self.assertAlmostEqual(band.mid_amount, 222.0, places=2)
        self.assertEqual(band.family_id.name, 'Migrated')

        # Idempotent: a second run makes nothing new.
        again = self.Band.migrate_legacy()
        self.assertEqual(again['bands'], 0)
        self.assertGreaterEqual(again['skipped'], 1)

    def test_t09_the_legacy_module_is_byte_identical(self):
        """The owner's standing ruling: nothing in the old module is touched.

        Only meaningful in OUR repository. On the live server the addons
        directory sits inside the platform's own git clone, which has never
        tracked a Payobook module, so `git status` there reports every file of
        every module as untracked and the check would fail for a reason that
        has nothing to do with this rule. `ls-files` is the honest probe: no
        tracked files means this is not the repository the ruling is about.
        """
        tracked = subprocess.run(
            ['git', '-C', ROOT, 'ls-files', '--', 'pb_hr_workforce_planning'],
            capture_output=True, text=True, timeout=30)
        if not tracked.stdout.strip():
            self.skipTest('not the source repository')
        out = subprocess.run(
            ['git', '-C', ROOT, 'status', '--porcelain', '--',
             'pb_hr_workforce_planning'],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(out.stdout.strip(), '',
                         'the old planning module must be untouched, and git '
                         'says otherwise:\n%s' % out.stdout)

    # ================================================================= T10
    def test_t10_the_contract_carries_the_band_and_the_position(self):
        person = self._person('Pay Contract Read', 2500.0)
        self.Position.recompute_all([self.company.id])
        contract = person.contract_ids[:1]
        self.assertEqual(contract.pb_band_id, self.band)
        self.assertAlmostEqual(contract.pb_position_pct, 75.0, places=2)
        self.assertEqual(contract.pb_band_state, 'in')

    def test_t10_the_contract_screens_name_the_old_fields_nowhere(self):
        base = os.path.join(ROOT, 'pb_contracts')
        offenders = []
        for folder, _dirs, files in os.walk(base):
            if '__pycache__' in folder:
                continue
            for name in files:
                if not name.endswith(('.py', '.js', '.xml')):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding='utf-8') as handle:
                    body = handle.read()
                body = re.sub(r'#[^\n]*', '', body)
                body = re.sub(r'//[^\n]*', '', body)
                body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
                body = re.sub(r'"""(?:.|\n)*?"""', '', body)
                for word in ('wfp.pay.grade', 'grade_id', 'compa_ratio'):
                    if word in body:
                        offenders.append('%s: %s' % (name, word))
        self.assertFalse(offenders,
                         'the contract screens still name the old pay grade '
                         'fields: %s' % offenders)

    def test_t10_the_drawer_prints_the_position_as_a_sentence(self):
        person = self._person('Pay Sentence', 2500.0)
        self.Position.recompute_all([self.company.id])
        contract = person.contract_ids[:1]
        terms = self.env['pb.contracts']._cd_terms(
            contract, '$', False, True)
        money = next(group for group in terms if group['key'] == 'money')
        entry = next(f for f in money['fields']
                     if f['name'] == 'pb_position_pct')
        self.assertIn('way through the band', entry['display'])

    # ============================================================ the board
    def test_the_board_answers_and_the_empty_state_proposes(self):
        self._person('Pay Board One', 2000.0)
        self._person('Pay Board Two', 2400.0)
        self.Position.recompute_all([self.company.id])
        board = self.Bands.get_board([self.company.id])
        self.assertTrue(board['allowed'])
        self.assertTrue(board['lanes'])
        self.assertTrue(board['health'])
        lane = board['lanes'][0]
        self.assertTrue(lane['axis']['ticks'])
        band = next(b for b in lane['bands'] if b['id'] == self.band.id)
        self.assertGreaterEqual(band['people'], 2)
        self.assertTrue(band['dots'])

        suggestion = self.Bands.suggest_bands([self.company.id])
        self.assertTrue(suggestion['lanes'],
                        'the empty state has nothing to propose')
        families = self.Bands.suggest_families([self.company.id])
        self.assertTrue(families)

    # ====================================== TIDY P2 — every person is drawn
    def test_tidy_t1_every_person_is_in_the_payload_and_nobody_is_dropped(self):
        """TIDY rule 12, at the seam where it can be proven.

        The picture is drawn from `wages`, and `wages` is EVERY person on the
        band — so the count and the list agree, always. `dots` is the named
        form and is sent only while a band is small enough to draw one mark
        per name; above that the browser draws columns and asks for names one
        bin at a time. And the words "not drawn" appear nowhere at all, in any
        band, any label or any chip.
        """
        for index in range(30):
            self._person('Tidy Crowd %s' % index, 1500.0 + (index * 25))
        self.Position.recompute_all([self.company.id])
        board = self.Bands.get_board([self.company.id])
        bands = [b for lane in board['lanes'] for b in lane['bands']]
        self.assertTrue(bands)
        big = next(b for b in bands if b['id'] == self.band.id)
        self.assertGreaterEqual(big['people'], 30)

        for band in bands:
            self.assertEqual(
                len(band['wages']), band['people'],
                'a band drew %s of %s people' % (len(band['wages']),
                                                 band['people']))
            self.assertEqual(band['wages'], sorted(band['wages']),
                             'the wages are handed over out of order')
            self.assertTrue(all(isinstance(w, int) for w in band['wages']),
                            'a wage came over as something other than a whole '
                            'number')
            self.assertNotIn('more', band,
                             'a band still counts people it did not draw')
            self.assertNotIn('more_label', band)
            self.assertTrue(band['people_scope'],
                            'a band cannot find its own people again')
            if band['people'] <= 24:
                self.assertEqual(len(band['dots']), band['people'])
            else:
                self.assertEqual(band['dots'], [],
                                 'a big band still ships every name')

        self.assertNotIn('not drawn', str(board).lower())
        proposal = self.Bands.suggest_bands([self.company.id])
        for band in [b for lane in proposal['lanes'] for b in lane['bands']]:
            self.assertEqual(len(band['wages']), band['people'])
            self.assertNotIn('more', band)
            self.assertTrue(band['people_scope'])
        self.assertNotIn('not drawn', str(proposal).lower())

    def test_tidy_t2_people_between_names_exactly_the_people_in_that_slice(self):
        """The other half of rule 12: a column that says how many can be
        asked who, and it answers about those people and nobody else."""
        # 800 is under the band's floor of 1,000 and 3,600 is over its
        # ceiling of 3,000, so all three standings are on the fixture.
        wages = [800.0, 1600.0, 1650.0, 1700.0, 2500.0, 3600.0]
        for index, wage in enumerate(wages):
            self._person('Tidy Slice %s' % index, wage)
        self.Position.recompute_all([self.company.id])
        scope = {'band_id': self.band.id}

        answer = self.Bands.people_between(scope, 1600.0, 1700.0)
        self.assertTrue(answer['allowed'])
        self.assertEqual(answer['total'], 3)
        self.assertEqual(len(answer['rows']), 3)
        self.assertEqual([r['wage'] for r in answer['rows']],
                         [1600.0, 1650.0, 1700.0])
        self.assertTrue(all(r['state'] == 'in' for r in answer['rows']))
        self.assertTrue(answer['title'])

        low = self.Bands.people_between(scope, 0.0, 900.0)
        self.assertEqual([r['state'] for r in low.get('rows', [])
                          if r['name'].startswith('Tidy Slice')], ['below'])
        high = self.Bands.people_between(scope, 3000.0, 4000.0)
        self.assertEqual([r['state'] for r in high.get('rows', [])
                          if r['name'].startswith('Tidy Slice')], ['above'])

        # The cap is the cap, and the total still tells the truth.
        for index in range(25):
            self._person('Tidy Cap %s' % index, 1660.0)
        self.Position.recompute_all([self.company.id])
        capped = self.Bands.people_between(scope, 1600.0, 1700.0, limit=200)
        self.assertGreaterEqual(capped['total'], 28)
        self.assertLessEqual(len(capped['rows']), 20)
        self.assertEqual(capped['more'], capped['total'] - len(capped['rows']))
        self.assertIn(str(capped['more']), capped['more_label'])

        # Somebody else's company is never in the answer, and a reader with
        # no role is told nothing at all.
        other = self.env['res.company'].create({
            'name': 'Tidy Other Co', 'currency_id': self.currency.id})
        outsider = self._person('Tidy Outsider', 1660.0, company=other)
        self.Position.recompute_all([self.company.id, other.id])
        again = self.Bands.people_between(scope, 1600.0, 1700.0, limit=20)
        self.assertNotIn(outsider.name, [r['name'] for r in again['rows']])

        nobody = self.env['res.users'].create({
            'name': 'Tidy Nobody', 'login': 'tidy.nobody.test',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        refused = self.Bands.with_user(nobody).people_between(
            scope, 0.0, 9999999.0)
        self.assertFalse(refused['allowed'])
        self.assertEqual(refused['rows'], [])
        self.assertEqual(refused['total'], 0)

    def test_tidy_t3_the_picture_arithmetic_passes_its_own_check(self):
        """`binPeople` and `dodgeDots` decide where every person is drawn, so
        they are checked under node with no browser anywhere near them."""
        script = os.path.join(HERE, 'tools', 'band_picture_check.mjs')
        self.assertTrue(os.path.exists(script))
        try:
            done = subprocess.run(['node', script], capture_output=True,
                                  text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            self.skipTest('node is not available on this machine')
        self.assertEqual(done.returncode, 0,
                         'the band picture check failed:\n%s%s'
                         % (done.stdout, done.stderr))

    def test_a_reader_with_no_role_gets_an_explained_empty_board(self):
        nobody = self.env['res.users'].create({
            'name': 'Pay Nobody', 'login': 'pay.nobody.test',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        board = self.Bands.with_user(nobody).get_board([self.company.id])
        self.assertFalse(board['allowed'])
        self.assertEqual(board['lanes'], [])
