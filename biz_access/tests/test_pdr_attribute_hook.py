"""PDR S4 — the attribute hook's fast exit must not skip a catalogue field."""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.addons.biz_access.models.studio_catalogue import RESOURCES
from odoo.addons.biz_access.models.studio_policy import _CATALOGUE_FIELD_NAMES


@tagged('post_install', '-at_install', 'access_studio')
class TestPdrAttributeHook(TransactionCase):

    def test_every_catalogue_field_still_reaches_the_check(self):
        checked = 0
        for model, spec in RESOURCES.items():
            if model not in self.env:
                continue
            records = self.env[model]
            seen = []
            with patch.object(type(records), '_studio_attribute_check',
                              lambda rec, name, seen=seen: seen.append(name)):
                for name in spec['fields']:
                    if name in records._fields:
                        getattr(records, name)
                        self.assertIn(name, seen, '%s.%s skipped the field check' % (model, name))
                        checked += 1
                seen.clear()
                getattr(records, 'display_name')
                getattr(records, '_name')
                self.assertFalse([n for n in seen if n not in spec['fields']])
        self.assertTrue(checked)

    def test_fast_exit_set_is_the_catalogue(self):
        self.assertEqual(_CATALOGUE_FIELD_NAMES,
                         frozenset(n for spec in RESOURCES.values() for n in spec['fields']))
