# -*- coding: utf-8 -*-
"""Keeping a customer's database in step with the master — ACCESS P8.

WHY THE DECISION IS A FUNCTION AND THE TEST IS OF THE FUNCTION
--------------------------------------------------------------
Same reasoning as `test_currency`: `sync_report` and `_sync_install` read and
write OTHER databases on the cluster through registries opened by hand. Nothing
about that is reachable from a suite, and a test that mocked it would only
assert that the mock was called.

So the decision — "given what the master has and what this customer has, what
should be installed and what must never be" — is a pure function, and this is a
real test of it, including the refusal in both of the two places that refuse.

WHAT THIS FILE IS REALLY GUARDING. The owner's rule is *install everything by
default*. That makes the deny-list the only thing standing between a customer's
database and the controls to the whole fleet, and a deny-list is exactly the
kind of list that rots: somebody renames a module, somebody adds a platform
module and forgets. So the tests below assert the list against the modules that
are actually on disk, and assert that the guard is applied a second time to the
literal list about to be installed — never only to the list the report showed.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from ..models.service import (TENANT_SYNC_NEVER, TENANT_SYNC_NEVER_PREFIXES,
                              sync_never_reason, sync_split)

SERVICE = 'models/service.py'

#: The rule this whole feature exists to carry out, in the owner's own words.
#: Asserted verbatim against the file, because a comment that drifts from the
#: decision it records is worse than no comment.
OWNER_RULE = (
    "From now on all tenant databases should get installed once master gets "
    "it, except anything related to the platform cockpit or anything which "
    "can interfere or be misused against the master tenant / platform "
    "functions.")


def _service_source():
    path = os.path.join(get_module_path('pb_tenants'), SERVICE)
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestTenantSyncSplit(TransactionCase):
    """The split itself."""

    def test_01_everything_the_master_has_is_offered_by_default(self):
        """The default answer is yes — that is the owner's rule."""
        master = ['pb_assets', 'pb_budget', 'pb_lifecycle', 'hr']
        tenant = ['hr']
        behind, held = sync_split(master, tenant)
        self.assertEqual(behind, ['pb_assets', 'pb_budget', 'pb_lifecycle'])
        self.assertEqual(held, [])

    def test_02_the_platform_cockpit_is_never_offered(self):
        behind, held = sync_split(['pb_tenants', 'pb_assets'], [])
        self.assertEqual(behind, ['pb_assets'])
        self.assertEqual(held, ['pb_tenants'])

    def test_03_demo_data_and_the_public_site_are_never_offered(self):
        behind, held = sync_split(
            ['pb_demo', 'pb_demo_portal', 'pb_website', 'pb_rnr'], [])
        self.assertEqual(behind, ['pb_rnr'])
        self.assertEqual(held, ['pb_demo', 'pb_demo_portal', 'pb_website'])

    def test_04_a_database_already_in_step_is_offered_nothing(self):
        behind, held = sync_split(['a', 'b'], ['a', 'b', 'c'])
        self.assertEqual(behind, [])
        self.assertEqual(held, [])

    def test_05_something_the_customer_has_and_the_master_does_not_is_left_alone(self):
        """Taking a part of the product away is never a sync."""
        behind, held = sync_split(['a'], ['a', 'their_own_thing'])
        self.assertEqual(behind, [])
        self.assertEqual(held, [])

    def test_06_a_future_platform_module_is_refused_by_default(self):
        """The prefix rail: refused without anybody remembering to add it."""
        self.assertTrue(TENANT_SYNC_NEVER_PREFIXES)
        made_up = TENANT_SYNC_NEVER_PREFIXES[0] + '_billing'
        behind, held = sync_split([made_up, 'pb_pip'], [])
        self.assertEqual(behind, ['pb_pip'])
        self.assertEqual(held, [made_up])

    def test_07_the_lists_come_back_sorted_and_never_overlap(self):
        behind, held = sync_split(
            ['pb_website', 'pb_zoho_sso', 'pb_assets', 'pb_tenants'], [])
        self.assertEqual(behind, sorted(behind))
        self.assertEqual(held, sorted(held))
        self.assertFalse(set(behind) & set(held))

    def test_08_empty_input_is_answered_not_crashed(self):
        self.assertEqual(sync_split(None, None), ([], []))
        self.assertEqual(sync_split([], ['a']), ([], []))


@tagged('post_install', '-at_install')
class TestTenantSyncReasons(TransactionCase):
    """Every refusal says why, in words the owner would use."""

    def test_09_every_never_entry_has_a_real_sentence(self):
        for name, reason in TENANT_SYNC_NEVER.items():
            self.assertGreater(
                len(reason), 60,
                "%s is refused without explaining itself" % name)
            self.assertTrue(reason.rstrip().endswith('.'),
                            "%s's reason is not a sentence" % name)

    def test_10_no_refusal_leaks_the_engineering_vocabulary(self):
        """The reason is printed on screen, so it is written for a reader.

        Matched on WHOLE WORDS. "orm" as a substring lives inside "platform",
        which is a word this feature cannot avoid using.
        """
        banned = ('odoo', 'addon', 'addons', 'manifest', 'registry', 'orm',
                  'xmlid', 'xml', 'cron', 'sql')
        for name, reason in TENANT_SYNC_NEVER.items():
            words = set(re.findall(r"[a-z]+", reason.lower()))
            for word in banned:
                self.assertNotIn(word, words,
                                 '%s\'s reason says "%s"' % (name, word))

    def test_11_a_module_outside_the_list_still_gets_a_reason(self):
        """The prefix rail has no per-module sentence; it must still answer."""
        made_up = TENANT_SYNC_NEVER_PREFIXES[0] + '_anything'
        self.assertTrue(sync_never_reason(made_up))
        self.assertNotEqual(sync_never_reason(made_up),
                            sync_never_reason('pb_tenants'))

    def test_12_the_cockpit_refuses_itself(self):
        """The one entry that can never be argued away."""
        self.assertIn('pb_tenants', TENANT_SYNC_NEVER)


@tagged('post_install', '-at_install')
class TestTenantSyncSource(TransactionCase):
    """What the file has to keep saying."""

    def test_13_the_owners_rule_is_quoted_verbatim(self):
        src = _service_source()
        # The quote is a COMMENT, so the comment markers come out before the
        # words are read — otherwise this only ever tests the line wrapping.
        stripped = '\n'.join(re.sub(r'^\s*#', '', line)
                             for line in src.splitlines())
        flat = ' '.join(stripped.split())
        self.assertIn(' '.join(OWNER_RULE.split()), flat,
                      "the rule this feature implements is no longer quoted "
                      "in the file that implements it")

    def test_14_the_install_re_checks_the_list_it_is_about_to_write(self):
        """The report's split is not the guard. The list that runs is."""
        src = _service_source()
        body = src.split('def _sync_install(self, dbname, dry_run=True):')[1]
        body = body.split('\n    def ')[0]
        self.assertIn('TENANT_SYNC_NEVER', body,
                      "_sync_install trusts the earlier split instead of "
                      "re-asking about the exact list it is about to install")
        self.assertIn('button_immediate_install', body)
        # And the re-check has to happen BEFORE anything is installed.
        self.assertLess(body.index('TENANT_SYNC_NEVER'),
                        body.index('button_immediate_install'))

    def test_15_nothing_installs_without_somebody_asking_for_it(self):
        """No cron, no upgrade hook, no auto-install path reaches the install."""
        src = _service_source()
        for cron in ('_cron_nightly_backups', '_cron_health', '_cron_certs',
                     '_warn_cert_expiry'):
            body = src.split('def %s(self' % cron)[1].split('\n    def ')[0]
            self.assertNotIn('sync_install', body,
                             "%s can install parts of the product on a "
                             "customer's database on its own" % cron)
        self.assertNotIn('sync_install', _manifest_source(),
                         "a hook in the manifest reaches the installer")

    def test_16_the_report_writes_nothing(self):
        src = _service_source()
        body = src.split('def sync_report(self):')[1].split('\n    def ')[0]
        for verb in ('.write(', '.create(', '.unlink(',
                     'button_immediate_install'):
            self.assertNotIn(verb, body,
                             'sync_report is supposed to only read, and it '
                             'contains "%s"' % verb)

    def test_17_the_master_is_never_a_target(self):
        src = _service_source()
        body = src.split('def _sync_install(self, dbname, dry_run=True):')[1]
        body = body.split('\n    def ')[0]
        self.assertIn('self.env.cr.dbname', body,
                      "_sync_install does not refuse the database it is "
                      "running on")


def _manifest_source():
    path = os.path.join(get_module_path('pb_tenants'), '__manifest__.py')
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestTenantSyncAgainstDisk(TransactionCase):
    """The deny-list has to keep naming modules that exist."""

    def test_18_every_refused_module_is_a_real_one(self):
        """A renamed module would silently fall off the deny-list."""
        Module = self.env['ir.module.module']
        for name in TENANT_SYNC_NEVER:
            self.assertTrue(
                Module.sudo().search_count([('name', '=', name)]),
                'the deny-list refuses "%s", which is not a module on this '
                'database any more' % name)

    def test_19_the_cockpit_is_refused_by_name_not_by_luck(self):
        """This module is on the list under the name it actually has."""
        self.assertIn(
            'pb_tenants', TENANT_SYNC_NEVER,
            "this module renamed itself out of its own deny-list")
