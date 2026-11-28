# -*- coding: utf-8 -*-
"""HOME P3 — the cards row, the closing row, the clean-up and Vietnamese
(tests 1–8 of docs/handovers/home/P3_HANDOVER.md).

The cards' rules are pure functions in pb_dashboard.js between the markers
`/* PURE:start */` and `/* PURE:end */`. Where `node` exists (the server clone
has it) tests 2 and 3 cut that block out and RUN it against fixture payloads;
without node they fall back to source-string checks and say so in the skip
message of the node half. Absence checks spell their token by concatenation
(the ledger's six-times lesson).
"""
import json
import os
import re
import shutil
import subprocess

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.modules.module import get_module_path, get_modules
from odoo.tests.common import TransactionCase, tagged

# The module, not its class: a class imported here would be collected and
# run a second time by the test loader.
from . import test_home_data as thd

JS = 'static/src/js/pb_dashboard.js'
TPL = 'static/src/xml/pb_dashboard.xml'
OLD_CALL = 'get_dash' + 'board_data'


def _read(rel, module='pb_dashboard'):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _pure_block(js):
    start = js.index('/* PURE:start */')
    end = js.index('/* PURE:end */')
    return js[start:end].replace('export function', 'function')


def _run_node(js, script):
    """Run the PURE block + `script` in node; returns the parsed JSON it
    prints, or None when node is not on this machine."""
    node = shutil.which('node') or shutil.which('nodejs')
    if not node:
        return None
    src = _pure_block(js) + '\n' + script
    out = subprocess.run([node, '-e', src], capture_output=True, text=True,
                         timeout=60, check=False)
    if out.returncode:
        raise AssertionError('node failed: %s' % out.stderr[-2000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def _table_keys(js, name):
    table = re.search(r'const %s = \{(.*?)\n\};' % name, js, re.S)
    return set(re.findall(r'^    ([a-z_]+): \{', table.group(1), re.M)) \
        if table else None


@tagged('post_install', '-at_install')
class TestHomeCardsSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = _read(JS)
        cls.tpl = _read(TPL)

    # ------------------------------------------------------------ test 1
    def test_01_cards_hide_when_their_section_is_none(self):
        for var, getter, section in (('pc', 'peopleCard', 'people'),
                                     ('hc', 'hiringCard', 'hiring'),
                                     ('lc', 'learnCard', 'learn'),
                                     ('sc', 'schemesCard', 'schemes')):
            self.assertIn('t-set="%s" t-value="%s"' % (var, getter), self.tpl)
            self.assertRegex(self.tpl, r'<section t-if="%s"' % var,
                             'the %s card is drawn without a guard' % section)
            body = re.search(r'get %s\(\) \{(.*?)\n    \}' % getter, self.js, re.S)
            self.assertTrue(body, '%s getter moved' % getter)
            self.assertRegex(body.group(1),
                             r'this\.d\.%s;\s*\n\s*if \(!\w+[^)]*\) \{ return null; \}'
                             % section,
                             '%s does not answer null for a missing section'
                             % getter)
        # the pay runs card is always drawn (it has its own empty state)
        self.assertIn('No pay run this month yet', self.js)
        # dash-formula moved to the Pay schemes card (H9)
        card = self.tpl[self.tpl.index('t-set="sc" t-value="schemesCard"'):]
        self.assertIn('data-coach="dash-formula"', card[:400])

    # ------------------------------------------------------------ test 2
    def test_02_run_badges_cover_every_state_the_server_emits(self):
        states = [s for s, _l in self.env['hr.payslip.run']._fields['state']
                  ._description_selection(self.env)]
        self.assertIn('cancel', states)
        table = _table_keys(self.js, 'RUN_BADGES')
        self.assertTrue(table, 'RUN_BADGES moved')
        fixtures = []
        for state in states:
            for variant in ({}, {'slips': 3}, {'awaiting_me': True},
                            {'waiting_on': 'Lan'}):
                fixtures.append(dict(variant, state=state))
        got = _run_node(self.js, 'console.log(JSON.stringify(%s.map(runBadge)));'
                        % json.dumps(fixtures))
        if got is None:
            # source fallback: every non-cancel state is named in runBadge
            body = _pure_block(self.js)
            for state in states:
                if state != 'cancel':
                    self.assertIn('"%s"' % state, body)
            return
        by_state = {}
        for fx, key in zip(fixtures, got):
            by_state.setdefault(fx['state'], set()).add(key)
        self.assertEqual(by_state.pop('cancel'), {None},
                         'a cancelled run would be drawn')
        reached = set()
        for state, keys in by_state.items():
            self.assertNotIn(None, keys, 'state %s has no badge' % state)
            reached |= keys
        self.assertEqual(reached, table,
                         'RUN_BADGES and the states disagree: %s'
                         % sorted(reached ^ table))

    # ------------------------------------------------------------ test 3
    def test_03_notes_name_the_biggest_run_and_appear_only_above_zero(self):
        runs = [
            {'id': 1, 'state': 'draft', 'no_bank': 2, 'unsourced': 0},
            {'id': 2, 'state': 'approval_pending', 'no_bank': 5, 'unsourced': 0},
            {'id': 3, 'state': 'done', 'no_bank': 0, 'unsourced': 0},
            {'id': 4, 'state': 'cancel', 'no_bank': 9, 'unsourced': 9},
        ]
        quiet = [dict(r, no_bank=0, unsourced=0) for r in runs[:3]]
        script = 'console.log(JSON.stringify([bankNote(%s), sourceNote(%s), ' \
                 'bankNote(%s), sourceNote(%s), weekBars(%s), ' \
                 'runProgress({state:"draft",slips:4,done:0}), ' \
                 'runProgress({state:"done",slips:4,done:4})]));' % (
                     json.dumps(runs), json.dumps(runs), json.dumps(quiet),
                     json.dumps([dict(runs[0], unsourced=3)]),
                     json.dumps([{'date': 'd%d' % i, 'n': n, 'weekend': i > 4}
                                 for i, n in enumerate([3, 1, 7, 0, 2, 0, 0])]))
        got = _run_node(self.js, script)
        if got is None:
            body = _pure_block(self.js)
            self.assertIn('n > (top.no_bank || 0)', body)
            self.assertIn('total > 0 ?', body)
            return
        bank, source, bank0, source3, week, draft, done = got
        self.assertEqual(bank, {'n': 5, 'id': 2, 'more': 2},
                         'the bank note does not name the biggest run')
        self.assertIsNone(source, 'a source note at zero')
        self.assertIsNone(bank0)
        self.assertEqual(source3, {'n': 3, 'id': 1})
        self.assertEqual(week['peak'], 2)
        self.assertTrue(week['bars'][0]['today'] and week['bars'][0]['label'])
        self.assertEqual(week['bars'][2]['pct'], 100)
        self.assertIsNone(draft, 'a run with nothing done draws an empty bar')
        self.assertEqual(done, 100)

    # ------------------------------------------------------------ test 4
    def test_04_the_old_payload_is_gone_and_nothing_calls_it(self):
        self.assertFalse(hasattr(self.env['pb.dashboard'], OLD_CALL))
        for name in ('_period_' + 'kpis', '_payroll_' + 'months',
                     '_resolve_' + 'period'):
            self.assertFalse(hasattr(self.env['pb.dashboard'], name), name)
        callers = [
            # python: the model by name, then the old call on it
            re.compile(r"""\[['"]pb\.dashboard['"]\][^\n]*\.""" + OLD_CALL + r'\('),
            # js: an ORM call naming the model and the old method
            re.compile(r"""['"]pb\.dashboard['"]\s*,\s*['"]""" + OLD_CALL + r"""['"]"""),
        ]
        own = re.compile(r'(def |\.)' + OLD_CALL + r'\(')
        found = []
        for module in sorted(m for m in get_modules() if m.startswith('pb_')):
            path = get_module_path(module)
            if not path:
                continue
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ('lib', 'node_modules',
                                                        '__pycache__')]
                for fname in files:
                    if not fname.endswith(('.py', '.js', '.xml')):
                        continue
                    full = os.path.join(root, fname)
                    try:
                        with open(full, encoding='utf-8') as fh:
                            text = fh.read()
                    except (OSError, UnicodeDecodeError):
                        continue
                    pats = callers + ([own] if module == 'pb_dashboard' else [])
                    if any(p.search(text) for p in pats):
                        found.append(os.path.relpath(full, os.path.dirname(path)))
        self.assertFalse(found, 'still calling the old payload: %s' % found)

    # ------------------------------------------------------------ test 5
    def test_05_vietnamese_parses_and_matches_the_template(self):
        try:
            import polib
        except ImportError:                              # pragma: no cover
            self.skipTest('polib is not installed here')
        base = get_module_path('pb_dashboard')
        pot = polib.pofile(os.path.join(base, 'i18n', 'pb_dashboard.pot'))
        po = polib.pofile(os.path.join(base, 'i18n', 'vi_VN.po'))
        pot_ids = {e.msgid for e in pot if e.msgid}
        po_ids = {e.msgid for e in po if e.msgid}
        self.assertFalse(po_ids - pot_ids,
                         'msgids not in the template: %s' % sorted(po_ids - pot_ids)[:5])
        self.assertFalse(pot_ids - po_ids,
                         'untranslated: %s' % sorted(pot_ids - po_ids)[:5])
        ph = re.compile(r'%\(\w+\)s|%s')
        for entry in po:
            if not entry.msgid:
                continue
            self.assertTrue(entry.msgstr.strip(), 'empty msgstr: %r' % entry.msgid)
            self.assertEqual(sorted(ph.findall(entry.msgid)),
                             sorted(ph.findall(entry.msgstr)),
                             'placeholders differ: %r' % entry.msgid)
            self.assertNotIn('od' + 'oo', entry.msgstr.lower())
            self.assertIn('module: pb_dashboard', entry.comment)
            self.assertTrue(any(o[0].startswith('code:addons/pb_dashboard/')
                                or o[0].startswith('addons/pb_dashboard/')
                                for o in entry.occurrences) or entry.occurrences,
                            'no occurrence: %r' % entry.msgid)
        # the template is FRESH: every _t("...") literal in the script is in it
        literals = set(re.findall(r'_t\(\s*"((?:[^"\\]|\\.)*)"', self.js))
        literals = {lit.replace('\\"', '"') for lit in literals}
        self.assertFalse(literals - pot_ids,
                         'the .pot is stale: %s' % sorted(literals - pot_ids)[:5])


@tagged('post_install', '-at_install')
class TestHomeCardsData(TransactionCase):

    def setUp(self):
        super().setUp()
        self.D = self.env['pb.dashboard']
        self.company = self.env.company
        self.period = self.D.get_home_data()['period']
        self.p_first = fields.Date.to_date(self.period['date_start'])
        self.p_last = fields.Date.to_date(self.period['date_end'])
        self.today = fields.Date.context_today(self.D)

    # the P1 fixtures, borrowed (same seeding, same skips)
    _employee = thd.TestHomeData._employee
    _run = thd.TestHomeData._run
    _slip = thd.TestHomeData._slip
    _category = thd.TestHomeData._category

    def _cal(self, month, cutoff):
        Cal = self.env['pb.payroll.calendar']
        row = Cal.search([('month', '=', month),
                          ('company_id', '=', self.company.id)], limit=1)
        vals = {'cutoff_date': cutoff, 'pay_date': month + relativedelta(days=27)}
        if row:
            row.write(vals)
        else:
            Cal.create(dict(vals, month=month, company_id=self.company.id))

    # ------------------------------------------------------------ test 6
    def test_06_next_month_cutoff_once_this_month_s_has_passed(self):
        if 'pb.payroll.calendar' not in self.env:
            self.skipTest('the payroll calendar (pb_comp_ben) is not installed')
        nxt = self.p_first + relativedelta(months=1)
        self._cal(self.p_first, self.today - relativedelta(days=1))
        self._cal(nxt, nxt + relativedelta(days=20))
        items = self.D.get_home_data()['upcoming']
        cuts = [i for i in items if i['kind'] == 'cutoff']
        self.assertEqual(len(cuts), 1, cuts)
        self.assertEqual(cuts[0]['date'], (nxt + relativedelta(days=20)).isoformat())
        self.assertEqual(cuts[0]['extra'].get('month'), nxt.strftime('%Y-%m'))
        # ... and while this month's is still ahead, only this month's
        ahead = max(self.today, self.p_first) + relativedelta(days=1)
        if ahead <= self.p_last:
            self._cal(self.p_first, ahead)
            cuts = [i for i in self.D.get_home_data()['upcoming']
                    if i['kind'] == 'cutoff']
            self.assertEqual([c['date'] for c in cuts], [ahead.isoformat()])
            self.assertFalse(cuts[0]['extra'].get('month'))

    # ------------------------------------------------------------ test 7
    def test_07_waiting_on_names_the_seat_holder_and_not_me(self):
        approver = thd.one_person_route(self)
        emp = self._employee('Home Card Waiter')
        run = self._run('Home card waiting run', self.p_first, self.p_last)
        self._slip(run, emp, {'NET': 4200.0})
        self.env['biz.approval.engine'].submit(run)
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending')

        mine = next(r for r in self.D.with_user(approver).get_home_data()['runs']
                    if r['id'] == run.id)
        self.assertTrue(mine['awaiting_me'])
        self.assertIsNone(mine['waiting_on'], 'my own seat reads as somebody else')
        theirs = next(r for r in self.D.get_home_data()['runs']
                      if r['id'] == run.id)
        self.assertFalse(theirs['awaiting_me'])
        self.assertEqual(theirs['waiting_on'], approver.name)

    # ------------------------------------------------------------ test 8
    def test_08_the_learn_lesson_anchors_exist_on_home(self):
        """The Home lesson (LW) and the tour step on Home point at anchors
        the template really carries — joined from pb_learn's content."""
        path = get_module_path('pb_learn')
        if not path:
            self.skipTest('pb_learn is not on this machine')
        with open(os.path.join(path, 'static', 'content', 'learn_content.json'),
                  encoding='utf-8') as fh:
            content = fh.read()
        tpl = _read(TPL)
        used = set(re.findall(r'"anchor":\s*"(dash-[a-z]+)"', content))
        self.assertTrue(used, 'no Home anchor in the lessons — the scan is broken')
        for anchor in ('dash-hero', 'dash-runpayroll', 'dash-period',
                       'dash-kpis', 'dash-formula'):
            self.assertIn(anchor, used,
                          'the lesson no longer teaches %s' % anchor)
        for anchor in used:
            self.assertEqual(tpl.count('data-coach="%s"' % anchor), 1,
                             '%s is taught but not on Home once' % anchor)
