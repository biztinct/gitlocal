# -*- coding: utf-8 -*-
"""Regression contract for the Connection & Feed Studio."""
import json
from urllib.parse import parse_qs, urlparse

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFeedConfiguration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cockpit = cls.env['pb.import.connector.cockpit']
        cls.Connector = cls.env['hr.integration.connector']

    def _zoho(self, name='Feed Studio Zoho'):
        return self.Connector.create({
            'name': name,
            'connector_type': 'zoho',
            'auth_type': 'oauth2',
            'api_endpoint': 'https://people.zoho.com/people/api',
        })

    def test_seeded_zoho_catalogue_marks_only_proven_feeds_runnable(self):
        connector = self._zoho()
        detail = self.Cockpit.get_connector_detail(connector.id)
        by_code = {row['code']: row for row in detail['endpoints']}

        self.assertEqual(len(by_code), 7)
        self.assertEqual(by_code['zohoemployees']['operation'], 'employee')
        self.assertEqual(
            by_code['zohoemployees']['full_url'],
            'https://people.zoho.com/people/api/forms/P_Employee/records')
        self.assertTrue(by_code['zohoemployees']['runnable'])
        self.assertEqual(by_code['zoholeave']['path'], 'leave/getLeaveDetails')
        self.assertEqual(by_code['zohotimesheet']['operation'], 'catalog_only')
        self.assertFalse(by_code['zohotimesheet']['runnable'])

    def test_save_is_additive_and_does_not_accept_secrets(self):
        connector = self._zoho('Feed Studio additive')
        planted = 'must-not-travel-through-public-config'
        result = self.Cockpit.save_configuration(connector.id, {
            'api_endpoint': 'https://people.zoho.eu/people/api/',
            'sync_interval': '120',
            'client_secret': planted,
        }, [{
            'id': 0, 'name': 'Awards', 'code': 'awards',
            'data_type': 'custom', 'operation': 'generic',
            'http_method': 'get', 'path': 'forms/P_Awards/records',
            'params_note': 'sIndex, limit', 'active': True,
        }])

        connector.invalidate_recordset()
        self.assertEqual(connector.api_endpoint,
                         'https://people.zoho.eu/people/api')
        self.assertEqual(connector.sync_interval, 120)
        self.assertFalse(connector.client_secret)
        self.assertTrue(connector.endpoint_ids.filtered(
            lambda row: row.code == 'awards'))
        self.assertNotIn(planted, json.dumps(result, default=str))

    def test_explicit_restore_returns_to_seeded_template(self):
        connector = self._zoho('Feed Studio restore')
        employee = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohoemployees')
        employee.write({
            'name': 'My employee API', 'path': 'custom/employees',
            'operation': 'catalog_only',
        })

        result = self.Cockpit.restore_endpoint_template(
            connector.id, employee.id)
        employee.invalidate_recordset()
        self.assertFalse(result.get('error'))
        self.assertEqual(employee.name, 'Employees')
        self.assertEqual(employee.path, 'forms/P_Employee/records')
        self.assertEqual(employee.operation, 'employee')

    def test_invalid_and_credential_bearing_urls_are_refused(self):
        connector = self._zoho('Feed Studio validation')
        with self.assertRaises(ValidationError):
            self.Cockpit.save_configuration(
                connector.id, {'api_endpoint': 'not a URL'}, [])
        with self.assertRaises(ValidationError):
            self.Cockpit.save_configuration(
                connector.id,
                {'api_endpoint': 'https://user:secret@example.com/api'}, [])

    def test_duplicate_feed_code_gets_a_clear_validation_error(self):
        connector = self._zoho('Feed Studio duplicate guard')
        with self.assertRaisesRegex(ValidationError, 'already used'):
            self.Cockpit.save_configuration(connector.id, {}, [{
                'id': 0, 'name': 'Duplicate employees',
                'code': 'zohoemployees', 'data_type': 'employee',
                'operation': 'employee', 'http_method': 'get',
                'path': 'forms/P_Employee/records', 'active': True,
            }])

    def test_feed_output_type_is_stable_after_it_has_stored_data(self):
        connector = self._zoho('Feed Studio provenance guard')
        employee = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohoemployees')
        self.env['hr.api.data.store'].create({
            'connector_id': connector.id, 'endpoint_id': employee.id,
            'data_type': 'employee', 'raw_payload': {'EmployeeID': 'E-1'},
        })
        with self.assertRaisesRegex(ValidationError, 'cannot change'):
            self.Cockpit.save_configuration(connector.id, {}, [{
                'id': employee.id, 'name': employee.name,
                'code': employee.code, 'data_type': 'custom',
                'operation': employee.operation,
                'http_method': employee.http_method, 'path': employee.path,
                'params_note': employee.params_note, 'active': True,
            }])

    def test_execution_and_output_type_cannot_contradict_each_other(self):
        connector = self._zoho('Feed Studio operation guard')
        employee = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohoemployees')
        with self.assertRaisesRegex(ValidationError, 'must produce'):
            self.Cockpit.save_configuration(connector.id, {}, [{
                'id': employee.id, 'name': employee.name,
                'code': employee.code, 'data_type': 'custom',
                'operation': 'employee', 'http_method': 'get',
                'path': employee.path, 'params_note': employee.params_note,
                'active': True,
            }])

    def test_exact_feed_counts_do_not_duplicate_legacy_rows(self):
        connector = self._zoho('Feed Studio provenance')
        overtime = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohoovertime')
        timesheet = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohotimesheet')
        Store = self.env['hr.api.data.store']
        Store.create({
            'connector_id': connector.id, 'endpoint_id': overtime.id,
            'data_type': 'custom', 'raw_payload': {'kind': 'exact'},
        })
        Store.create({
            'connector_id': connector.id, 'data_type': 'custom',
            'raw_payload': {'kind': 'older-unassigned'},
        })

        self.assertEqual(overtime.synced_count, 2)
        self.assertEqual(timesheet.synced_count, 0)
        self.assertEqual(overtime.unassigned_count, 1)
        self.assertEqual(timesheet.unassigned_count, 1)
        self.assertEqual(
            overtime.synced_count + timesheet.synced_count,
            Store.search_count([
                ('connector_id', '=', connector.id),
                ('data_type', '=', 'custom'),
            ]))

    def test_field_discovery_uses_the_selected_feed_not_its_sibling(self):
        connector = self._zoho('Feed Studio exact field discovery')
        overtime = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohoovertime')
        timesheet = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohotimesheet')
        Store = self.env['hr.api.data.store']
        Store.create({
            'connector_id': connector.id, 'endpoint_id': overtime.id,
            'data_type': 'custom', 'raw_payload': {'OvertimeOnly': 1},
        })
        Store.create({
            'connector_id': connector.id, 'endpoint_id': timesheet.id,
            'data_type': 'custom', 'raw_payload': {'TimesheetOnly': 1},
        })

        fields_ = self.env[
            'hr.integration.field.mapping'].get_available_source_fields(
                connector.id, 'custom', overtime.id)
        paths = {item['path'] for item in fields_}
        self.assertIn('OvertimeOnly', paths)
        self.assertNotIn('TimesheetOnly', paths)

    def test_runtime_url_resolution_honours_connector_and_feed(self):
        from odoo.addons.pb_hr_payroll_formula.integrations.zoho_connector import (
            ZohoConnector,
        )

        connector = self._zoho('Feed Studio URL runtime')
        employee = connector.endpoint_ids.filtered(
            lambda row: row.code == 'zohoemployees')
        connector.api_endpoint = 'https://people.zoho.com.au/people/api'
        employee.path = 'forms/Custom_Employee/records'
        runtime = ZohoConnector(connector)
        self.assertEqual(
            runtime._endpoint_url('zohoemployees', 'unused/fallback'),
            'https://people.zoho.com.au/people/api/forms/Custom_Employee/records')

        employee.path = 'https://proxy.example.test/zoho/employees'
        self.assertEqual(
            runtime._endpoint_url('zohoemployees', 'unused/fallback'),
            'https://proxy.example.test/zoho/employees')

    def test_oauth_url_uses_configured_contract_and_one_time_state(self):
        from odoo.addons.pb_hr_payroll_formula.integrations.zoho_connector import (
            ZohoConnector,
        )

        connector = self._zoho('Feed Studio OAuth contract')
        connector.write({
            'client_id': 'client-id',
            'oauth_authorize_url': 'https://accounts.zoho.eu/oauth/v2/auth',
            'oauth_redirect_uri': 'https://payobook.example/zoho/callback',
            'oauth_scope': 'ZOHOPEOPLE.forms.READ',
        })
        parsed = urlparse(ZohoConnector(connector).get_authorization_url(
            state='single-use-state'))
        query = parse_qs(parsed.query)
        self.assertEqual(
            parsed.geturl().split('?', 1)[0],
            'https://accounts.zoho.eu/oauth/v2/auth')
        self.assertEqual(query['client_id'], ['client-id'])
        self.assertEqual(
            query['redirect_uri'], ['https://payobook.example/zoho/callback'])
        self.assertEqual(query['state'], ['single-use-state'])
