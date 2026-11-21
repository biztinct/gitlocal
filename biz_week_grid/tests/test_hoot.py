# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P7 — make the committed hoot suite mean something.

THE GAP THIS CLOSES. `static/tests/week_grid.test.js` has been in the repo since
P5 with twenty-odd cases in it, registered in `web.assets_unit_tests`. Nothing
ever ran it. `-u biz_week_grid` does not: that bundle is built only by
`/web/tests`, so the suite was compiled, served and never executed — the most
expensive kind of test, one that costs maintenance and buys nothing, and one
that reads as coverage on the way past.

Two gates, because the cheap one and the real one fail in opposite directions.

`TestHootSuiteIsWired` is a STATIC gate and it always runs. It cannot tell you
whether the assertions pass; it can tell you the suite is still declared, still
reachable, still non-empty, and still has unique case names — which covers the
ways a suite silently stops existing (a manifest edit, a moved file, a rename
that collapses two cases into one). It is deliberately not a count: pinning "22"
makes every added case a failing build.

`TestWeekGridHoot` is the REAL one and it needs a browser. It is tagged out of
the standard run on purpose:

  * `browser_js` needs a Chrome binary on the machine running the tests, and
    the deploy host does not have one. A gate that errors on every deploy is a
    gate the next person disables.
  * hoot's URL filter is a HASH of the suite descriptor. If that descriptor
    ever drifts, the filter matches nothing, hoot runs zero tests and reports
    "[HOOT] Test suite succeeded" — a green gate proving nothing at all, which
    is worse than no gate. `test_the_suite_descriptor_still_matches_the_file`
    below pins the descriptor this hash is built from so that drift is loud.

Run it explicitly:

    odoo-bin -d <db> --test-enable --test-tags /biz_week_grid:TestWeekGridHoot

or open `/web/tests` in a browser and filter to "week grid" — the ritual is in
the ledger (W75) because on this deployment the browser route is the one that
actually gets used.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

# The hoot suite's descriptor, as hoot derives it from the test file's module
# path inside `web.assets_unit_tests`. The URL filter is a hash of THIS string,
# so it is written once, here, and pinned by a test below.
_SUITE = '@biz_week_grid/../tests/week_grid.test'

_TEST_FILE = ('static', 'tests', 'week_grid.test.js')
_RE_CASE = re.compile(r'^\s*test\(\s*(["\'])(.+?)\1', re.M)


def _hoot_hash(text):
    """hoot's own 32-bit string hash (`web/tests/test_js.py::_generate_hash`),
    reproduced rather than imported because importing a test helper out of the
    `web` module's test package couples this suite to core's file layout."""
    h = 0
    for char in text:
        h = ((h << 5) - h + ord(char)) & 0xFFFFFFFF
    return '%08x' % h


def _suite_source():
    path = get_module_path('biz_week_grid')
    if not path:
        return ''
    full = os.path.join(path, *_TEST_FILE)
    if not os.path.exists(full):
        return ''
    with open(full, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestHootSuiteIsWired(TransactionCase):
    """The always-on half. Cheap, and it catches the suite DISAPPEARING."""

    def test_the_suite_file_exists_and_holds_cases(self):
        src = _suite_source()
        self.assertTrue(src, 'the hoot suite file is missing: %s'
                             % os.path.join(*_TEST_FILE))
        cases = _RE_CASE.findall(src)
        self.assertGreaterEqual(
            len(cases), 15,
            'the hoot suite has shrunk to %s cases — it covered the whole P5 '
            'redesign' % len(cases))

    def test_no_two_cases_share_a_name(self):
        """hoot addresses a case by its name. Two identical names are not a
        collision it reports — they are simply indistinguishable in a filter and
        in the output, so one of them can rot unnoticed."""
        names = _RE_CASE.findall(_suite_source())
        seen = {}
        for _q, name in names:
            seen.setdefault(name, 0)
            seen[name] += 1
        dupes = sorted(n for n, c in seen.items() if c > 1)
        self.assertFalse(dupes, 'duplicated hoot case names: %s' % dupes)

    def test_the_suite_is_declared_in_the_unit_test_bundle(self):
        """`web.assets_unit_tests` is what makes `/web/tests` able to see it. A
        suite outside that bundle is a file, not a test."""
        path = get_module_path('biz_week_grid')
        with open(os.path.join(path, '__manifest__.py'), encoding='utf-8') as fh:
            manifest = fh.read()
        self.assertIn('web.assets_unit_tests', manifest)
        self.assertIn('biz_week_grid/static/tests/', manifest)

    def test_the_suite_descriptor_still_matches_the_file(self):
        """The one that keeps the browser gate honest.

        hoot's URL filter is `&id=<hash of the descriptor>`. A descriptor that
        no longer matches any suite filters EVERYTHING out: hoot runs nothing
        and prints "Test suite succeeded". So the descriptor is derived from the
        file's real location here, and compared to the constant the runner uses.
        """
        derived = '@biz_week_grid/../%s' % '/'.join(
            _TEST_FILE[1:]).replace('.js', '')
        self.assertEqual(
            _SUITE, derived,
            'the hoot suite moved — the browser runner would filter to nothing '
            'and pass without running a single case')
        # and the hash is stable, so a silent change to the algorithm is loud
        self.assertEqual(len(_hoot_hash(_SUITE)), 8)


@tagged('-standard', 'week_grid_hoot')
class TestWeekGridHoot(HttpCase):
    """The real execution. Needs Chrome; excluded from the standard run."""

    def test_the_week_grid_hoot_suite_passes(self):
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
            '&id=%s' % _hoot_hash(_SUITE),
            "", "", login='admin', timeout=900,
            success_signal="[HOOT] Test suite succeeded")
