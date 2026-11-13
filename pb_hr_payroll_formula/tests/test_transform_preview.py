# -*- coding: utf-8 -*-
"""`preview_transform`'s two failure modes, which must not look the same.

The canvas calls this on every keystroke in the transform popover, and it has
exactly two ways to fail:

  * a ValidationError the code RAISED ON PURPOSE — divide-by-zero — whose
    message was written for a human and belongs on screen verbatim;
  * anything else, which by definition nobody anticipated. That branch used to
    return `str(e)` and write nothing anywhere: the user read a bare exception
    string beside a field name, and the server log — the one place it could
    have been diagnosed — was silent (W40: a catch that narrows nothing must
    still report).

This pins both, because the difference is invisible until the day it matters.
"""
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTransformPreview(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn = cls.env['hr.integration.connector'].create({
            'name': 'IG-C3 preview', 'connector_type': 'demo'})
        cls.mapping = cls.env['hr.integration.field.mapping'].create({
            'connector_id': conn.id, 'source_field': 'base_salary',
            'source_sample_value': '12', 'source_data_type': 'number',
        })

    def test_a_working_preview_still_works(self):
        res = self.mapping.preview_transform(
            {'transformation_type': 'divide', 'transformation_value': 4})
        self.assertTrue(res['ok'])
        self.assertEqual(res['result'], 3.0)

    def test_divide_by_zero_keeps_its_own_words(self):
        """The message is deliberate and the user caused it — it goes through
        untouched, and it is not an incident anybody should be paged about."""
        res = self.mapping.preview_transform(
            {'transformation_type': 'divide', 'transformation_value': 0})
        self.assertFalse(res['ok'])
        self.assertIn('zero', res['error'].lower())
        self.assertNotIn('exception', res)

    def test_an_unanticipated_failure_is_reported_not_recited(self):
        boom = RuntimeError('cursor already closed: 0x7f')

        with patch.object(type(self.mapping), '_apply_transform_ops',
                          side_effect=boom):
            with self.assertLogs(
                    'odoo.addons.pb_hr_payroll_formula.models'
                    '.integration_field_mapping', level='WARNING') as logs:
                res = self.mapping.preview_transform(
                    {'transformation_type': 'multiply',
                     'transformation_value': 2})

        self.assertFalse(res['ok'])
        # The user gets a sentence…
        self.assertIn('could not be previewed', res['error'])
        # …and NOT the raw exception text, which on an unanticipated failure is
        # as likely to be internal as it is to be readable.
        self.assertNotIn('cursor already closed', res['error'])
        self.assertEqual(res['exception'], 'RuntimeError')
        # …while the log has everything needed to diagnose it: the row, the
        # source field, the draft and the real message.
        line = '\n'.join(logs.output)
        self.assertIn('cursor already closed', line)
        self.assertIn('base_salary', line)
        self.assertIn(str(self.mapping.id), line)

    def test_a_validation_error_is_not_swallowed_into_the_generic_branch(self):
        """Guard against the obvious refactor: catching Exception FIRST would
        make the divide-by-zero message disappear behind the generic sentence,
        and every test above would still pass except this one."""
        with patch.object(type(self.mapping), '_apply_transform_ops',
                          side_effect=ValidationError('a sentence for a human')):
            res = self.mapping.preview_transform(
                {'transformation_type': 'multiply', 'transformation_value': 2})
        self.assertEqual(res['error'], 'a sentence for a human')
