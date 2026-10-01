# -*- coding: utf-8 -*-
"""RECRUIT P1 — Rize's stage set, presets, Hiring set-up, the Talent lead.

Numbered as in `docs/handovers/recruit/RECRUIT_P1_BOARD.md` §5 (tests 1–4 and
12–15). Test names in the RIZE programme style: they say the rule.
"""

import importlib.util

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from odoo.addons.pb_hiring.models.journey import (
    MEANINGS, STAGE_ROWS, STOCK_STAGE_MAP,
)
from .test_hiring import HiringCase


@tagged('post_install', '-at_install', 'recruit_p1')
class TestRecruitStages(HiringCase):

    def _stages(self):
        return self.env['hr.recruitment.stage'].sudo().search(
            [], order='sequence, id')

    # ------------------------------------------------------------- test 1
    def test_01_the_seed_makes_the_17_stages_and_no_stock_one_remains(self):
        Stage = self.env['hr.recruitment.stage']
        by_key = {s.pb_key: s for s in self._stages() if s.pb_key}
        self.assertEqual(set(by_key), {k for k, *_ in STAGE_ROWS})
        for key, name, seq, family in STAGE_ROWS:
            row = by_key[key].with_context(lang='en_US')
            self.assertEqual(row.name, name)
            self.assertEqual(row.sequence, seq)
            self.assertEqual(row.pb_family, family)
            self.assertTrue(row.pb_meaning, 'no meaning on %s' % key)
        self.assertEqual(by_key['phone'].with_context(lang='en_US').name,
                         'Recruiter review')
        self.assertFalse(self._stages().filtered(lambda s: not s.pb_key),
                         'a stage with no key is still on this database')
        for xmlid, _key in STOCK_STAGE_MAP:
            self.assertFalse(self.env.ref(xmlid, raise_if_not_found=False))
        self.assertTrue(Stage._pb_stage('joined').hired_stage)
        self.assertTrue(Stage._pb_stage('cv_reject').fold)

    # ------------------------------------------------------------- test 2
    def test_02_the_seed_is_idempotent_and_a_client_rename_survives(self):
        Stage = self.env['hr.recruitment.stage']
        before = [(s.id, s.name, s.sequence, s.pb_meaning) for s in self._stages()]
        Stage._ensure_journey_stages()
        after = [(s.id, s.name, s.sequence, s.pb_meaning) for s in self._stages()]
        self.assertEqual(before, after)

        shortlist = Stage._pb_stage('shortlist').with_context(lang='en_US')
        shortlist.write({'name': 'Worth a chat', 'sequence': 999})
        Stage._ensure_journey_stages()
        self.assertEqual(shortlist.name, 'Worth a chat',
                         'an upgrade put the product word back over the client\'s')
        self.assertEqual(shortlist.sequence, 999,
                         'an upgrade undid the client\'s order')

        # a row still carrying the WAVE-2 word is renamed
        screening = Stage._pb_stage('screening').with_context(lang='en_US')
        screening.write({'name': 'Screening'})
        Stage._ensure_journey_stages()
        self.assertEqual(screening.name, 'Applications received')

    # ------------------------------------------------------------- test 3
    def test_03_a_stock_stage_is_retired_silently_with_its_people_moved(self):
        Stage = self.env['hr.recruitment.stage'].sudo()
        template = self.env.ref(
            'hr_recruitment.email_template_data_applicant_congratulations',
            raise_if_not_found=False)
        stock = Stage.create({'name': 'Qualification', 'sequence': 1,
                              'template_id': template.id if template else False})
        self.env['ir.model.data'].sudo().create({
            'module': 'hr_recruitment', 'name': 'stage_job1',
            'model': 'hr.recruitment.stage', 'res_id': stock.id,
            'noupdate': True})
        job = self.env['hr.job'].sudo().create({'name': 'RECRUIT P1 retire role',
                                                'company_id': self.company.id})
        app = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P1 Stock Person', 'job_id': job.id,
            'email_from': 'recruit.p1.stock@example.com',
            'company_id': self.company.id})
        app.with_context(just_moved=True).write({'stage_id': stock.id})
        mails = self.env['mail.mail'].sudo().search([]).ids
        logs = self.env['pb.hiring.stage.log'].sudo().search_count(
            [('applicant_id', '=', app.id)])
        retired = Stage._retire_stock_stages()
        self.assertEqual(retired, 1)
        self.assertEqual(app.stage_id.pb_key, 'shortlist')
        self.assertFalse(stock.exists())
        self.assertFalse(self.env.ref('hr_recruitment.stage_job1',
                                      raise_if_not_found=False))
        new_mail = self.env['mail.mail'].sudo().search(
            [('id', 'not in', mails), ('model', '=', 'hr.applicant'),
             ('res_id', '=', app.id)])
        self.assertFalse(new_mail, 'retiring a stage emailed a candidate')
        self.assertEqual(self.env['pb.hiring.stage.log'].sudo().search_count(
            [('applicant_id', '=', app.id)]), logs,
            'a housekeeping move was written down as somebody\'s decision')
        self.assertEqual(Stage._retire_stock_stages(), 0, 'not idempotent')

    # ------------------------------------------------------------- test 4
    def test_04_a_new_role_takes_its_columns_from_the_best_preset(self):
        Stage = self.env['hr.recruitment.stage']
        Preset = self.env['pb.hiring.stage.preset'].sudo()
        vn = self.env.ref('base.vn')
        sg = self.env.ref('base.sg')
        other = self.env['hr.department'].create({
            'name': 'RECRUIT P1 Other Function', 'company_id': self.company.id,
            'manager_id': self.head.id})
        d3 = Stage._pb_stage('discussion_3')
        asg = Stage._pb_stage('assignment')
        ref = Stage._pb_stage('reference')
        Preset.create({'name': 'both', 'company_id': self.company.id,
                       'department_id': self.dept.id, 'country_id': vn.id,
                       'stage_ids': [(6, 0, d3.ids)]})
        Preset.create({'name': 'dept', 'company_id': self.company.id,
                       'department_id': self.dept.id,
                       'stage_ids': [(6, 0, asg.ids)]})
        Preset.create({'name': 'country', 'company_id': self.company.id,
                       'country_id': vn.id, 'stage_ids': [(6, 0, ref.ids)]})
        self.assertEqual(self._requisition(country_id=vn.id).pb_visible_stage_ids, d3)
        self.assertEqual(self._requisition(country_id=sg.id).pb_visible_stage_ids, asg)
        self.assertEqual(self._requisition(department_id=other.id,
                                           country_id=vn.id).pb_visible_stage_ids, ref)
        standard = Preset.search([('company_id', '=', self.company.id),
                                  ('is_standard', '=', True)])
        self.assertTrue(standard)
        plain = self._requisition(department_id=other.id, country_id=sg.id)
        self.assertEqual(plain.pb_visible_stage_ids, standard.stage_ids)
        self.assertNotIn(d3, plain.pb_visible_stage_ids,
                         'Discussion 3 is hidden by default')
        standard.write({'stage_ids': [(5, 0, 0)]})
        never_empty = self._requisition(department_id=other.id, country_id=sg.id)
        self.assertTrue(never_empty.pb_visible_stage_ids, 'a role was left with no columns')
        # always-on stages show whatever the role's own set says
        shown = never_empty._pb_board_stages().mapped('pb_key')
        for key in ('screening', 'shortlist', 'offer', 'post_offer', 'joined',
                    'cv_reject', 'on_hold'):
            self.assertIn(key, shown)

    # ------------------------------------------------------------ test 12
    def _user(self, login, *groups):
        return self.env['res.users'].sudo().create({
            'name': 'RECRUIT P1 %s' % login, 'login': 'recruit.p1.%s' % login,
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref(g).id) for g in ('base.group_user',) + groups]})

    def test_12_presets_save_and_delete_and_only_the_talent_lead_may(self):
        facade = self.env['pb.hiring']
        vn = self.env.ref('base.vn')
        asg = self.env['hr.recruitment.stage']._pb_stage('assignment')
        res = facade.act('preset_save', {'department_id': self.dept.id,
                                         'country_id': vn.id,
                                         'stage_ids': asg.ids})
        setup = facade.get_setup()
        row = [p for p in setup['presets'] if p['id'] == res['id']][0]
        self.assertEqual(row['stage_ids'], asg.ids)
        self.assertEqual(row['department_id'], self.dept.id)
        facade.act('preset_save', {'id': res['id'], 'stage_ids': []})
        row = [p for p in facade.get_setup()['presets'] if p['id'] == res['id']][0]
        self.assertEqual(row['stage_ids'], [])
        gone = facade.act('preset_delete', {'id': res['id']})
        self.assertEqual(gone['saved']['department_id'], self.dept.id)
        self.assertFalse(self.env['pb.hiring.stage.preset'].sudo().browse(res['id']).exists())

        recruiter = self._user('rec12', 'pb_hiring.group_hiring_user')
        with self.assertRaises(AccessError):
            facade.with_user(recruiter).act('preset_save', {
                'department_id': self.dept.id, 'stage_ids': asg.ids})
        with self.assertRaises(AccessError):
            facade.with_user(recruiter).act('stage_rename', {
                'stage_id': asg.id, 'name': 'Homework'})
        lead = self._user('lead12', 'pb_hiring.group_hiring_manager')
        facade.with_user(lead).act('stage_rename', {'stage_id': asg.id, 'name': 'Homework'})
        self.assertEqual(asg.with_context(lang='en_US').name, 'Homework')

    # ------------------------------------------------------------ test 13
    def test_13_set_up_has_six_cards_and_none_is_a_dead_end(self):
        setup = self.env['pb.hiring'].get_setup()
        self.assertEqual([c['key'] for c in setup['cards']],
                         ['stages', 'forms', 'scorecards', 'emails',
                          'automations', 'people',
                          # RECRUIT P4: Consent & retention, inline
                          'retention',
                          # RECRUIT P6: Before they join, inline
                          'prejoin'])
        for card in setup['cards']:
            self.assertTrue(card['status'], '%s has no sentence' % card['key'])
            if card.get('live') or card.get('inline'):
                continue
            action = card['action']
            self.assertTrue(action, '%s leads nowhere' % card['key'])
            if action.get('type') == 'ir.actions.act_window':
                self.assertTrue(action.get('views'),
                                '%s would throw "reading map" (RC13)' % card['key'])

    # ------------------------------------------------------------ test 14
    def test_14_the_middle_tier_is_the_talent_lead_everywhere(self):
        self.assertEqual(self.env.ref('pb_hiring.group_hiring_manager')
                         .with_context(lang='en_US').name, 'Talent lead')
        from odoo.addons.pb_vendor_access.hooks import CATALOGUE
        from odoo.addons.pb_vendor_access.catalogue_vi import VI
        row = [r for r in CATALOGUE if r[0] == ('hiring-manager',)][0]
        self.assertEqual(row[3], 'Talent lead')
        self.assertEqual(VI.get('Talent lead'), 'Trưởng nhóm tuyển dụng')
        self.assertTrue(VI.get(row[4]), 'the new sentence has no Vietnamese')
        if 'pb.role.ability' not in self.env:
            return
        path = get_module_path('pb_vendor_access') + \
            '/migrations/19.0.1.11.0/post-migrate.py'
        spec = importlib.util.spec_from_file_location('pbva_1110', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ability = self.env['pb.role.ability'].sudo().search(
            [('technical_key', '=', 'hiring-manager')], limit=1)
        if not ability:
            return
        ability.with_context(lang='en_US').write({'name': 'Hiring manager'})
        self.assertGreaterEqual(mod.rename_hiring_tiers(self.env), 1)
        self.assertEqual(ability.with_context(lang='en_US').name, 'Talent lead')
        self.assertEqual(mod.rename_hiring_tiers(self.env), 0, 'not idempotent')

    # ------------------------------------------------------------ test 15
    def test_15_the_stock_recruitment_menus_are_hidden(self):
        for xmlid in ('hr_recruitment.menu_hr_recruitment_root',
                      'hr_recruitment.menu_crm_case_categ0_act_job',
                      'hr_recruitment.menu_hr_job_position',
                      'hr_recruitment.menu_hr_job_position_interviewer',
                      'hr_recruitment.menu_hr_talent_pools',
                      'hr_recruitment.menu_crm_case_categ_all_app',
                      'hr_recruitment.menu_hr_recruitment_configuration',
                      'website_hr_recruitment.menu_job_pages'):
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                self.assertFalse(menu.with_context(active_test=False).active,
                                 '%s is still in the menus' % xmlid)

    def test_meanings_are_one_sentence_and_never_promise_a_later_phase(self):
        for key, text in MEANINGS.items():
            self.assertLessEqual(len(text), 160, key)
            self.assertNotIn('phone screen', text.lower())
            if key != 'phone':
                self.assertNotIn('Calendly', text, 'only Recruiter review sends it')
        # RECRUIT P5 made the promise true: moving into Recruiter review sends
        # the recruiter's Calendly link, and the column says so.
        self.assertIn('Calendly', MEANINGS['phone'])
