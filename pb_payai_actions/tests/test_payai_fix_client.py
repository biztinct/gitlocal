# -*- coding: utf-8 -*-
"""PAYAI FIX-1, cluster E — the client halves and the Approvals deep link.

  P4:link-1 / test-1  the Home hub hands its deep link to the Approvals lens;
  P4:link-3           the server says which pile a request lives in;
  P4:link-4           a gone or unreadable request answers in a sentence;
  P4:vi-13 / test-2   the card and the server fold a typed word the same way
                      (one shared table, `tests/js/word_fold_cases.json`);
  P3:crit-6, crit-7   the Remind chips and the lost-reply wording (node half);
                      a server error is "Nothing was done" (test 04 guards
                      that the engine never commits part of a call).

The browser halves run in node (`tests/js/client_fix.test.mjs`, a small loader
that runs the product's own modules with OWL stubbed). Test 02 runs it when
node is on the machine and says so when it is not; the static checks in 03
stand on their own either way.

Same rules as P1–P4: gates are judged for an explicit user (PA12); the
approval fixtures are pb_approval_config's own, reached through the module so
none of its tests run twice (PA56).
"""
import json
import os
import re
import shutil
import subprocess

from odoo.exceptions import AccessError, MissingError, UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payai_actions.payai import runner
# Reached through the module: importing the class by name here would make the
# loader collect it in this module as well (PA56).
from odoo.addons.pb_approval_config.tests import common as am

HERE = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(HERE, 'js')


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _code_only(js):
    """JS source with its comments removed (a word in a comment is not code)."""
    js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$|(?<=[;{}),])\s*//.*$', '', js)


class _Words:
    """The one thing `runner.word_ok` asks of an Action."""

    def __init__(self, words):
        self._words = words

    def confirm_words(self):
        return list(self._words)


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixClient(TransactionCase):

    # ================================================================ 01
    def test_01_the_server_folds_the_shared_table(self):
        """vi-13: the server half of the table the card is tested against."""
        with open(os.path.join(JS_DIR, 'word_fold_cases.json'), encoding='utf-8') as fh:
            table = json.load(fh)
        for row in table['fold']:
            self.assertEqual(runner._norm_word(row['in']), row['out'],
                             'server fold of %r' % row['in'])
        for row in table['match']:
            self.assertEqual(runner.word_ok(_Words(row['words']), row['typed']), row['ok'],
                             'server verdict on %r vs %s' % (row['typed'], row['words']))
        # the repro words, by name
        self.assertTrue(runner.word_ok(_Words(['APPROVE', 'DUYỆT']), 'ＤＵＹỆＴ'))
        self.assertFalse(runner.word_ok(_Words(['REJECT', 'TỪ CHỐI']), 'từ chốı'))
        self.assertFalse(runner.word_ok(_Words(['APPROVE', 'DUYỆT']), 'DUYỆT﻿'))

    # ================================================================ 02
    def test_02_the_client_halves_run_in_node(self):
        """link-1/3/4, vi-13, test-2, crit-6, crit-7 — the browser code, run."""
        node = shutil.which('node')
        if not node:
            self.skipTest('node is not installed here; run '
                          'pb_payai_actions/tests/js/client_fix.test.mjs by hand.')
        version = subprocess.run([node, '--version'], capture_output=True, text=True,
                                 check=False).stdout.strip()
        major = re.match(r'v(\d+)', version)
        if not major or int(major.group(1)) < 16:
            self.skipTest('node %s is too old for the client test (16+).' % version)
        root = os.path.dirname(get_module_path('pb_payai_actions'))
        env = dict(os.environ, PB_SRC_ROOT=root)
        out = subprocess.run(
            [node, os.path.join(JS_DIR, 'client_fix.test.mjs')],
            capture_output=True, text=True, timeout=120, env=env, check=False)
        self.assertEqual(out.returncode, 0, out.stdout[-4000:] + out.stderr[-2000:])
        self.assertRegex(out.stdout, r'\d+ passed, 0 failed')

    # ================================================================ 03
    def test_03_the_deep_link_is_wired_where_the_lens_can_read_it(self):
        """link-1 / test-1, as text — the node run above is the real proof."""
        hub = _src('pb_home_hub', 'static', 'src', 'js', 'home_hub.js')
        lens = re.search(r'\{\s*key: "approvals",[^}]*\}', hub)
        self.assertTrue(lens, 'the Approvals lens is no longer declared in home_hub.js')
        self.assertIn('wantsArrival: true', lens.group(0),
                      'the Approvals lens must ask for the hub arrival (wantsArrival)')

        inbox = _code_only(_src('pb_approval_config', 'static', 'src', 'js', 'inbox.js'))
        self.assertNotIn('currentAction', inbox,
                         'the inbox must not read the action service\'s current action: '
                         'on this version it is a Promise (P4:link-1)')
        self.assertRegex(inbox, r'arrival:\s*\{\s*type:\s*Object,\s*optional:\s*true\s*\}')
        self.assertIn('"locate_request"', inbox)

        cards = _src('pb_payai_actions', 'static', 'src', 'xml', 'cards.xml')
        self.assertIn('this.payaiChipOff(card, chip)', cards,
                      'a chip is disabled per chip (Remind), not per card (P3:crit-6)')
        self.assertNotIn('t-att-disabled="card.picked', cards)

    # ================================================================ 04
    def test_04_a_server_error_means_nothing_was_done(self):
        """crit-7 follow-on: the card tells "the server answered with an error"
        (an RPCError: rolled back, so "Nothing was done", with the reason) from
        "no answer" (the careful wording on a decision). The first is only
        true while the engine never commits part of a call on its own, so that
        is guarded here; the wording itself is run in node (test 02)."""
        root = get_module_path('pb_payai_actions')
        commits = []
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ('tests', '__pycache__', 'static')]
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding='utf-8') as fh:
                    for no, line in enumerate(fh, 1):
                        code = line.split('#', 1)[0]
                        if re.search(r'\.commit\(\)|\bnew_cursor\b|registry\([^)]*\)\.cursor\(', code):
                            commits.append('%s:%d' % (os.path.relpath(path, root), no))
        self.assertFalse(commits, 'PayAI commits part of a call on its own, so a server '
                                  'error no longer means "Nothing was done": %s' % commits)

        chat = _code_only(_src('pb_payai_actions', 'static', 'src', 'js', 'chat_patch.js'))
        self.assertIn('payaiCallFailedText(e, method, msg.card)', chat,
                      'a failed task call must be worded by payaiCallFailedText')
        self.assertRegex(chat, r'error instanceof RPCError',
                         'the wording must tell a server answer from a lost connection')


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixInboxDoor(am.MatrixCase):
    """link-3 / link-4 — the inbox facade the deep link lands on."""

    def setUp(self):
        super().setUp()
        # the seeded default route sends everything to the company's own
        # administrator; move that seat onto a person these cases can name
        # (pb_approval_config test_inbox_facade's own setUp)
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id), ('active', '=', True)])
        held.write({'user_id': self.fin.id})

    def _inbox(self, user):
        return self.Inbox.with_user(user).with_company(self.company)

    def _gone_id(self):
        self.env.cr.execute('SELECT COALESCE(MAX(id), 0) + 1000 FROM biz_approval_request')
        return self.env.cr.fetchone()[0]

    # ================================================================ 04
    def test_04_a_gone_request_answers_in_a_sentence(self):
        gone = self._gone_id()
        for scope in ('me', 'team', 'org'):
            for method in ('get_request', 'locate_request'):
                with self.assertRaises(UserError) as caught:
                    getattr(self._inbox(self.fin), method)(gone, scope)
                self.assertNotIsInstance(caught.exception, MissingError)
                self.assertEqual(caught.exception.args[0], 'That request no longer exists.',
                                 '%s(%s) as a gone id' % (method, scope))

    # ================================================================ 05
    def test_05_a_request_i_may_not_read_is_a_plain_refusal(self):
        made = self.ask()
        for method in ('get_request', 'locate_request'):
            with self.assertRaises(AccessError) as caught:
                getattr(self._inbox(self.hr), method)(made['request_id'])
            text = caught.exception.args[0]
            self.assertEqual(text, 'You cannot open this request.')
            self.assertNotIn('biz.approval', text)

    # ================================================================ 06
    def test_06_the_server_names_the_pile_a_request_is_in(self):
        made = self.ask()
        rid = made['request_id']
        self.assertEqual(self._inbox(self.fin).locate_request(rid),
                         {'id': rid, 'tab': 'mine', 'scope': 'me'})
        self.assertEqual(self._inbox(self.asker).locate_request(rid)['tab'], 'all')
        self.assertEqual(self._inbox(self.asker).locate_request(rid, 'nonsense')['scope'], 'me')

        # under "My team" it is there while it waits on my seat ...
        self.assertEqual(self._inbox(self.fin).locate_request(rid, 'team'),
                         {'id': rid, 'tab': 'mine', 'scope': 'team'})

        request = self.env['biz.approval.request'].sudo().browse(rid)
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self._inbox(self.fin).decide(rid, step.key, 'approve')
        self.assertEqual(self._inbox(self.fin).locate_request(rid)['tab'], 'done')
        # ... and once decided it is read in my own queue, where it is listed
        self.assertEqual(self._inbox(self.fin).locate_request(rid, 'team'),
                         {'id': rid, 'tab': 'done', 'scope': 'me'})
        # the pile it names is the pile that lists it
        listed = self._inbox(self.fin).list_requests('done')
        self.assertIn(rid, [c['id'] for c in listed['cards']])

        sent_back = self.ask(name='Another sign-off please')['request_id']
        request = self.env['biz.approval.request'].sudo().browse(sent_back)
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self._inbox(self.fin).decide(sent_back, step.key, 'return',
                                     'Ask your manager first, please.')
        self.assertEqual(self._inbox(self.asker).locate_request(sent_back)['tab'], 'returned')
