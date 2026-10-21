"""Desk projection, precedence review and atomic source editing. All fixtures roll back."""
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError


@tagged('post_install', '-at_install', 'mapping_experience')
class TestMappingExperience(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.studio = cls.env['pb.formula.studio']
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Connection desk test', 'code': 'DESKTEST', 'country_code': 'VN',
            'source_api_enabled': True, 'source_excel_enabled': True, 'source_records_enabled': True})
        cls.rule = cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id, 'name': 'Working hours', 'code': 'DESKHOURS',
            'column_type': 'input', 'value_kind': 'quantity'})
        cls.rule.set_source_binding('excel', 'Hours', origin='board')
        cls.rule.set_source_binding('feed', 'hours', origin='board')
        cls.connector = cls.env['hr.integration.connector'].create({'name': 'Desk test connector', 'connector_type': 'zoho'})
        cls.env['hr.api.data.store'].create({'connector_id': cls.connector.id, 'data_type': 'custom',
            'employee_external_id': 'DESK1', 'raw_payload': {'hours': 0},
            'extracted_data': {'hours': 0}, 'state': 'extracted'})
        cls.admin = cls.env['res.users'].create({'name': 'Desk administrator', 'login': 'desk-admin-test',
            'group_ids': [(4, cls.env.ref('pb_hr_payroll_formula.group_formula_admin').id)]})
        cls.manager = cls.env['res.users'].create({'name': 'Desk manager', 'login': 'desk-manager-test',
            'group_ids': [(4, cls.env.ref('pb_hr_payroll_formula.group_formula_manager').id)]})
        cls.reader = cls.env['res.users'].create({'name': 'Desk reader', 'login': 'desk-reader-test',
            'group_ids': [(4, cls.env.ref('pb_hr_payroll_formula.group_formula_user').id)]})

    def _spec(self):
        return {'name': 'Desk hours total', 'output_key': 'DESKTOTAL', 'builder_mode': 'guided',
            'rule_type': 'sum', 'source_data_type': 'custom', 'record_source': 'records',
            'filter_conditions': {'join': 'all', 'rows': []},
            'value_steps': [{'field': 'hours', 'contains': 'number'}], 'default_value': 0}

    def test_read_does_not_rewrite_configuration(self):
        before = (self.config.write_date, self.rule.write_date, self.rule.value_kind, self.rule.source_ids.ids)
        data = self.studio.mapping_workspace_data(self.config.id)
        self.assertTrue(data['ok'])
        row = next(r for r in data['components'] if r['id'] == self.rule.id)
        self.assertEqual([s['kind'] for s in row['sources']], ['feed', 'excel'])
        self.assertEqual(before, (self.config.write_date, self.rule.write_date, self.rule.value_kind, self.rule.source_ids.ids))

    def test_application_journey_separates_mapping_from_data_readiness(self):
        self.config.write({'application_data_enabled': True, 'application_effective_from': '2026-11-01'})
        self.rule.write({'application_source_key': 'period.paid_day_equivalents'})
        pending = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'code': 'DESKPENDING', 'name': 'Unreviewed metadata', 'column_type': 'input',
            'application_source_key': 'pending.domain.DESKPENDING'})
        data = self.studio.journey_data(self.config.id)
        app = data['header']['application']
        self.assertEqual(app['spreadsheet'], 1)
        self.assertEqual(app['pending'], 1)
        self.assertEqual(app['mapped'], 1)
        self.assertEqual(data['header']['fed'], 1)
        pending_row = next(r for r in data['lanes']['scheme'][0]['rows'] if r['id'] == 's:%s' % pending.id)
        self.assertFalse(pending_row['fed'])
        self.assertIn('review', pending_row['sub'])
        self.assertTrue(any(r['group'] == 'application' for r in data['lanes']['source'][0]['rows']))
        desk = self.studio.mapping_workspace_data(self.config.id)
        descriptors = {r['id']: r['application_source'] for r in desk['components']}
        self.assertTrue(descriptors[self.rule.id]['available'])
        self.assertTrue(descriptors[pending.id]['pending'])

    def test_completed_branch_arrival_returns_mainline(self):
        branch = self.config.copy({'name': 'Merged migration branch', 'code': 'DESKMERGED',
                                  'parent_branch_id': self.config.id, 'branch_state': 'merged'})
        data = self.studio.mapping_pickers({'config_id': branch.id})
        self.assertNotIn(branch.id, [c['id'] for c in data['configs']])
        self.assertEqual(data['defaults']['config_id'], self.config.id)
        self.assertIn('config', data['defaults']['fell_back'])

    def test_unified_mapping_keeps_hr_context_and_period_sources_honest(self):
        self.config.write({'application_data_enabled': True, 'application_effective_from': '2026-11-01'})
        self.rule.application_source_key = 'period.paid_day_equivalents'
        context = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'code': 'DESKASSET', 'name': 'IT Asset number', 'column_type': 'input',
            'value_kind': 'text', 'net_role': 'info', 'application_source_key': 'assets.physical_codes'})
        rows = {r['id']: r for r in self.studio.mapping_workspace_data(self.config.id)['components']}
        self.assertFalse(rows[context.id]['payroll_relevant'])
        self.assertIn('pb.asset.assignment', rows[context.id]['mapping_details'][0]['owner'])
        self.assertIn('read only', rows[context.id]['mapping_details'][0]['direction'])
        self.assertTrue(rows[self.rule.id]['payroll_relevant'])
        self.assertIn('contractual', rows[self.rule.id]['mapping_details'][0]['calculation'])
        self.assertIn('not checked', rows[self.rule.id]['mapping_details'][0]['availability'])
        self.config.payroll_basis = 'timesheet'
        row = next(r for r in self.studio.mapping_workspace_data(self.config.id)['components'] if r['id'] == self.rule.id)
        self.assertIn('hr.attendance', row['mapping_details'][0]['calculation'])
        self.assertIn('Attendance', row['mapping_details'][0]['owner'])

    def test_formula_consumed_text_stays_in_payroll_view(self):
        self.rule.write({'value_kind': 'text', 'net_role': 'info'})
        self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'Conditional pay',
            'code': 'DESKRESULT', 'column_type': 'formula', 'excel_formula': '=IF(DESKHOURS="Yes",1,0)'})
        row = next(r for r in self.studio.mapping_workspace_data(self.config.id)['components'] if r['id'] == self.rule.id)
        self.assertTrue(row['payroll_relevant'])

    def test_closed_branches_are_history_not_operational_configs(self):
        branch = self.config.copy({'name': 'Historic desk', 'code': 'DESKHISTORY',
            'parent_branch_id': self.config.id, 'branch_state': 'merged'})
        self.assertNotIn(branch.id, [c['id'] for c in self.studio.get_config_list()])
        with patch.object(type(self.studio), 'get_problems', return_value={'counts': {}}):
            card = next(c for c in self.studio.bureau_board()['cards'] if c['id'] == branch.id)
        self.assertEqual(card['branch_state'], 'merged')
        self.assertEqual(card['parent_id'], self.config.id)

    def test_default_employee_catalogue_preserves_wires_not_unrelated_fields(self):
        data = self.studio.employee_mapping_data(self.config.id, False, True)
        curated, _ = self.studio._ec_lane_index()
        wired = {w['rightId'] for w in data['wires']}
        for item in data['right']:
            if item['id'].startswith('f:') and item['id'] not in wired:
                self.assertIn((item['meta']['model'], item['meta']['field']), curated)
        self.assertNotIn('f:hr.employee:sunday_location_id', [i['id'] for i in data['right']])

    def test_preview_is_read_only_and_save_matches_engine_order(self):
        order = ['excel', 'records', 'api']
        before = self.config.source_priority
        preview = self.studio.mapping_priority_preview(self.config.id, order)
        self.assertEqual(self.config.source_priority, before)
        row = next(r for r in preview['affected'] if r['id'] == self.rule.id)
        self.assertEqual([s['kind'] for s in row['after']], ['excel', 'feed'])
        self.studio.mapping_priority_save(self.config.id, order, preview['token'])
        self.assertEqual([s['kind'] for s in self.studio._declared_sources(self.rule, {})], ['excel', 'feed'])
        self.assertEqual(self.config._source_kind_rank()[-1], 'pay_run')

    def test_disabled_lanes_remain_disabled_including_legacy_wires(self):
        self.config.source_api_enabled = False
        wires = {self.rule.id: {'kind': 'feed', 'key': 'hours'}}
        self.assertEqual([s['kind'] for s in self.studio._declared_sources(self.rule, {}, wires)], ['excel'])
        p = self.studio.mapping_priority_preview(self.config.id, ['records', 'api', 'excel'])
        self.studio.mapping_priority_save(self.config.id, ['records', 'api', 'excel'], p['token'])
        self.assertFalse(self.config.source_api_enabled)

    def test_stale_review_and_invalid_order_are_refused(self):
        token = self.studio._desk_priority(self.config)['token']
        self.config.source_priority = 'records,excel,api'
        with self.assertRaises(UserError):
            self.studio.mapping_priority_save(self.config.id, ['excel', 'api', 'records'], token)
        with self.assertRaises(UserError):
            self.studio.mapping_priority_preview(self.config.id, ['api', 'api', 'excel'])

    def test_reader_cannot_mutate_priority_or_create_component(self):
        with self.assertRaises(AccessError):
            self.studio.with_user(self.reader).mapping_priority_save(self.config.id, ['api', 'excel', 'records'], '')
        with self.assertRaises(AccessError):
            self.studio.with_user(self.reader).mapping_component_create(self.config.id, 'Not allowed')

    def test_text_component_keeps_existing_sources(self):
        sources = self.rule.source_ids.ids
        self.studio.mapping_component_setup(self.config.id, self.rule.id, 'text', 'info', 'text')
        self.assertTrue(self.rule.is_text_component)
        self.assertTrue(self.rule.is_contract_component)
        self.assertEqual(self.rule.source_ids.ids, sources)
        self.assertEqual(self.rule.value_kind, 'text')
        self.assertEqual(self.rule.net_role, 'info')

    def test_invalid_storage_rolls_back_new_component(self):
        before = self.config.rule_ids.ids
        with self.assertRaises(UserError):
            self.studio.mapping_component_create(self.config.id, 'Invalid text amount', 'money', 'text')
        self.assertEqual(self.config.rule_ids.ids, before)
        with self.assertRaises(UserError):
            self.studio.mapping_component_create(self.config.id, '   ')

    def test_atomic_save_and_connect_preserves_spreadsheet_fallback(self):
        result = self.studio.with_user(self.admin).mapping_rule_save(self.config.id, self.connector.id, self._spec(), target_id=self.rule.id)
        self.assertTrue(result['ok'])
        self.assertTrue(self.env['hr.integration.field.mapping'].search([
            ('connector_id', '=', self.connector.id), ('target_rule_id', '=', self.rule.id), ('source_field', '=', 'DESKTOTAL')]))
        self.assertTrue(self.rule.source_ids.filtered(lambda s: s.kind == 'excel' and s.key == 'Hours'))

    def test_failed_connection_rolls_back_rule_save(self):
        with patch.object(type(self.studio), 'api_mapping_create', return_value={'ok': False, 'msg': 'Connection test refusal'}) as connect:
            with self.assertRaises(UserError):
                self.studio.with_user(self.admin).mapping_rule_save(self.config.id, self.connector.id, self._spec(), target_id=self.rule.id)
            connect.assert_called_once()
        self.assertFalse(self.env['hr.api.transformation.rule'].search([('connector_id', '=', self.connector.id), ('output_key', '=', 'DESKTOTAL')]))

    def test_text_and_foreign_targets_cannot_be_connected(self):
        self.rule.write({'is_text_component': True, 'value_kind': 'text'})
        self.assertNotIn(self.rule.id, [r['id'] for r in self.studio.mapping_rule_targets(self.config.id)])
        with self.assertRaises(UserError):
            self.studio.mapping_rule_save(self.config.id, self.connector.id, self._spec(), target_id=self.rule.id)

    def test_rule_editor_without_mapping_rights_can_only_save_rule(self):
        studio = self.studio.with_user(self.manager)
        self.assertEqual(studio.mapping_rule_targets(self.config.id), [])
        with self.assertRaises(AccessError):
            studio.mapping_rule_save(self.config.id, self.connector.id, self._spec(), target_id=self.rule.id)
        self.assertFalse(self.env['hr.api.transformation.rule'].search([('connector_id', '=', self.connector.id), ('output_key', '=', 'DESKTOTAL')]))
        self.assertTrue(studio.mapping_rule_save(self.config.id, self.connector.id, self._spec())['ok'])

    def test_priority_review_expires_when_a_component_or_binding_changes(self):
        token = self.studio._desk_priority(self.config)['token']
        self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'New input',
            'code': 'DESKNEW', 'column_type': 'input'})
        with self.assertRaises(UserError):
            self.studio.mapping_priority_save(self.config.id, ['excel', 'api', 'records'], token)
        token = self.studio._desk_priority(self.config)['token']
        self.rule.set_source_binding('excel', 'Another column', origin='board')
        with self.assertRaises(UserError):
            self.studio.mapping_priority_save(self.config.id, ['excel', 'api', 'records'], token)
