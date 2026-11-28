# -*- coding: utf-8 -*-
"""`models.ValidationError` does not exist in Odoo 19 — the guards that used it.

Two sites in this module raised through `models.ValidationError`. `odoo.models`
exports models, fields and the ORM; it has never exported the exception classes,
and Odoo 19 removed the last of the re-exports that made this look like it
worked. So each of these guards answered a bad input with

    AttributeError: module 'odoo.models' has no attribute 'ValidationError'

instead of the sentence it was written to say. The failure only exists on the
path nobody exercises — the guard — which is why both survived: the happy path
never touches the name, so no test, no lint and no upgrade could see it.

The tests below are deliberately about the CLASS of the raised exception, not
about the message. An assertion on the words would pass on an AttributeError
carrying a plausible string, and it is the class that decides whether Odoo
renders a dialog or a traceback.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOdoo19Exceptions(TransactionCase):

    def test_the_onboarding_wizard_refuses_an_empty_vendor_in_words(self):
        """`hr.integration.onboarding.wizard.action_to_auth`'s own guard.

        `pb.integration.onboarding` (IA Cycle 3) validates BEFORE delegating and
        so never reached this line; the modal action, which is still registered,
        reaches it on every user who presses Next without choosing a system.
        """
        wiz = self.env['hr.integration.onboarding.wizard'].create({})
        self.assertFalse(wiz.connector_type)
        with self.assertRaises(ValidationError):
            wiz.action_to_auth()

    def test_a_bad_rate_table_code_is_refused_in_words(self):
        """`hr.formula.rate.table._check_code` — the second site, same defect.

        An `@api.constrains` that raises the wrong class is worse than one that
        raises nothing: the record is still rejected, so the write fails, and
        the user is shown a traceback about a missing attribute of `odoo.models`
        with nothing in it about the code they typed.
        """
        Cfg = self.env['hr.formula.config']
        cfg = Cfg.search([], limit=1)
        if not cfg:
            self.skipTest("no hr.formula.config on this database")
        with self.assertRaises(ValidationError):
            self.env['hr.formula.rate.table'].create({
                'config_id': cfg.id,
                'name': 'IA-C4 probe',
                # underscores are exactly what the constraint exists to refuse
                'code': 'BAD_CODE',
            })

    def test_neither_site_names_the_exception_on_the_models_module(self):
        """A source gate beside the behaviour tests.

        The behaviour tests above prove the two guards raise correctly TODAY.
        They cannot prove the habit is gone, and this defect is a habit: the
        name reads perfectly, the import line looks complete, and the mistake is
        invisible until the guard fires. So the files are read.
        """
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bad = []
        for root, _dirs, files in os.walk(os.path.join(here, 'models')):
            for f in files:
                if not f.endswith('.py'):
                    continue
                path = os.path.join(root, f)
                with open(path, encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        # The comments explaining this rule say the words
                        # "models" and "ValidationError" and must not fail their
                        # own gate (W48's corollary), so the needle is the
                        # ATTRIBUTE ACCESS, and only outside a comment.
                        code = line.split('#', 1)[0]
                        if 'models.ValidationError' in code or 'models.UserError' in code:
                            bad.append('%s:%s' % (f, n))
        self.assertFalse(bad, "exceptions read off the models module: %s" % bad)
