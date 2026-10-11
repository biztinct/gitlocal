# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""PAYAI P0 — an approval switch in a request is dropped at the door."""
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.models.ir_http import (
    is_guarded_key, scrub_params)


@tagged('post_install', '-at_install')
class TestContextScrub(TransactionCase):

    def test_the_twelve_switches_and_the_two_tokens_are_guarded(self):
        for key in ('pb_contract_approved_write', 'pb_bands_approved_write',
                    'pb_unlock_approved_write', 'pb_newhire_approved_write',
                    'pb_statutory_approved_write', 'pb_chain_state_write',
                    'pb_import_apply'):
            self.assertTrue(is_guarded_key(key), key)
        for key in ('lang', 'tz', 'active_id', 'pb_lens', 'default_state',
                    'approved_write_note'):
            self.assertFalse(is_guarded_key(key), key)

    def test_call_kw_context_is_scrubbed_in_place(self):
        params = {'model': 'hr.contract', 'method': 'write',
                  'args': [[1], {'wage': 1}],
                  'kwargs': {'context': {'lang': 'en_US',
                                         'pb_contract_approved_write': True}}}
        dropped = scrub_params(params)
        self.assertEqual(dropped, ['pb_contract_approved_write'])
        self.assertEqual(params['kwargs']['context'], {'lang': 'en_US'})

    def test_execute_kw_and_positional_context_are_scrubbed(self):
        params = {'service': 'object', 'method': 'execute_kw',
                  'args': ['db', 2, 'pw', 'pb.wf.lock', 'unlock_day',
                           [{'pb_unlock_approved_write': True, 'day': '2026-06-01'}],
                           {'context': {'pb_bands_approved_write': 1}}]}
        dropped = scrub_params(params)
        self.assertEqual(sorted(dropped), ['pb_bands_approved_write',
                                           'pb_unlock_approved_write'])
        self.assertEqual(params['args'][5][0], {'day': '2026-06-01'})
        self.assertEqual(params['args'][6], {'context': {}})

    def test_a_clean_request_is_left_alone(self):
        params = {'model': 'hr.employee', 'method': 'search_read',
                  'args': [], 'kwargs': {'context': {'lang': 'vi_VN'},
                                         'fields': ['name']}}
        before = repr(params)
        self.assertEqual(scrub_params(params), [])
        self.assertEqual(repr(params), before)
