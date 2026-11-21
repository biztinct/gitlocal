# -*- coding: utf-8 -*-
"""The provisioning currency decision — LEARNOS Phase 3.

WHY THE DECISION IS A FUNCTION AND THE TEST IS OF THE FUNCTION
--------------------------------------------------------------
`_step_configure` runs against a database that has just been cloned on a live
box, inside a registry opened by hand. Nothing about that is reachable from a
test suite, and pretending otherwise would produce a test that mocks the whole
step and asserts that the mock was called.

So the part that can be decided without a database was lifted out —
`currency_change(country_currency_id, company_currency_id)` — and this is a
real test of it, with every branch executed including both refusals. What is
left at the call site is two record reads and a write, and the ledger note on
the phase says plainly that THAT part is deploy-verified only.

THE BUG IT CLOSES: the golden template's company is USD and every clone
inherits it, so a Vietnamese tenant's first dashboard read "$0" on the payroll
tile. The number was honest and the money sign was not.
"""
import os

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from ..models.service import currency_change

VND, USD = 23, 2          # ids stand for themselves; the function only compares

SERVICE = 'models/service.py'


def _configure_step():
    """The `_step_configure` body, read off disk.

    NOT `inspect.getsource` on the class: importing the class pulls in half of
    Odoo's service layer, and the two assertions below are about the FILE that
    ships. Every other source-level test in this repo reads it the same way,
    which is also what lets the offline harness replay them.
    """
    path = os.path.join(get_module_path('pb_tenants'), SERVICE)
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    body = src.split('def _step_configure(self, tenant, say):')[1]
    return body.split('\n    def ')[0]


@tagged('post_install', '-at_install')
class TestProvisioningCurrency(TransactionCase):

    def test_01_a_different_country_currency_is_taken(self):
        """The case the fix exists for: a VN tenant cloned from a USD
        template."""
        self.assertEqual(currency_change(VND, USD), VND)

    def test_02_the_same_currency_is_not_a_change(self):
        """A US tenant cloned from a USD template must not have a currency line
        in its provisioning trail — that trail is what somebody reads when a
        clone goes wrong, and a line describing a write that did not happen is
        worse than no line."""
        self.assertIsNone(currency_change(USD, USD))

    def test_03_a_country_with_no_currency_leaves_the_company_alone(self):
        """A handful of `res.country` rows carry no currency. Writing that
        emptiness onto the company would clear the currency on every monetary
        field the tenant has, which is a far bigger failure than a wrong
        symbol."""
        self.assertIsNone(currency_change(False, USD))
        self.assertIsNone(currency_change(None, USD))
        self.assertIsNone(currency_change(0, USD))

    def test_04_a_company_with_no_currency_still_gets_one(self):
        """The mirror case, and it must NOT be refused: an empty company
        currency is exactly the state a currency should be written into."""
        self.assertEqual(currency_change(VND, False), VND)

    def test_05_the_call_site_activates_what_it_sets(self):
        """An INACTIVE currency on a company is a currency that appears in no
        selection and has no rate maintained — Odoo ships almost all of them
        switched off, so setting one without activating it swaps a wrong symbol
        for a broken one.

        Source-level, because the call site itself is not reachable from here.
        """
        src = _configure_step()
        self.assertIn('currency_change(', src,
                      "the configure step no longer asks for the decision")
        self.assertIn("write({'active': True})", src,
                      "the configure step sets a currency it may never "
                      "activate")

    def test_06_the_currency_write_can_never_abort_provisioning(self):
        """Its OWN write, guarded twice. Odoo raises on a currency change once
        journal items exist, so bundling currency into the rename write would
        turn a cosmetic fix into a configure-step abort (Phase-3 review
        BLOCKER-1). The currency write must: come AFTER the main write, ask
        `_existing_accounting()` first, and swallow its own failure."""
        src = _configure_step()
        self.assertNotIn("vals['currency_id']", src,
                         "the currency has crept back into the bundled write")
        self.assertIn("company.write({'currency_id': currency.id})", src)
        self.assertLess(src.index('company.write(vals)'),
                        src.index("company.write({'currency_id'"),
                        "the currency write must follow the main write")
        self.assertIn('_existing_accounting', src,
                      "the journal-items guard is gone")
        self.assertLess(src.index('_existing_accounting'),
                        src.index("company.write({'currency_id'"),
                        "the guard must be asked before the write")
        self.assertIn('Currency could not be set', src,
                      "a currency failure must log and continue, not raise")
