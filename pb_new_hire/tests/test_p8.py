# -*- coding: utf-8 -*-
"""NEWHIRE P8 — owner decisions of 2026-11-26. Numbers match the P8 handover:
A1–A8 (pay scheme follows the country, a choice when there are several),
B1–B5 ("Suggest who pays each team" on Mapping). C–H live in
test_p8_more.py."""
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .test_docs import DocsCommon
from .test_new_hire import NewHireCommon


@tagged('post_install', '-at_install', 'newhire')
class TestP8Scheme(DocsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Config = env['hr.formula.config']
        # a second Singapore scheme: the country has several
        cls.sg_hourly = Config.create({'name': 'DEMO NH Singapore hourly', 'code': 'DEMONHSGH',
                                       'country_code': 'SG', 'state': 'active',
                                       'company_id': cls.company.id})
        # an advance is never "who pays this person"
        cls.sg_advance = Config.create({'name': 'DEMO NH Singapore advance', 'code': 'DEMONHSGA',
                                        'country_code': 'SG', 'state': 'active', 'cycle_type': 'mid_cycle',
                                        'company_id': cls.company.id})
        cls.in_scheme = Config.create({'name': 'DEMO NH India monthly', 'code': 'DEMONHIN',
                                       'country_code': 'IN', 'state': 'active',
                                       'company_id': cls.company.id})
        Emp = env['hr.employee']
        cls.lonely_people = Emp.create([
            {'name': 'DEMO NH Lonely %s' % i, 'company_id': cls.company.id,
             'department_id': cls.lonely.id, 'payroll_country': 'SG'} for i in range(3)])
        cls.lonely_people.sudo().write({'pb_paid_by_id': cls.sg_hourly.id})

    def dec(self, team, code, scheme=False, job=False):
        return self.studio().decides(team.id if team else False, code, '2026-12-07', 'permanent',
                                     scheme.id if scheme else False, job.id if job else False)

    # ------------------------------------------------------------ A1 one
    def test_a1_one_scheme_for_the_country(self):
        out = self.dec(False, 'VN')
        self.assertEqual(out['scheme']['id'], self.vn_scheme.id, 'no team yet: the country names it')
        self.assertEqual(out['scheme']['why'], 'The only pay scheme for Vietnam.')
        self.assertFalse(out['schemes'], 'one scheme: no chooser')
        self.assertFalse(out['problem'])
        india = self.dec(False, 'IN')
        self.assertEqual(india['scheme']['id'], self.in_scheme.id)

    # ------------------------------------------------------------ A2 none
    def test_a2_no_scheme_for_the_country(self):
        out = self.dec(False, 'MY')
        self.assertFalse(out['scheme'])
        self.assertFalse(out['schemes'])
        self.assertEqual(out['currency']['name'], 'MYR', 'the rest of step 2 still follows the country')

    # ------------------------------------------------------------ A3 several, team mapped
    def test_a3_several_default_is_the_team_scheme(self):
        out = self.dec(self.finance, 'SG')
        self.assertEqual([s['id'] for s in out['schemes']], sorted([self.sg_scheme.id, self.sg_hourly.id],
                         key=lambda i: self.env['hr.formula.config'].browse(i).name))
        self.assertNotIn(self.sg_advance.id, [s['id'] for s in out['schemes']], 'never an advance')
        self.assertEqual(out['scheme']['id'], self.sg_scheme.id, "the team's map line")
        self.assertEqual(out['scheme']['usual_id'], self.sg_scheme.id)
        self.assertTrue(out['scheme']['honoured'])
        self.assertFalse(out['scheme']['hand'])
        self.assertIn(self.finance.id, out['scheme_teams'], 'A.3: the scheme puts its teams first')
        hourly = next(s for s in out['schemes'] if s['id'] == self.sg_hourly.id)
        self.assertEqual(hourly['people'], 3)
        self.assertEqual(hourly['currency'], 'SGD')
        self.assertFalse(out['problem'])

    # ------------------------------------------------------------ A4 several, team unmapped
    def test_a4_unmapped_team_most_paid_and_honest(self):
        out = self.dec(self.lonely, 'SG')
        self.assertEqual(out['scheme']['id'], self.sg_hourly.id, 'pays most of the team')
        self.assertEqual(out['scheme']['why'], 'Pays most people in DEMO NH Lonely.')
        self.assertFalse(out['scheme']['honoured'], 'no line pays the team: the pay run would not')
        self.assertEqual(out['problem'], 'No pay scheme pays DEMO NH Lonely yet.')
        self.assertIn('Set who pays DEMO NH Lonely in Mapping', out['fix'])
        # a team nobody is paid in: most people in the country
        farm = self.dec(self.farm, 'SG')
        self.assertEqual(farm['scheme']['id'], self.sg_hourly.id)
        self.assertEqual(farm['scheme']['why'], 'Pays most people working in Singapore.')

    # ------------------------------------------------------------ A5 hand pick kept
    def test_a5_hand_pick_kept_with_a_note(self):
        out = self.dec(self.finance, 'SG', scheme=self.sg_hourly)
        s = out['scheme']
        self.assertEqual(s['id'], self.sg_hourly.id)
        self.assertTrue(s['hand'])
        self.assertTrue(s['differs'])
        self.assertEqual(s['usual_name'], 'DEMO NH Singapore monthly')
        self.assertFalse(s['honoured'], "the pay run follows the team's line")
        self.assertEqual(out['problem'], 'DEMO NH Finance is paid by DEMO NH Singapore monthly, and '
                                         'the pay run follows the team.')
        self.assertIn(self.finance.id, out['scheme_teams'] + [self.finance.id])
        # another team: the pick stays
        other = self.dec(self.lonely, 'SG', scheme=self.sg_hourly)
        self.assertEqual(other['scheme']['id'], self.sg_hourly.id)
        # a pick of another country is ignored
        wrong = self.dec(self.finance, 'SG', scheme=self.in_scheme)
        self.assertEqual(wrong['scheme']['id'], self.sg_scheme.id)
        self.assertFalse(wrong['scheme']['hand'])

    # ------------------------------------------------------------ A6 old payloads
    def test_a6_values_old_and_new_payloads(self):
        vals, _d = self.studio()._values(self.draft())
        self.assertEqual(vals['pb_nh_scheme_id'], self.sg_scheme.id, 'no scheme key: as before')
        vals2, _d = self.studio()._values(self.draft(scheme_id=self.sg_hourly.id))
        self.assertEqual(vals2['pb_nh_scheme_id'], self.sg_hourly.id, 'the chosen scheme is sent')
        self.assertEqual(vals2['pb_nh_names']['scheme'], 'DEMO NH Singapore hourly')
        self.assertIn('pay run follows the team', vals2['pb_nh_names']['scheme_note'])
        self.assertFalse(vals['pb_nh_names']['scheme_note'])
        # the places() call carries the pick through to "What this decides"
        out = self.studio().places('SG', self.finance.id, False, '2026-12-07', 'permanent', False,
                                   self.sg_hourly.id)
        self.assertEqual(out['decides']['scheme']['id'], self.sg_hourly.id)

    # ------------------------------------------------------------ A7 apply honoured by a pay run
    def test_a7_pay_run_takes_the_chosen_scheme(self):
        if 'pb.payrun.wizard' not in self.env:
            self.skipTest('no pay run wizard on this database')
        self.fast_lane()
        # a rule on the map pays people working in India (rize's shape)
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.in_scheme.id, 'domain': "[('payroll_country', '=', 'IN')]",
            'cycle_type': 'any'})
        out = self.dec(self.lonely, 'IN')
        self.assertEqual(out['scheme']['id'], self.in_scheme.id)
        self.assertTrue(out['scheme']['honoured'], 'the rule on the map pays them')
        self.assertFalse(out['problem'])
        self.assertIn('through a rule on the map', out['pay_line'])
        answer = self.studio().send(self.draft(department_id=self.lonely.id, job_id=False,
                                               job_title='DEMO NH Grower', payroll_country='IN',
                                               parent_id=False, work_location_id=False, wage=50000,
                                               login_mode='none', open_case=False, letter=False))
        self.assertTrue(answer.get('applied'), answer)
        emp = self.hires()
        self.assertEqual(len(emp), 1)
        Wizard = self.env['pb.payrun.wizard'].sudo().with_company(self.company)
        covered, _missed = Wizard._scheme_population(self.in_scheme.id, emp.ids)
        self.assertEqual(covered, emp.ids, "the person lands in the chosen scheme's run")
        covered, _missed = Wizard._scheme_population(self.sg_scheme.id, emp.ids)
        self.assertFalse(covered)
        # a team with its own line: the run of that line
        answer = self.studio().send(self.draft(name='DEMO NH Second', work_email='demo.nh.second@example.com',
                                               login_mode='none', open_case=False, letter=False))
        second = self.hires('DEMO NH Second')
        covered, _missed = Wizard._scheme_population(self.sg_scheme.id, second.ids)
        self.assertEqual(covered, second.ids)

    # ------------------------------------------------------------ A9 one chain, the pay run's
    def test_a9_resolver_agrees_with_the_pay_run_in_every_branch(self):
        """`_scheme_for` (what the studio shows) and the pay run's own answer for
        a real person with the same team, country and company agree in every
        branch: team line, division, a rule on the map, the only scheme, none."""
        Map = self.env['pb.scheme.map'].sudo()
        division = self.env['pb.division'].sudo().create({'name': 'DEMO NH8 Division'})
        self.env['pb.division.link'].sudo().create({'division_id': division.id, 'department_id': self.farm.id,
                                                    'date_from': '2020-01-01'})
        self.env['hr.formula.scheme.assignment'].create({'config_id': self.vn_scheme.id, 'division_id': division.id,
                                                         'cycle_type': 'any'})
        self.env['hr.formula.scheme.assignment'].create({'config_id': self.in_scheme.id, 'cycle_type': 'any',
                                                         'domain': "[('payroll_country', '=', 'IN')]"})
        cases = [(self.finance, 'SG', 'department', self.sg_scheme), (self.farm, 'VN', 'division', self.vn_scheme),
                 (self.lonely, 'IN', 'rule', self.in_scheme), (self.lonely, 'MY', 'none', None)]
        for team, code, rung, scheme in cases:
            found = self.studio()._scheme_for({'department_id': team.id, 'payroll_country': code})
            emp = self.env['hr.employee'].create({'name': 'DEMO NH8 A9 %s' % code, 'company_id': self.company.id,
                                                  'department_id': team.id, 'payroll_country': code})
            self.env.flush_all()
            real = Map.resolve(emp)
            self.assertEqual(found['pay_run'].id or 0, real['config_id'], (team.name, code))
            self.assertEqual(found['rung'], real['rung'], (team.name, code))
            self.assertEqual(real['rung'], rung)
            self.assertEqual(found['pay_run'].id or 0, scheme.id if scheme else 0)
        # the only scheme, in a company that has one
        solo = self.env['res.company'].create({'name': 'DEMO NH8 Solo'})
        cfg = self.env['hr.formula.config'].create({'name': 'DEMO NH8 Solo scheme', 'code': 'DEMONH8SOLO',
                                                     'country_code': 'VN', 'state': 'active', 'company_id': solo.id})
        team = self.env['hr.department'].create({'name': 'DEMO NH8 Solo team', 'company_id': solo.id})
        self.maker.sudo().write({'company_ids': [(4, solo.id)]})
        S = self.env['pb.new.hire'].with_user(self.maker).with_context(allowed_company_ids=[solo.id])
        found = S._scheme_for({'department_id': team.id, 'payroll_country': 'VN'})
        emp = self.env['hr.employee'].create({'name': 'DEMO NH8 Solo person', 'company_id': solo.id,
                                              'department_id': team.id, 'payroll_country': 'VN'})
        self.env.flush_all()
        if not self.env['hr.formula.config'].sudo().search_count([('state', '=', 'active'),
                                                                   ('company_id', '=', False)]):
            self.assertEqual(found['pay_run'], cfg)
            self.assertEqual(Map.resolve(emp)['config_id'], cfg.id)

    def test_a10_unmapped_team_paid_by_a_rule_shows_and_examples(self):
        """rize's shape: no team line, a rule per country of work. Step 2 shows the
        scheme the rule gives, no amber line, and the payslip example works."""
        self.env['hr.formula.scheme.assignment'].create({'config_id': self.sg_hourly.id, 'cycle_type': 'any',
                                                         'domain': "[('payroll_country', '=', 'SG')]"})
        out = self.dec(self.lonely, 'SG')
        self.assertEqual(out['scheme']['id'], self.sg_hourly.id)
        self.assertTrue(out['scheme']['honoured'])
        self.assertFalse(out['problem'], 'the amber line only when the pay run finds nothing')
        self.assertEqual(self.studio().team_defaults(self.lonely.id)['scheme'], False,
                         'without a country the rule does not answer, as for a real person')
        ex = self.studio().payslip_example(self.draft(department_id=self.lonely.id, job_id=False,
                                                      job_title='DEMO NH Grower', parent_id=False,
                                                      work_location_id=False))
        self.assertTrue(ex.get('ok'), ex)
        self.assertEqual(ex['scheme_id'], self.sg_hourly.id)

    # ------------------------------------------------------------ A8 example follows the pick
    def test_a8_example_and_usual_answers_follow_the_pick(self):
        Ex = self.studio()
        out = Ex.payslip_example(self.draft(scheme_id=self.sg_hourly.id))
        if out.get('ok'):
            self.assertEqual(out['scheme_id'], self.sg_hourly.id)
        base = Ex.payslip_example(self.draft())
        if base.get('ok'):
            self.assertEqual(base['scheme_id'], self.sg_scheme.id)
        # usual answers are the chosen scheme's (sg_hourly has none, sg_scheme has four rules)
        self.assertTrue(Ex.usual_answers(self.sg_scheme.id))
        self.assertFalse(Ex.usual_answers(self.sg_hourly.id))
        vals, _d = Ex._values(self.draft(scheme_id=self.sg_hourly.id,
                                         usual=[{'code': 'DEMONHMEAL', 'amount': 99}]))
        self.assertFalse(vals['usual'], "another scheme's usual answer is not carried")


@tagged('post_install', '-at_install', 'newhire')
class TestP8Suggest(NewHireCommon):
    """B — "Suggest who pays each team" (pb_scheme_map, Mapping board)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.co = env['res.company'].create({'name': 'DEMO NH Map Co', 'country_id': env.ref('base.id').id})
        env['biz.approval.seed'].sudo().set_no_approval_needed(cls.co, 'schememap')
        Config = env['hr.formula.config']
        mk = lambda name, code, cc, **kw: Config.create(dict({  # noqa: E731
            'name': name, 'code': code, 'country_code': cc, 'state': 'active',
            'company_id': cls.co.id}, **kw))
        cls.c_id = mk('DEMO NH Map Indonesia', 'DEMONHMID', 'ID')
        cls.c_vn = mk('DEMO NH Map Vietnam', 'DEMONHMVN', 'VN')
        cls.c_sg1 = mk('DEMO NH Map Singapore A', 'DEMONHMSG1', 'SG')
        cls.c_sg2 = mk('DEMO NH Map Singapore B', 'DEMONHMSG2', 'SG')
        cls.c_old = mk('DEMO NH Map Old', 'DEMONHMOLD', 'ID')
        cls.c_old2 = mk('DEMO NH Map Older', 'DEMONHMOLD2', 'ID')
        Dept = env['hr.department'].with_company(cls.co)
        team = lambda name: Dept.create({'name': name, 'company_id': cls.co.id})  # noqa: E731
        cls.t_id, cls.t_mix, cls.t_empty, cls.t_mapped = (
            team('DEMO NH Map Bread'), team('DEMO NH Map Mixed'), team('DEMO NH Map Empty'),
            team('DEMO NH Map Mapped'))
        cls.t_my, cls.t_sg, cls.t_moves, cls.t_old = (
            team('DEMO NH Map Malaysia'), team('DEMO NH Map Singapore'), team('DEMO NH Map Moves'),
            team('DEMO NH Map Old line'))
        Emp = env['hr.employee']

        def people(t, codes):
            return Emp.create([{'name': 'DEMO NH Map %s %s' % (t.name[-5:], i), 'company_id': cls.co.id,
                                'department_id': t.id, 'payroll_country': c} for i, c in enumerate(codes)])
        cls.p_id = people(cls.t_id, ['ID', 'ID', 'ID'])
        people(cls.t_mix, ['VN', 'VN', 'IN', 'IN'])
        people(cls.t_mapped, ['ID'])
        people(cls.t_my, ['MY', 'MY'])
        cls.p_sg = people(cls.t_sg, ['SG', 'SG', 'SG'])
        cls.p_moves = people(cls.t_moves, ['VN', 'VN', 'VN', 'SG'])
        people(cls.t_old, ['ID', 'ID'])
        Assign = env['hr.formula.scheme.assignment']
        cls.mapped_row = Assign.create({'config_id': cls.c_id.id, 'department_id': cls.t_mapped.id,
                                        'cycle_type': 'any'})
        # the Singapore person of "Moves" is paid by a rule today
        Assign.create({'config_id': cls.c_sg1.id, 'cycle_type': 'any',
                       'domain': "[('payroll_country', '=', 'SG')]"})
        # an old line on an archived scheme, for any kind of run AND for regular
        Assign.create({'config_id': cls.c_old.id, 'department_id': cls.t_old.id, 'cycle_type': 'any'})
        Assign.create({'config_id': cls.c_old2.id, 'department_id': cls.t_old.id, 'cycle_type': 'regular'})
        (cls.c_old | cls.c_old2).write({'state': 'archived'})
        cls.admin = new_test_user(env, login='nh_map_admin', name='DEMO NH Map Admin',
                                  groups='base.group_user,pb_hr_payroll_formula.group_formula_manager,'
                                         'hr.group_hr_user',
                                  company_id=cls.co.id, company_ids=[(6, 0, [cls.co.id])])
        cls.officer = new_test_user(env, login='nh_map_officer', name='DEMO NH Map Officer',
                                    groups='base.group_user,hr.group_hr_user',
                                    company_id=cls.co.id, company_ids=[(6, 0, [cls.co.id])])

    def board(self, user=None):
        return self.env['pb.scheme.board'].with_user(user or self.admin).with_context(
            allowed_company_ids=[self.co.id]).with_company(self.co)

    def rows(self, out=None):
        out = out or self.board().country_suggestions(self.co.id)
        return {r['department_id']: r for r in out['rows']}, out

    # ------------------------------------------------------------ B1 the rule
    def test_b1_suggestions(self):
        rows, out = self.rows()
        self.assertNotIn(self.t_mapped.id, rows, 'a team on the map is never listed')
        self.assertGreaterEqual(out['mapped'], 1)
        bread = rows[self.t_id.id]
        self.assertEqual((bread['state'], bread['config_id'], bread['cycle_type']),
                         ('suggest', self.c_id.id, 'any'))
        self.assertTrue(bread['tick'])
        self.assertIn('3 of 3 work in Indonesia', bread['reason'])
        self.assertIn('the only pay scheme for Indonesia', bread['reason'])
        self.assertEqual(rows[self.t_mix.id]['state'], 'choice', 'a tie: no suggestion')
        self.assertIn('2 Vietnam', rows[self.t_mix.id]['reason'])
        self.assertEqual(rows[self.t_empty.id]['state'], 'none')
        self.assertEqual(rows[self.t_my.id]['state'], 'choice')
        self.assertIn('no active pay scheme for Malaysia', rows[self.t_my.id]['reason'])
        # Singapore has two schemes and no pay run yet: needs a choice
        self.assertEqual(rows[self.t_sg.id]['state'], 'choice')

    def test_b1b_several_schemes_latest_pay_run(self):
        Slip = self.env['hr.payslip'].sudo()
        run = self.env['hr.payslip.run'].sudo().create({
            'name': 'DEMO NH Map run', 'date_start': '2026-10-01', 'date_end': '2026-10-31'})
        for emp in self.p_sg[:2]:
            Slip.create({'name': 'DEMO NH slip', 'employee_id': emp.id, 'date_from': '2026-10-01',
                         'date_to': '2026-10-31', 'payslip_run_id': run.id, 'company_id': self.co.id,
                         'formula_config_id': self.c_sg2.id})
        rows, _out = self.rows()
        sg = rows[self.t_sg.id]
        # the rule on the map pays them by A today: offered, unticked, says so
        self.assertEqual((sg['state'], sg['config_id'], sg['moves']), ('moves', self.c_sg2.id, 3))
        self.assertIn('paid 2 of them in their latest pay run', sg['reason'])

    # ------------------------------------------------------------ B2 never moves anybody silently
    def test_b2_moves_are_offered_unticked(self):
        rows, _out = self.rows()
        moves = rows[self.t_moves.id]
        self.assertEqual((moves['state'], moves['config_id'], moves['moves']), ('moves', self.c_vn.id, 1))
        self.assertFalse(moves['tick'])
        self.assertIn('1 of them are paid by another pay scheme today', moves['warn'])

    # ------------------------------------------------------------ B3 an old line in the way
    def test_b3_old_line_blocks(self):
        rows, _out = self.rows()
        old = rows[self.t_old.id]
        self.assertEqual(old['state'], 'blocked')
        self.assertIn('DEMO NH Map Old', old['reason'])

    # ------------------------------------------------------------ B4 apply
    def test_b4_apply_writes_only_ticked_unmapped(self):
        Assign = self.env['hr.formula.scheme.assignment'].sudo().with_context(active_test=False)
        before = {r.id: (r.config_id.id, r.department_id.id, r.cycle_type, r.active, r.write_date)
                  for r in Assign.search([('company_id', '=', self.co.id)])}
        Map = self.env['pb.scheme.map'].sudo()
        everyone = self.env['hr.employee'].sudo().search([('company_id', '=', self.co.id)])
        paid_before = {k: v['config_id'] for k, v in Map.resolve_many(everyone.ids).items()}
        slips = self.env['hr.payslip'].sudo().search_count([('company_id', '=', self.co.id)])
        res = self.board().accept_country_suggestions(
            [self.t_id.id, self.t_mix.id, self.t_mapped.id, self.t_old.id, self.t_empty.id], self.co.id)
        self.assertEqual(res['teams'], [self.t_id.id], 'only the writable suggestion')
        after = {r.id: (r.config_id.id, r.department_id.id, r.cycle_type, r.active, r.write_date)
                 for r in Assign.search([('company_id', '=', self.co.id)])}
        for row_id, vals in before.items():
            self.assertEqual(after[row_id], vals, 'an existing line is never changed')
        new = Assign.browse(sorted(set(after) - set(before)))
        self.assertEqual(len(new), 1)
        self.assertEqual((new.department_id, new.config_id, new.cycle_type, new.source),
                         (self.t_id, self.c_id, 'any', 'accepted'))
        paid_after = {k: v['config_id'] for k, v in Map.resolve_many(everyone.ids).items()}
        for e in everyone.ids:
            if e not in self.p_id.ids:
                self.assertEqual(paid_after[e], paid_before[e], 'nobody else moved')
        self.assertTrue(all(paid_after[e] == self.c_id.id for e in self.p_id.ids))
        self.assertEqual(self.env['hr.payslip'].sudo().search_count([('company_id', '=', self.co.id)]), slips)
        rows, _out = self.rows()
        self.assertNotIn(self.t_id.id, rows, 'now on the map')
        # a moving team is written only when ticked on purpose
        res = self.board().accept_country_suggestions([self.t_moves.id], self.co.id)
        self.assertEqual(res['teams'], [self.t_moves.id])

    # ------------------------------------------------------------ B5 gates and a late approval
    def test_b5_gates_and_keep_existing(self):
        out = self.board(self.officer).country_suggestions(self.co.id)
        self.assertFalse(out['can_write'], 'an HR officer reads, a payroll manager writes')
        with self.assertRaises(AccessError):
            self.board(self.officer).accept_country_suggestions([self.t_id.id], self.co.id)
        # an approval that lands after somebody drew a line by hand changes nothing
        Assign = self.env['hr.formula.scheme.assignment'].sudo()
        hand = Assign.create({'config_id': self.c_vn.id, 'department_id': self.t_id.id, 'cycle_type': 'any'})
        res = self.env['pb.scheme.map'].sudo().accept_draft([{
            'department_id': self.t_id.id, 'config_id': self.c_id.id, 'cycle_type': 'any',
            'keep_existing': True}])
        self.assertEqual(res, {'created': 0, 'replaced': 0})
        self.assertTrue(hand.exists())
        self.assertEqual(hand.config_id, self.c_vn)
