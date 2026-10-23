# -*- coding: utf-8 -*-
"""LOOK P4 §5 — the WHEN clause.

The Explorer reads as a sentence — *Show total cost By department Over month
Where …* — and one clause was missing from it. `date_from` and `date_to` have
been in the spec since the board shipped and the server has always honoured
them; there was simply no control anywhere that set either one, and the link
did not carry them either.

What these tests are about, one line each:

  W1  the period resolves on the SERVER and the payload says what it resolved
      to, in words a person would say out loud (rule 18).
  W2  every preset names the dates it actually means, on a January financial
      year AND on a July one (R5's family, on this board).
  W3  a stretch is the months it covers, and it collapses the way P3's does.
  W4  setting a period changes EVERY number, not some of them.
  W5  the strip's weights are measure-aware, and they are NOT narrowed by the
      period already chosen — a control that could only be narrowed would be a
      dead end.
  W6  a period reaches the drill and the export, and the CSV names it in its
      own content.
  W7  a malformed period is never an error and never an empty screen.
  W8  the coverage and empty-state sentences are period-aware, carry no
      bracketed plural and no stray per cent sign.
"""

import base64
import os
import re

from odoo.tests import common, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestWhenClause(common.TransactionCase):
    """The period, asked of the real facade on the real database."""

    def setUp(self):
        super().setUp()
        self.ex = self.env['pb.explorer']
        self.schema = self.ex.get_schema()

    # ---------------------------------------------------------------- W1
    def test_w1_the_period_resolves_on_the_server(self):
        """Nothing chosen is "Everything", and it says so rather than leaving
        a blank where a clause should be."""
        payload = self.ex.query({'measure': 'net', 'dimension': 'department_id'})
        period = payload['period']
        self.assertEqual(period['kind'], 'all')
        self.assertTrue(period['label'])
        self.assertIsNone(period['date_from'])
        self.assertIsNone(period['date_to'])
        self.assertEqual(period['preset'], 'all')

    def test_w1b_a_whole_month_is_called_a_month(self):
        got = self.ex._resolve_period(self.ex._clean_spec(
            {'date_from': '2026-06-01', 'date_to': '2026-06-30'}))
        self.assertEqual(got['kind'], 'month')
        self.assertEqual(got['key'], '2026-06-01..2026-06-30')
        self.assertIn('2026', got['label'])

    def test_w1c_a_part_month_still_gets_a_sentence(self):
        """An old link, or a hand-edited hash. Never an error."""
        got = self.ex._resolve_period(self.ex._clean_spec(
            {'date_from': '2026-06-12', 'date_to': '2026-07-04'}))
        self.assertEqual(got['kind'], 'days')
        self.assertIn('2026-06-12', got['label'])

    def test_w1d_one_open_end_is_a_real_answer(self):
        got = self.ex._resolve_period(self.ex._clean_spec(
            {'date_from': '2026-04-01'}))
        self.assertEqual(got['kind'], 'open')
        self.assertTrue(got['label'])
        self.assertIsNone(got['date_to'])

    # ---------------------------------------------------------------- W2
    def test_w2_every_preset_names_the_dates_it_means(self):
        presets = self.schema['periods']['presets']
        keys = [p['key'] for p in presets]
        self.assertEqual(keys, ['this_month', 'last_month', 'this_quarter',
                                'last_quarter', 'this_year', 'last_year',
                                'all'])
        for p in presets:
            self.assertTrue(p['label'], 'a preset has no name')
            self.assertTrue(p['sub'], 'a preset does not say what it means')
            if p['key'] != 'all':
                self.assertTrue(p['date_from'] and p['date_to'])
                self.assertLess(p['date_from'], p['date_to'])
        allp = [p for p in presets if p['key'] == 'all'][0]
        self.assertIsNone(allp['date_from'])
        self.assertIsNone(allp['date_to'])

    def test_w2b_a_quarter_is_three_months_and_a_year_is_twelve(self):
        by = {p['key']: p for p in self.schema['periods']['presets']}
        from datetime import date
        for key, months in (('this_quarter', 3), ('last_quarter', 3),
                            ('this_year', 12), ('last_year', 12)):
            first = date.fromisoformat(by[key]['date_from'])
            last = date.fromisoformat(by[key]['date_to'])
            span = (last.year - first.year) * 12 + (last.month - first.month) + 1
            self.assertEqual(span, months, '%s is not %s months' % (key, months))
            self.assertEqual(first.day, 1)
        # The two quarters do not overlap, and last ends where this begins.
        self.assertLess(by['last_quarter']['date_to'],
                        by['this_quarter']['date_from'])
        self.assertLess(by['last_year']['date_to'], by['this_year']['date_from'])

    def test_w2c_a_quarter_is_a_quarter_of_the_FISCAL_year(self):
        """R5's rule, on this board: on a July financial year Q1 is July to
        September, and the preset says so out loud."""
        param = self.env['ir.config_parameter'].sudo()
        before = param.get_param('pb_budget.fy_start_month')
        try:
            param.set_param('pb_budget.fy_start_month', '7')
            presets = {p['key']: p for p in self.ex._period_presets()}
            from datetime import date
            first = date.fromisoformat(presets['this_year']['date_from'])
            self.assertEqual(first.month, 7,
                             'the financial year did not move to July')
            qfirst = date.fromisoformat(presets['this_quarter']['date_from'])
            self.assertIn(qfirst.month, (7, 10, 1, 4),
                          'a fiscal quarter does not start on a quarter '
                          'boundary of a July year')
            # And back on January it is the calendar's own quarters.
            param.set_param('pb_budget.fy_start_month', '1')
            jan = {p['key']: p for p in self.ex._period_presets()}
            self.assertEqual(
                date.fromisoformat(jan['this_year']['date_from']).month, 1)
        finally:
            if before is None:
                param.search([('key', '=', 'pb_budget.fy_start_month')]).unlink()
            else:
                param.set_param('pb_budget.fy_start_month', before)

    # ---------------------------------------------------------------- W3
    def test_w3_a_stretch_of_whole_months_is_named_as_one(self):
        got = self.ex._resolve_period(self.ex._clean_spec(
            {'date_from': '2026-03-01', 'date_to': '2026-06-30'}))
        self.assertEqual(got['kind'], 'range')
        self.assertTrue(got['label'])
        self.assertNotIn('%%', got['label'])

    def test_w3b_dragged_right_to_left_is_the_same_stretch(self):
        forward = self.ex._resolve_period(self.ex._clean_spec(
            {'date_from': '2026-03-01', 'date_to': '2026-06-30'}))
        backward = self.ex._resolve_period(self.ex._clean_spec(
            {'date_from': '2026-06-30', 'date_to': '2026-03-01'}))
        self.assertEqual(forward, backward)

    # ---------------------------------------------------------------- W5
    def test_w5_the_strip_is_not_narrowed_by_what_is_already_chosen(self):
        """A month strip that showed only the months already in scope would be
        a control that can be narrowed and never widened."""
        months = self.schema['periods']['months']
        if not months:
            self.skipTest('no facts on this database')
        one = months[0]
        payload = self.ex.query({'measure': 'net', 'date_from': one['date_from'],
                                 'date_to': one['date_to']})
        self.assertEqual(sorted(payload['weights']),
                         sorted(m['key'] for m in months
                                if m['key'] in payload['weights']))
        self.assertGreaterEqual(len(payload['weights']), 1)
        if len(months) > 1:
            self.assertGreater(
                len(payload['weights']), 1,
                'choosing one month flattened the strip to that one month')

    def test_w5b_the_months_come_from_the_facts_and_are_in_order(self):
        months = self.schema['periods']['months']
        keys = [m['key'] for m in months]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), len(set(keys)))
        self.env.cr.execute(
            "SELECT DISTINCT to_char(month, 'YYYY-MM') FROM pb_fact_line "
            " WHERE company_id IN %s AND month IS NOT NULL",
            (tuple(self.env.companies.ids) or (self.env.company.id,),))
        self.assertEqual(sorted(keys),
                         sorted(r[0] for r in self.env.cr.fetchall()))
        for m in months:
            self.assertTrue(m['label'] and m['short'])
            self.assertEqual(m['date_from'][:7], m['key'])

    # ---------------------------------------------------------------- W4/W6
    def test_w4_a_period_changes_every_number_on_the_board(self):
        months = self.schema['periods']['months']
        if len(months) < 2:
            self.skipTest('fewer than two months of facts on this database')
        whole = self.ex.query({'measure': 'net', 'dimension': 'department_id'})
        one = self.ex.query({'measure': 'net', 'dimension': 'department_id',
                             'date_from': months[-1]['date_from'],
                             'date_to': months[-1]['date_to']})
        self.assertEqual(one['period']['date_from'], months[-1]['date_from'])
        self.assertLessEqual(len(one['categories']), len(whole['categories']),
                             'one month covers more buckets than every month')
        self.assertLessEqual(one['heads']['people'], whole['heads']['people'],
                             'one month counts more people than every month')
        self.assertLessEqual(one['coverage']['runs'], whole['coverage']['runs'],
                             'one month covers more pay runs than every month')

    def test_w6_the_drill_and_the_export_carry_the_period(self):
        months = self.schema['periods']['months']
        if not months:
            self.skipTest('no facts on this database')
        spec = {'measure': 'net', 'dimension': 'department_id',
                'date_from': months[-1]['date_from'],
                'date_to': months[-1]['date_to']}
        drill = self.ex.drill(spec, '_all', '_all', 0)
        self.assertTrue(drill['ok'])
        wide = self.ex.drill({'measure': 'net', 'dimension': 'department_id'},
                             '_all', '_all', 0)
        self.assertLessEqual(drill['total'], wide['total'],
                             'the drill ignored the period')
        out = self.ex.export_csv(spec)
        body = base64.b64decode(out['csv_b64']).decode('utf-8-sig')
        head = body.splitlines()[0]
        label = self.ex.query(spec)['period']['label']
        self.assertIn(label, head,
                      'the sheet does not name the period in its own content')
        self.assertIn(months[-1]['date_from'], body)
        self.assertIn(months[-1]['key'], out['filename'])

    # ---------------------------------------------------------------- W7
    def test_w7_a_malformed_period_is_never_an_error(self):
        for bad in ({'date_from': 'rubbish'},
                    {'date_to': 'nonsense'},
                    {'date_from': 'rubbish', 'date_to': 'nonsense'},
                    {'date_from': '2026-13-45', 'date_to': '2026-99-99'},
                    {'date_from': 12345, 'date_to': ['a']},
                    {'date_from': None, 'date_to': None}):
            payload = self.ex.query(dict(bad, measure='net'))
            self.assertTrue(payload['ok'])
            self.assertTrue(payload['period']['label'],
                            'a malformed period left the clause blank')
        far = self.ex.query({'measure': 'net', 'date_from': '1990-01-01',
                             'date_to': '1990-12-31'})
        self.assertTrue(far['ok'])
        self.assertEqual(far['categories'], [])
        self.assertTrue(far['period']['label'])
        self.assertIn('weights', far,
                      'an empty answer dropped the strip, so the reader can '
                      'never widen the period again')

    # ---------------------------------------------------------------- W8
    def test_w8_the_link_carries_the_period(self):
        """R7. Two short keys in the same style as the eight already there —
        without them a period set in one browser is lost the moment the link
        is shared, and the reader at the other end sees a different answer to
        the same question with no way to tell."""
        js = _read('static', 'src', 'js', 'explorer.js')
        self.assertIn('s: s.date_from || ""', js,
                      'the link does not carry the start of the period')
        self.assertIn('e: s.date_to || ""', js,
                      'the link does not carry the end of the period')
        self.assertIn('s.date_from = typeof c.s === "string"', js,
                      'a shared link is not read back into the period')
        self.assertIn('s.date_to = typeof c.e === "string"', js)

    def test_w8a_a_hand_edited_date_is_refused_before_it_reaches_a_domain(self):
        """A date that is ten characters long is not necessarily a date. Handed
        `2026-13-45` the run domain used to raise inside the PLATFORM, which is
        a five-hundred error on a screen whose contract is that a saved link is
        never an error (rule 21)."""
        for bad in ('2026-13-45', '2026-02-31', 'not-a-date', '2026/06/01',
                    '', '2026-06'):
            self.assertIsNone(self.ex._as_date(bad),
                              '%r was accepted as a date' % bad)
        self.assertEqual(self.ex._as_date('2026-06-01'), '2026-06-01')
        self.assertEqual(self.ex._as_date('2026-06-01 00:00:00'), '2026-06-01')

    def test_w8b_no_bracketed_plural_and_no_stray_per_cent_sign(self):
        """GR42/R46 — "3 pay period(s)" is how a screen announces it was
        written by a programme rather than by a person. L9 — a `_t()` handed a
        dictionary writes ONE per cent sign, so a doubled one reaches the
        screen literally."""
        for rel in (('models', 'pb_explorer.py'),
                    ('static', 'src', 'js', 'explorer.js'),
                    ('static', 'src', 'xml', 'explorer.xml')):
            body = _read(*rel)
            # A WORD followed by "(s)". Written this way so `map((s) => …)` and
            # this file's own prose about the trap are not false positives —
            # a grep that fails for saying what it is looking for is WF13.
            self.assertFalse(re.findall(r'[A-Za-z]\(s\)', body),
                             '%s carries a bracketed plural' % rel[-1])
        # L9 is a BROWSER trap: `_t()` handed a dictionary writes ONE per cent
        # sign. Python's own `_()` is `%`-formatting and genuinely needs two,
        # and this module's SQL builders use `%%s` to protect a psycopg
        # placeholder, so only the two browser files are swept.
        for rel in (('static', 'src', 'js', 'explorer.js'),
                    ('static', 'src', 'xml', 'explorer.xml')):
            self.assertNotIn('%%', _read(*rel),
                             '%s carries a doubled per cent sign' % rel[-1])

    def test_w8c_the_notices_and_the_empty_state_know_the_period(self):
        js = _read('static', 'src', 'js', 'explorer.js')
        for name in ('get pendingLine()', 'get provisionalLine()',
                     'get emptyHint()'):
            self.assertIn(name, js, '%s is gone' % name)
            block = js[js.index(name):]
            block = block[:block.index('\n    }')]
            self.assertIn('hasPeriod', block,
                          '%s does not branch on whether a period is set'
                          % name)
        xml = _read('static', 'src', 'xml', 'explorer.xml')
        self.assertIn('t-esc="pendingLine"', xml)
        self.assertIn('t-esc="provisionalLine"', xml)
        self.assertIn('t-esc="emptyHint"', xml)

    def test_w8d_the_when_clause_sits_between_over_and_where(self):
        """R5 of this phase: a period is a CLAUSE in the sentence, not a filter
        in the "Where". Its position in the rail is the whole of that."""
        xml = _read('static', 'src', 'xml', 'explorer.xml')
        over = xml.index('>Over<')
        when = xml.index('>When<')
        where = xml.index('>Where<')
        self.assertLess(over, when, 'the When clause is before Over')
        self.assertLess(when, where, 'the When clause is after Where')

    def test_w8e_everything_this_phase_moves_is_inside_the_guard(self):
        """R85. A reader who has asked for calm gets the finished board on the
        first frame, because none of these declarations is applied at all.

        This pins the WHEN clause's own motion and the chip transition it
        inherited. It deliberately does not pin the whole stylesheet: this file
        carries nineteen further moving declarations that predate this phase,
        and they are recorded as a debt in the LOOK ledger (L21) rather than
        rewritten under a period picker's commit.
        """
        scss = _read('static', 'src', 'scss', 'explorer.scss')
        guard = '@media (prefers-reduced-motion: no-preference)'
        at = scss.index(guard)
        # The guarded block runs to the end of its own brace depth.
        depth, end = 0, at
        for i in range(at, len(scss)):
            if scss[i] == '{':
                depth += 1
            elif scss[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        inside, outside = scss[at:end], scss[:at] + scss[end:]
        for selector in ('.pbex-mchip', '.pbex-mchip-fill', '.pbex-chip'):
            block = re.search(re.escape(selector) + r'\s*\{', inside)
            self.assertTrue(block, '%s has no guarded motion' % selector)
        # And the picker's own markup declares none of its own outside it.
        for chunk in re.findall(r'\.pbex-when[\w-]*\s*\{[^}]*\}', outside):
            self.assertNotIn('transition', chunk)
            self.assertNotIn('animation', chunk)
        # The one exception, on purpose: a busy spinner is not decoration, it
        # is the only thing on screen saying the board is still reading.
        self.assertIn('pbex-spin', outside)
