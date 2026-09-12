# -*- coding: utf-8 -*-
"""U02-U08 — the configuration facade.

What is proved here is that the SCREEN cannot be the thing that permits
anything: every case calls the facade the way the browser does, as a named
person, and checks the answer against the engine's own records rather than
against the payload the facade happened to build.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import MatrixCase


@tagged('post_install', '-at_install')
class TestMatrixFacade(MatrixCase):

    # ----------------------------------------------------------------- U02
    def test_u02_the_grid_is_refused_to_somebody_who_may_not_set_up(self):
        with self.assertRaises(AccessError):
            self.env['pb.approval.matrix'].with_user(self.asker).get_matrix()

    def test_u02_the_grid_lists_every_process_with_a_worked_out_status(self):
        grid = self.as_admin('pb.approval.matrix').get_matrix()
        rows = {row['process_key']: row
                for area in grid['areas'] for row in area['rows']}
        self.assertGreaterEqual(len(rows), 39)

        # the seeded default is published AND its object is wired up
        self.assertEqual(rows['generic']['status'], 'live')
        self.assertTrue(rows['generic']['route_labels'])
        self.assertTrue(rows['generic']['workflow_id'])

        # a process no adapter has claimed can never read as protected
        self.assertEqual(rows['reopen']['status'], 'soon')
        self.assertFalse(rows['reopen']['connected'])

        # money rows are marked so the publisher is asked to confirm later
        self.assertTrue(rows['bankfile']['money'])

    def test_u02_the_areas_are_the_ones_a_person_sees_on_the_rail(self):
        grid = self.as_admin('pb.approval.matrix').get_matrix()
        keys = [area['key'] for area in grid['areas']]
        for key in ('pay', 'money', 'data', 'people', 'time', 'setup',
                    'platform'):
            self.assertIn(key, keys)
        for area in grid['areas']:
            self.assertTrue(area['icon'], 'an area with no icon')

    # ----------------------------------------------------------------- U03
    def test_u03_every_preset_yields_a_draft_with_no_structural_error(self):
        matrix = self.as_admin('pb.approval.matrix')
        grid = matrix.get_matrix()
        self.assertTrue(grid['presets'])
        for preset in grid['presets']:
            made = matrix.create_workflow(preset['key'], 'generic')
            self.assertTrue(made['workflow_id'])
            opened = matrix.get_workflow(made['workflow_id'])
            saved = matrix.save_draft(
                opened['draft']['version_id'],
                opened['draft']['draft_revision'],
                opened['draft']['definition'], {})
            self.assertFalse(
                saved['errors'],
                'preset %s starts broken: %s' % (preset['key'],
                                                 saved['errors']))

    def test_u03_a_preset_that_names_nobody_is_not_an_error_yet(self):
        """"Joint sign-off" ships with an empty people list on purpose: the
        reader chooses the signatories. That is a warning at publish, never a
        refusal to create the draft."""
        matrix = self.as_admin('pb.approval.matrix')
        made = matrix.create_workflow('joint', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        self.assertTrue(opened['draft']['definition']['steps'])

    # ----------------------------------------------------------------- U04
    def test_u04_a_stale_draft_revision_is_refused(self):
        matrix = self.as_admin('pb.approval.matrix')
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        version_id = opened['draft']['version_id']
        revision = opened['draft']['draft_revision']
        matrix.save_draft(version_id, revision,
                          opened['draft']['definition'], {})
        with self.assertRaises(UserError):
            matrix.save_draft(version_id, revision,
                              opened['draft']['definition'], {})

    def test_u04_a_saved_draft_reads_back_the_engines_own_sentence(self):
        matrix = self.as_admin('pb.approval.matrix')
        made = matrix.create_workflow('officer', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        saved = matrix.save_draft(
            opened['draft']['version_id'], opened['draft']['draft_revision'],
            opened['draft']['definition'], {'name': 'Chain of three'})
        version = self.env['biz.approval.workflow.version'].sudo().browse(
            opened['draft']['version_id'])
        self.assertEqual(saved['summary'], version.summary)
        self.assertEqual(saved['route_labels'], version.route_labels)
        self.assertEqual(version.workflow_id.name, 'Chain of three')
        # and the same sentence the additive engine method now writes
        self.assertEqual(
            saved['summary'],
            self.env['biz.approval.engine'].with_user(self.boss).summary(
                version.definition))

    def test_u04_a_published_version_cannot_be_edited_through_the_facade(self):
        workflow = self.seeded_workflow()
        matrix = self.as_admin('pb.approval.matrix')
        with self.assertRaises(UserError):
            matrix.save_draft(workflow.published_version_id.id, None, {}, {})

    # ----------------------------------------------------------------- U05
    def test_u05_the_example_names_the_people_the_route_would_reach(self):
        matrix = self.as_admin('pb.approval.matrix')
        self.hold(self.role_finance, self.fin)
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        definition = dict(opened['draft']['definition'], steps=[{
            'key': 's1', 'kind': 'approve', 'title': 'Finance approval',
            'who': {'mode': 'role', 'role': 'finance', 'scope': 'company'},
            'min_amount': 0, 'condition': None,
        }])
        matrix.save_draft(opened['draft']['version_id'],
                          opened['draft']['draft_revision'], definition, {})
        preview = matrix.preview(opened['draft']['version_id'],
                                 {'company_id': self.company.id})
        step = preview['steps'][0]
        self.assertEqual([p['user_id'] for p in step['people']],
                         [self.fin.id])
        self.assertFalse(step['issue'])
        self.assertEqual(preview['level'], 'ready')

    def test_u05_a_seat_with_nobody_is_an_issue_that_carries_its_repair(self):
        matrix = self.as_admin('pb.approval.matrix')
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        definition = dict(opened['draft']['definition'], steps=[{
            'key': 's1', 'kind': 'approve', 'title': 'HR lead review',
            'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'company'},
            'min_amount': 0, 'condition': None,
        }])
        matrix.save_draft(opened['draft']['version_id'],
                          opened['draft']['draft_revision'], definition, {})
        preview = matrix.preview(opened['draft']['version_id'],
                                 {'company_id': self.company.id})
        issue = preview['steps'][0]['issue']
        self.assertTrue(issue)
        self.assertEqual(issue['level'], 'block')
        self.assertEqual(issue['code'], 'person_missing')
        acts = [fix['act'] for fix in issue['fixes']]
        self.assertIn('assign', acts, 'the gap has no way to mend it')

    # ----------------------------------------------------------------- U06
    def test_u06_coverage_lists_a_gap_and_naming_somebody_clears_it(self):
        matrix = self.as_admin('pb.approval.matrix')
        # a generic request in a part of the business gives the scan a scope
        self.Generic.with_user(self.asker).with_company(self.company).create({
            'name': 'Something in Retail', 'company_id': self.company.id,
            'requester_user_id': self.asker.id,
            'area_key': 'retail', 'area_label': 'Retail',
        })
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        definition = dict(opened['draft']['definition'], steps=[{
            'key': 's1', 'kind': 'approve', 'title': 'HR lead review',
            'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'area'},
            'min_amount': 0, 'condition': None,
        }])
        matrix.save_draft(opened['draft']['version_id'],
                          opened['draft']['draft_revision'], definition, {})

        scan = matrix.check_coverage(opened['draft']['version_id'])
        self.assertTrue(scan['ran'])
        self.assertTrue(scan['gaps'], 'a route with no HR lead anywhere is '
                                      'not reported as a gap')
        row = next(r for r in scan['rows'] if r['issues'])
        self.assertEqual(row['issues'][0]['fix']['kind'], 'assign')
        self.assertEqual(row['issues'][0]['fix']['role_key'], 'hr_lead')

        # the role allows no company fall-back, so each place needs its own
        self.hold(self.role_hr_lead, self.hr, scope_key='area:retail')
        self.hold(self.role_hr_lead, self.hr, scope_key='')
        again = matrix.check_coverage(opened['draft']['version_id'])
        self.assertFalse(again['gaps'],
                         'naming somebody did not clear the gap: %s'
                         % again['rows'])

    # ----------------------------------------------------------------- U07
    def test_u07_publishing_needs_the_warnings_confirmed_first(self):
        matrix = self.as_admin('pb.approval.matrix')
        self.hold(self.role_finance, self.fin)
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        definition = dict(opened['draft']['definition'], steps=[{
            'key': 's1', 'kind': 'approve', 'title': 'Finance approval',
            'who': {'mode': 'role', 'role': 'finance', 'scope': 'company'},
            'min_amount': 0, 'condition': None,
        }])
        saved = matrix.save_draft(opened['draft']['version_id'],
                                  opened['draft']['draft_revision'],
                                  definition, {})
        version_id = opened['draft']['version_id']

        publication = matrix.publication_preview(version_id)
        self.assertFalse(publication['errors'])
        self.assertTrue(publication['warnings'],
                        'a one-person route raises nothing to confirm')
        self.assertTrue(publication['diff'])

        with self.assertRaises(UserError):
            matrix.publish(version_id, saved['draft_revision'], None,
                           'no confirmations', [])

        result = matrix.publish(
            version_id, saved['draft_revision'], None, 'Because I said so',
            [w['code'] for w in publication['warnings']])
        self.assertTrue(result['version_id'])

        version = self.env['biz.approval.workflow.version'].sudo().browse(
            version_id)
        self.assertEqual(version.status, 'published')
        self.assertTrue(version.confirmations,
                        'the confirmations were not kept with the version')
        self.assertEqual(version.publish_reason, 'Because I said so')

        # and it is on the trail, in words
        events = self.env['biz.approval.event'].sudo().search(
            [('kind', '=', 'published'), ('workflow_id', '=',
                                          version.workflow_id.id)])
        self.assertTrue(events)
        history = matrix.get_history(self.company.id, 'publishes')
        self.assertTrue(any(row['summary'] for row in history['rows']))

    def test_u07_a_published_route_shows_as_in_use_on_the_grid(self):
        matrix = self.as_admin('pb.approval.matrix')
        grid = matrix.get_matrix()
        row = next(r for area in grid['areas'] for r in area['rows']
                   if r['process_key'] == 'generic')
        self.assertEqual(row['status'], 'live')
        self.assertTrue(row['version'])

    def test_u07_publishing_is_refused_to_somebody_who_may_only_draft(self):
        """Deciding who signs pay off must not make you a person who signs pay
        off, so the two powers are separate groups."""
        matrix = self.env['pb.approval.matrix'].with_user(
            self.officer).with_company(self.company)
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        self.assertFalse(opened['can_publish'])
        with self.assertRaises(AccessError):
            matrix.publish(opened['draft']['version_id'], None, None, '', [])

    # ----------------------------------------------------------------- U08
    def test_u08_two_holders_of_one_seat_at_one_time_are_refused(self):
        matrix = self.as_admin('pb.approval.matrix')
        matrix.set_responsibility(self.company.id, 'finance', '', self.fin.id)
        matrix.set_responsibility(self.company.id, 'finance', '', self.hr.id)
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_finance.id), ('active', '=', True)])
        self.assertEqual(len(held), 1, 'a seat grew a second holder')
        self.assertEqual(held.user_id, self.hr)

    def test_u08_a_person_from_another_company_cannot_hold_a_seat(self):
        other = self.env['res.company'].create({'name': 'AM Beta'})
        outsider = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Otto Outside', 'login': 'am_outside',
                'company_id': other.id, 'company_ids': [(6, 0, [other.id])],
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            })
        with self.assertRaises(UserError):
            self.as_admin('pb.approval.matrix').set_responsibility(
                self.company.id, 'finance', '', outsider.id)

    def test_u08_the_picker_says_who_cannot_open_this_kind_of_request(self):
        rows = self.as_admin('pb.approval.matrix').user_options(
            'Hana', 'hr_lead', self.company.id, 'payrun')
        self.assertTrue(rows)
        row = rows[0]
        self.assertIn('eligible', row)
        self.assertIn('needs_permission', row)
        self.assertFalse(row['eligible'],
                         'somebody with no payroll access is not flagged')
        self.assertTrue(row['needs_permission'],
                        'the flag carries no words explaining it')

        # naming them anyway is allowed: the screen says what is still missing
        self.as_admin('pb.approval.matrix').set_responsibility(
            self.company.id, 'hr_lead', '', self.hr.id)
        grid = self.as_admin('pb.approval.matrix').get_people(self.company.id)
        cell = next(c for role in grid['roles'] if role['key'] == 'hr_lead'
                    for c in role['cells'] if c['scope_key'] == '')
        self.assertEqual(cell['state'], 'held')
        self.assertEqual(cell['name'], self.hr.name)

    def test_u08_an_empty_seat_a_route_needs_is_a_gap_even_company_wide(self):
        """Found in the browser walk: a company with no divisions showed
        "every seat has somebody in it" while the seat its only published
        route needed was empty. A company-wide seat with nobody stops a
        request exactly as hard as a divisional one.

        And the other half: an empty seat NO route asks for is not a gap.
        Every responsibility in the catalogue starts empty, and calling all
        nine a problem would be noise nobody could act on.
        """
        matrix = self.as_admin('pb.approval.matrix')
        made = matrix.create_workflow('blank', 'generic')
        opened = matrix.get_workflow(made['workflow_id'])
        definition = dict(opened['draft']['definition'], steps=[{
            'key': 's1', 'kind': 'approve', 'title': 'Finance approval',
            'who': {'mode': 'role', 'role': 'finance', 'scope': 'company'},
            'min_amount': 0, 'condition': None,
        }])
        matrix.save_draft(opened['draft']['version_id'],
                          opened['draft']['draft_revision'], definition, {})

        grid = matrix.get_people(self.company.id)
        gaps = {gap['role_key'] for gap in grid['gaps']}
        self.assertIn('finance', gaps,
                      'an empty seat the route needs is not reported')
        self.assertNotIn('director', gaps,
                         'a seat no route asks for is reported as a problem')

        matrix.set_responsibility(self.company.id, 'finance', '', self.fin.id)
        after = matrix.get_people(self.company.id)
        self.assertNotIn('finance',
                         {gap['role_key'] for gap in after['gaps']})

    def test_u08_clearing_a_seat_leaves_it_empty_rather_than_wrong(self):
        matrix = self.as_admin('pb.approval.matrix')
        matrix.set_responsibility(self.company.id, 'finance', '', self.fin.id)
        matrix.clear_responsibility(self.company.id, 'finance', '')
        grid = matrix.get_people(self.company.id)
        cell = next(c for role in grid['roles'] if role['key'] == 'finance'
                    for c in role['cells'] if c['scope_key'] == '')
        self.assertEqual(cell['state'], 'empty')

    # ----------------------------------------------------------------- U09
    def test_u09_cover_can_be_arranged_and_stopped(self):
        matrix = self.as_admin('pb.approval.matrix')
        made = matrix.set_delegation({
            'company_id': self.company.id,
            'principal_user_id': self.fin.id,
            'delegate_user_id': self.hr.id,
            'date_from': '2026-01-01', 'date_to': '2099-01-01',
            'reason': 'Annual leave',
        })
        rows = matrix.list_delegations(self.company.id)
        row = next(r for r in rows if r['id'] == made['id'])
        self.assertTrue(row['live'], 'the cover is not in force')
        self.assertEqual(row['delegate'], self.hr.name)

        matrix.end_delegation(made['id'])
        rows = matrix.list_delegations(self.company.id)
        row = next(r for r in rows if r['id'] == made['id'])
        self.assertEqual(row['state'], 'revoked')

    def test_u09_arranging_somebody_elses_cover_needs_the_admin_group(self):
        matrix = self.env['pb.approval.matrix'].with_user(
            self.officer).with_company(self.company)
        with self.assertRaises(AccessError):
            matrix.set_delegation({
                'company_id': self.company.id,
                'principal_user_id': self.fin.id,
                'delegate_user_id': self.hr.id,
                'date_from': '2026-01-01', 'date_to': '2099-01-01',
                'reason': 'Annual leave',
            })

    # ------------------------------------------------- where it applies
    def test_the_scheme_panel_says_inherited_before_anything_narrower(self):
        panel = self.as_admin('pb.approval.matrix').get_scheme_panel(
            'generic', '', self.company.id)
        self.assertEqual(panel['selection'], 'custom')
        self.assertTrue(panel['route_labels'])
        self.assertEqual(panel['scope_label'], self.company.name)

    def test_the_whole_company_card_cannot_be_repointed_from_the_panel(self):
        with self.assertRaises(UserError):
            self.as_admin('pb.approval.matrix').set_scheme_binding(
                'generic', '', 'custom', 0, self.company.id)

    def test_the_scope_options_carry_a_level_a_label_and_options(self):
        shape = self.as_admin('pb.approval.matrix')._approval_scope_options(
            self.env['biz.approval.process']._by_key('generic'), self.company)
        self.assertIsInstance(shape, list)
        for level in shape:
            self.assertIn('level', level)
            self.assertIn('label', level)
            self.assertIn('options', level)
            for option in level['options']:
                self.assertIn('key', option)
                self.assertIn('label', option)
                self.assertIn(':', option['key'],
                              'a scope fragment must name its level')

    def test_scope_keys_are_joined_most_specific_first(self):
        matrix = self.as_admin('pb.approval.matrix')
        self.assertEqual(
            matrix.scope_key_for(['division:7', 'scheme:3']),
            'scheme:3|division:7')
        self.assertEqual(matrix.scope_key_for([]), '')
        self.assertEqual(matrix.scope_key_for(['division:7']), 'division:7')
