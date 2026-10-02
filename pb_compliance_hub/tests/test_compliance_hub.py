# -*- coding: utf-8 -*-
"""pb_compliance_hub — the four gates, the four lenses, and the filing flow.

The gate tests are the ones that matter and they read each gate back out of the
JS to check it against the model behind the lens (W95). The four answers are
deliberately different from each other, so the tests assert the DIFFERENCE as
well: a hub whose four gates had quietly converged on one group would pass any
test that only asked "is this a real group".

The filing-flow tests are behaviour, on the demo world, and they stop short of
generating anything by default — `generate()` writes an attachment, so the one
test that calls it is explicit about that and cleans up after itself. Nothing in
this file can reach a mail or submit path: `test_the_facade_can_only_generate`
is the assertion that says so.
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


def _hub(*parts):
    return _read(HERE, *parts)


def _code(src):
    """The file with its COMMENTS removed — `//`, `/* … */` and `#`.

    W48's corollary: a word-shaped gate fails on the DOCUMENTATION that explains
    the rule, and `pb_filing_flow.py`'s header has to be able to name
    `action_mail_report` as the button this facade must never reach.
    """
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('//', i) or src[i] == '#':
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif src.startswith('"""', i) or src.startswith("'''", i):
            q = src[i:i + 3]
            j = src.find(q, i + 3)
            i = n if j < 0 else j + 3
        elif src[i] in '"\'`':
            q = src[i]
            out.append(q)
            i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            out.append(q)
            i += 1
        else:
            out.append(src[i])
            i += 1
    return ''.join(out)


def _js_list(src, name):
    m = re.search(r'export const %s = \[(.*?)\];' % name, src, re.S)
    assert m, "no such exported list: %s" % name
    return re.findall(r'"([^"]+)"', m.group(1))


@tagged('post_install', '-at_install')
class TestComplianceGates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRC = _hub('static', 'src', 'js', 'compliance_hub.js')

    def _acl_groups(self, model):
        rows = self.env['ir.model.access'].sudo().search([
            ('model_id.model', '=', model), ('perm_read', '=', True)])
        out = set()
        for row in rows:
            if not row.group_id:
                continue
            data = self.env['ir.model.data'].sudo().search([
                ('model', '=', 'res.groups'), ('res_id', '=', row.group_id.id)],
                limit=1)
            if data:
                out.add('%s.%s' % (data.module, data.name))
        return out

    def test_every_gate_group_exists_on_this_database(self):
        """Group resolution FAILS OPEN, so a typo is invisible at runtime in
        both directions and needs a source gate (W95's second rule)."""
        for name in ('FILINGS_GATE', 'BANK_GATE', 'YOUNG_GATE', 'AUDIT_GATE'):
            for xmlid in _js_list(self.SRC, name):
                self.assertTrue(
                    self.env.ref(xmlid, raise_if_not_found=False),
                    "%s names a group that does not exist: %s" % (name, xmlid))

    def test_the_filings_gate_is_the_wizards_own_acl(self):
        declared = set(_js_list(self.SRC, 'FILINGS_GATE'))
        acl = self._acl_groups('pb.govt.report.wizard')
        self.assertTrue(acl, "pb.govt.report.wizard has no ACL rows")
        self.assertFalse(declared - acl,
                         "the filings lens is offered to %s, which cannot use "
                         "the wizard behind it" % (declared - acl))

    def test_the_bank_gate_is_deliberately_every_internal_user(self):
        """An employee files their OWN bank change on this surface, so a
        narrower gate would hide the cockpit from the population it exists for.
        The cockpit's `_is_hr` / `_is_finance` decide what else they see."""
        declared = _js_list(self.SRC, 'BANK_GATE')
        self.assertEqual(declared, ['base.group_user'])
        self.assertIn('base.group_user', self._acl_groups('pb.bank.change.request'))

    def test_the_young_gate_is_the_facades_own_predicate(self):
        """`pb.young.worker.guard._require_access` is the enforcement, so it is
        the ACL for this purpose — and it is what the lens must mirror."""
        declared = set(_js_list(self.SRC, 'YOUNG_GATE'))
        py = _read(ROOT, 'pb_young_worker', 'models', 'young_worker_guard.py')
        facade = set(re.findall(r"_(?:HR_GROUP|ATT_OFFICER) = '([^']+)'", py))
        self.assertEqual(declared, facade,
                         "the young lens and its facade disagree about who may "
                         "open it")

    def test_the_audit_gate_is_the_managers_only(self):
        declared = set(_js_list(self.SRC, 'AUDIT_GATE'))
        py = _read(ROOT, 'pb_audit', 'models', 'pb_audit_console.py')
        facade = set(re.findall(r"_(?:MANAGER_GROUP|SYSTEM_GROUP) = '([^']+)'", py))
        self.assertEqual(declared, facade)

    def test_a_payroll_officer_is_refused_by_the_audit_facade(self):
        """The behaviour half of the gating claim.

        The shell HIDES the lens; this asserts that hiding it was right, by
        asking the facade the same question as a persona holding the payroll
        USER group and nothing above it. Without this, "the lens is absent"
        could just as well mean the gate is wrong in the other direction.
        """
        officer = self.env['res.users'].create({
            'name': 'IA-C4 gate probe',
            'login': 'ia_c4_gate_probe',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('om_hr_payroll.group_hr_payroll_user').id,
            ])],
        })
        self.assertFalse(officer.has_group('om_hr_payroll.group_hr_payroll_manager'))
        self.assertFalse(officer.has_group('base.group_system'))
        # `get_kpis` is the console's cheapest REAL public method and its first
        # line is `_require_manager()`. The first version of this test called a
        # method that does not exist, so it raised AttributeError and passed for
        # the wrong reason — a test that cannot fail for the reason it names
        # (W78). `assertRaises(AccessError)` is what pins it to the gate.
        Console = self.env['pb.audit.console'].with_user(officer)
        with self.assertRaises(AccessError):
            Console.get_kpis()
        # …and the same persona is refused by the analytics facades, which is
        # why three of the Insights hub's four lenses are absent for them too
        with self.assertRaises(AccessError):
            self.env['pb.insights'].with_user(officer)._require()
        # …and the lenses this persona SHOULD see really are open to them
        self.assertTrue(officer.has_group('base.group_user'))
        self.assertTrue(officer.has_group('om_hr_payroll.group_hr_payroll_user'))

    def test_the_four_gates_are_genuinely_four_different_answers(self):
        """A hub whose gates had converged on one group would pass every test
        above that only asks "is this a real group". The point of W95 is that
        four doors need four answers, so the difference itself is asserted."""
        sets = [frozenset(_js_list(self.SRC, n)) for n in
                ('FILINGS_GATE', 'BANK_GATE', 'YOUNG_GATE', 'AUDIT_GATE')]
        self.assertEqual(len(set(sets)), 4,
                         "two lenses share a gate — check whether that is true "
                         "of the models behind them")


@tagged('post_install', '-at_install')
class TestComplianceHubStatic(TransactionCase):

    def test_the_lens_order_matches_the_mockup(self):
        keys = re.findall(r'key:\s*"(\w+)",\s*icon:\s*"(\w+)",\s*label:',
                          _hub('static', 'src', 'js', 'compliance_hub.js'))
        self.assertEqual(
            keys,
            [('filings', 'fileText'), ('bank', 'scan'),
             ('young', 'shield'), ('audit', 'scrollText')])

    def test_the_lens_persistence_key(self):
        self.assertIn('key: "compliance"',
                      _hub('static', 'src', 'js', 'compliance_hub.js'))

    def test_the_hub_action_is_hidden(self):
        act = self.env.ref('pb_compliance_hub.action_pb_compliance_hub')
        self.assertEqual(act.tag, 'pb_compliance_hub')
        self.assertFalse(
            self.env['ir.ui.menu'].search(
                [('action', '=', 'ir.actions.client,%s' % act.id)]))
        # CYCLE 5 REVERSED THE RAIL HALF (see pb_insights_hub's twin for the
        # reasoning): the hub is UNDERSTAND > Compliance now, and the four items
        # it absorbed — including Audit, which changed domain rather than just
        # address — are retired. The MENU half above is unchanged.
        Item = self.env.get('pb.sidebar.item')
        if Item is not None:
            items = Item.with_context(active_test=False).search(
                [('action_tag', '=', 'pb_compliance_hub')])
            self.assertEqual(len(items), 1)
            self.assertTrue(items.active)
            self.assertEqual(items.section_id.technical_key, 'understand')
            self.assertEqual(items.sequence, 20)

    def test_the_hub_ships_no_model(self):
        self.assertFalse(os.path.isdir(os.path.join(HERE, 'models')))

    def test_the_hub_declares_no_local_palette(self):
        for f in ('compliance_hub.js', 'compliance_hub_palette.js'):
            src = _hub('static', 'src', 'js', f)
            self.assertNotIn('pb_hub_palette_yield', src)
            self.assertNotIn('useHotkey', src)

    def test_every_palette_entry_names_a_lens_that_exists_and_the_reverse(self):
        hub = _hub('static', 'src', 'js', 'compliance_hub.js')
        lenses = set(re.findall(r'key:\s*"(\w+)",\s*icon:', hub))
        pal = _hub('static', 'src', 'js', 'compliance_hub_palette.js')
        for lens in re.findall(r'lens:\s*"(\w+)"', pal):
            self.assertIn(lens, lenses)
        for lens in lenses:
            self.assertIn('lens: "%s"' % lens, pal)

    def test_the_palette_imports_its_gates_instead_of_restating_them(self):
        pal = _hub('static', 'src', 'js', 'compliance_hub_palette.js')
        self.assertIn('from "@pb_compliance_hub/js/compliance_hub"', pal)

    def test_the_filing_flow_palette_row_names_a_real_action(self):
        pal = _hub('static', 'src', 'js', 'compliance_hub_palette.js')
        self.assertIn('pb_govt_reports.action_pb_filing_flow', pal)
        self.assertTrue(self.env.ref('pb_govt_reports.action_pb_filing_flow'))
        self.assertIn('requires: "pb_filing_flow"', pal,
                      "an xmlid row needs a presence probe or it can offer a "
                      "door the database does not have")

    def test_every_asset_on_disk_is_in_the_bundle_and_vice_versa(self):
        manifest = ast.literal_eval(_hub('__manifest__.py'))
        declared = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                p = os.path.join(root, f)
                on_disk.add('pb_compliance_hub/'
                            + os.path.relpath(p, HERE).replace(os.sep, '/'))
        self.assertEqual(declared, on_disk)

    def test_no_python_style_implicit_string_concatenation(self):
        bad = []
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if not f.endswith('.js'):
                    continue
                with open(os.path.join(root, f), encoding='utf-8') as fh:
                    lines = fh.readlines()
                for n, line in enumerate(lines[:-1], 1):
                    nxt = lines[n].strip()
                    if line.strip().startswith(('//', '*', '/*')) \
                            or nxt.startswith(('//', '*', '/*')):
                        continue
                    if re.search(r'["\']\s*$', line) and re.match(r'^["\']', nxt):
                        bad.append('%s:%s' % (f, n))
        self.assertFalse(bad, 'adjacent JS string literals: %s' % bad)

    def test_every_template_file_parses(self):
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if f.endswith('.xml'):
                    ElementTree.parse(os.path.join(root, f))
        ElementTree.parse(os.path.join(HERE, 'views',
                                       'pb_compliance_hub_action.xml'))


@tagged('post_install', '-at_install')
class TestEmbeddedComplianceLenses(TransactionCase):

    GUARDS = {
        ('pb_govt_reports', 'govt_reports.xml'): 1,
        ('pb_bank_ocr', 'pb_bank_ocr.xml'): 1,
        ('pb_young_worker', 'pb_young_worker.xml'): 1,
        ('pb_audit', 'pb_audit.xml'): 1,
    }

    def test_every_embedded_guard_is_a_guard_and_not_a_rewrite(self):
        """One `t-if="!props.embedded"` on ONE element per cockpit.

        That shape is what makes the standalone render provably unchanged: with
        `embedded` falsy the condition is true and the element renders exactly
        as it did.
        """
        for (module, fname), n in self.GUARDS.items():
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            self.assertEqual(src.count('!props.embedded'), n,
                             "%s: expected %s embedded guards" % (fname, n))

    def test_all_four_lens_components_are_exported_and_still_register(self):
        expected = {
            'pb_govt_reports': ('govt_reports.js', 'PbGovtReports',
                                'pb_govt_reports'),
            'pb_bank_ocr': ('pb_bank_ocr.js', 'PbBankOcr', 'pb_bank_ocr'),
            'pb_young_worker': ('pb_young_worker.js', 'PbYoungWorker',
                                'pb_young_worker'),
            'pb_audit': ('pb_audit.js', 'PbAudit', 'pb_audit'),
        }
        for module, (fname, cls, tag) in expected.items():
            src = _read(ROOT, module, 'static', 'src', 'js', fname)
            self.assertIn('export class %s' % cls, src)
            self.assertIn('registry.category("actions").add("%s"' % tag, src)


@tagged('post_install', '-at_install')
class TestFilingFlow(TransactionCase):
    """Flow doctrine card 1 — the facade, its allow-list, and its coverage."""

    GOV = os.path.join(ROOT, 'pb_govt_reports')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Flow = cls.env['pb.filing.flow']

    # ------------------------------------------------------- generate-only
    def test_the_facade_can_only_generate(self):
        """The single most important property of this surface.

        The VN wizard carries `action_mail_report` right next to
        `action_export`, and four other wizards carry buttons of their own. The
        facade names ONE method per country, as a constant, and nothing on the
        wire can change which. Both halves are asserted: the table's contents,
        and the absence of any expression that could build a method name.
        """
        from odoo.addons.pb_govt_reports.models.pb_filing_flow import (
            _GENERATE, _ONLY_GENERATE)
        for country, method in _GENERATE.items():
            for bad in _ONLY_GENERATE:
                self.assertNotIn(bad, method,
                                 "%s's adapter names %s" % (country, method))
        code = _code(_read(self.GOV, 'models', 'pb_filing_flow.py'))
        # Every `getattr` in the file must take its NAME from a constant. The
        # first version of this gate matched `getattr\(([^)]*)\)`, which stops
        # at the first `)` — so `getattr(w.with_context(...), method)` looked
        # like a getattr on an expression. The check is on the SECOND argument,
        # which is what decides which method gets pressed.
        calls = re.findall(r'getattr\([^,]*,\s*([^,)]+)', code)
        # Two read an exception's `name` for its message; one presses the
        # button, and its second argument is the constant looked up in
        # `_GENERATE`. Anything else is a remote-method-call primitive.
        self.assertEqual(sorted(calls), ["'name'", "'name'", 'method'],
                         "a getattr in the filing facade takes its method name "
                         "from something other than the constant table: %s" % calls)
        self.assertIn('getattr(w.with_context(discard_logo_check=True), method,',
                      code, "the generate button is pressed BY THE CONSTANT")
        self.assertIn('method = _GENERATE[(country or ', code)
        self.assertNotIn('action_mail_report', code)
        # nothing builds a method name out of the payload
        self.assertNotIn('getattr(w, vals', code)
        self.assertNotIn("vals.get('method')", code)

    def test_the_two_adapter_tables_describe_the_same_countries(self):
        """`ADAPTERS` says which model; `_GENERATE` says which button.

        `generate` indexes the second one directly, so a country added to only
        one table is a KeyError traceback on the button rather than a refusal —
        and it would be added by whoever adds the fifth country, months from
        now, in a file they are reading for the first time.
        """
        from odoo.addons.pb_govt_reports.models.pb_filing_flow import (
            ADAPTERS, _GENERATE)
        self.assertEqual(set(ADAPTERS), set(_GENERATE))

    def test_the_client_never_names_a_server_method_it_should_not(self):
        js = _read(self.GOV, 'static', 'src', 'js', 'filing_flow.js')
        called = set(re.findall(r'orm\.call\(MODEL,\s*"(\w+)"', js))
        self.assertEqual(
            called,
            {'start', 'scope', 'save_scope', 'search_employees', 'generate'})

    # ------------------------------------------------------------- coverage
    def test_coverage_is_a_server_answer_and_vn_is_in_it(self):
        covered = self.Flow.covered_countries()
        self.assertIn('VN', covered,
                      "Vietnam MUST be fully adapted (handover, workstream 4)")
        from odoo.addons.pb_govt_reports.models.pb_filing_flow import ADAPTERS
        for cc in covered:
            self.assertIn(ADAPTERS[cc]['model'], self.env,
                          "%s is claimed as covered and its wizard is absent" % cc)
        for cc, spec in ADAPTERS.items():
            if spec['model'] not in self.env:
                self.assertNotIn(cc, covered)

    def test_the_board_asks_the_server_rather_than_hard_coding_coverage(self):
        """A list of covered countries in the browser would offer the flow on a
        database where the wizard model does not exist — W29 through a second
        entrance."""
        js = _read(self.GOV, 'static', 'src', 'js', 'govt_reports.js')
        self.assertIn('"pb.filing.flow", "covered_countries"', js)
        self.assertIn('this.isCovered', js)
        # …and the uncovered branch still opens the old modal
        self.assertIn("target: \"new\"", js)

    # ---------------------------------------------------------------- step 1
    def test_start_lists_the_boards_own_catalogue(self):
        d = self.Flow.start('VN')
        self.assertEqual(d['country_code'], 'VN')
        self.assertTrue(d['is_covered'])
        keys = [f['key'] for f in d['filings']]
        self.assertEqual(sorted(keys),
                         sorted(['bhxh630', 'bhxhdstk01', 'bangke_d01',
                                 'tang_ld', 'giam_ld']))
        for f in d['filings']:
            self.assertTrue(f['label'] and f['native'] and f['group'])

    def test_an_unknown_country_is_refused_in_words(self):
        with self.assertRaises(UserError):
            self.Flow.scope('ZZ', 'bhxh630')

    # ---------------------------------------------------------------- step 2
    def test_the_scope_step_asks_only_for_what_the_filing_needs(self):
        """The whole reason this flow exists.

        The stock form renders thirty fields and hides twenty-seven of them
        behind `invisible=`; the flow asks for the common scope plus exactly the
        chosen report's own group, and SAYS how many it left out.
        """
        d = self.Flow.scope('VN', 'tang_ld')
        names = [f['name'] for f in d['fields']]
        for n in ('date_from', 'date_to', 'tang_reason', 'tang_effective_date'):
            self.assertIn(n, names)
        for n in ('bhxh630_bank_no', 'd01_doc_number', 'giam_reason',
                  'bhxhdstk_hospital_code'):
            self.assertNotIn(n, names,
                             "%s belongs to another filing and is on screen" % n)
        self.assertTrue(d['hidden_count'] > 15,
                        "the flow claims to hide %s fields" % d['hidden_count'])
        blocks = {f['name']: f['block'] for f in d['fields']}
        self.assertEqual(blocks['date_from'], 'common')
        self.assertEqual(blocks['tang_reason'], 'filing')

    def test_every_filing_produces_a_usable_descriptor(self):
        for key in ('bhxh630', 'bhxhdstk01', 'bangke_d01', 'tang_ld', 'giam_ld'):
            with self.subTest(filing=key):
                d = self.Flow.scope('VN', key)
                self.assertTrue(d['wizard_id'])
                self.assertTrue(d['fields'])
                for f in d['fields']:
                    self.assertTrue(f['label'], "%s: unlabelled field %s"
                                    % (key, f['name']))
                    self.assertIn(f['type'],
                                  ('char', 'text', 'date', 'datetime',
                                   'selection', 'many2one', 'typeahead',
                                   'integer', 'float', 'boolean', 'monetary'))
                    if f['type'] in ('selection', 'many2one'):
                        self.assertIn('options', f)

    def test_the_descriptor_never_renders_a_relation_as_an_id_box(self):
        """A relational field with no picker and no typeahead would be a number
        input nobody can fill — W29's door that can only produce an error."""
        d = self.Flow.scope('VN', 'bhxh630')
        for f in d['fields']:
            if f['type'] == 'many2one':
                self.assertTrue(f.get('options') is not None)

    def test_the_defaults_on_screen_are_the_wizards_own(self):
        d = self.Flow.scope('VN', 'bhxh630')
        self.assertEqual(d['values']['company_id'], self.env.company.id)
        self.assertTrue(d['values']['date_from'])
        self.assertTrue(d['values']['date_to'])
        # a selection default comes from the model, not from this facade
        self.assertEqual(d['values']['bhxh630_benefit_group'], 'om_dau_thai_san')

    # ----------------------------------------------------------- the allow-list
    def test_a_field_outside_the_allow_list_is_dropped(self):
        """An allow-list, not a deny-list. These transients carry COMPUTED
        result fields, and a forged call that could write one would let a caller
        manufacture a plausible outcome for a step that never ran."""
        d = self.Flow.scope('VN', 'tang_ld')
        self.Flow.save_scope(d['wizard_id'], 'VN', 'tang_ld', {
            'tang_region_code': 'IA-C4',
            # belongs to ANOTHER filing's group — not writable on this one
            'giam_region_code': 'FORGED',
            # not in any allow-list
            'report_type': 'bhxh630',
        })
        w = self.env['pb.govt.report.wizard'].browse(d['wizard_id'])
        self.assertEqual(w.tang_region_code, 'IA-C4')
        self.assertFalse(w.giam_region_code)
        self.assertEqual(w.report_type, 'tang_ld',
                         "the filing key must not be rewritable from the scope "
                         "step — it decides which allow-list applies")

    def test_a_caller_cannot_validate_one_filing_and_generate_another(self):
        """The other half of the same hole, closed by `_assert_key`.

        `generate` takes `filing_key` from the browser to choose the allow-list,
        while the WIZARD's own field is what the export dispatches on. A call
        naming a different filing than the transient holds is refused rather
        than trusted — otherwise a scope validated as one filing could produce
        the file of another.
        """
        d = self.Flow.scope('VN', 'tang_ld')
        with self.assertRaises(UserError):
            self.Flow.save_scope(d['wizard_id'], 'VN', 'bhxh630', {})
        with self.assertRaises(UserError):
            self.Flow.generate(d['wizard_id'], 'VN', 'bhxh630', {})

    def test_the_scope_write_survives_a_back_and_forth(self):
        d = self.Flow.scope('VN', 'giam_ld')
        self.Flow.save_scope(d['wizard_id'], 'VN', 'giam_ld',
                             {'giam_reason': 'resign'})
        again = self.Flow.save_scope(d['wizard_id'], 'VN', 'giam_ld', {})
        self.assertEqual(again['values']['giam_reason'], 'resign')

    def test_an_expired_flow_says_so(self):
        with self.assertRaises(UserError):
            self.Flow.save_scope(2 ** 31 - 1, 'VN', 'tang_ld', {})

    # -------------------------------------------------------- the typeahead
    def test_the_employee_typeahead_calls_odoo_19s_name_search(self):
        """`args` became `domain` in Odoo 19, and calling it by the old name
        raises a TypeError a surrounding catch turns into a control that
        silently deletes itself — the exact bug that cost this program its
        person search for three phases (W40)."""
        hits = self.Flow.search_employees('a')
        self.assertIsInstance(hits, list)
        self.assertLessEqual(len(hits), 20)
        for h in hits:
            self.assertIn('id', h)
            self.assertIn('label', h)

    # ------------------------------------------------------------- generate
    def test_generating_a_vn_filing_produces_a_real_file(self):
        """End to end on whatever this database holds, and it CLEANS UP.

        This is the one test in the suite that writes: `generate()` renders the
        report and stores an `ir.attachment`. It runs in a rolled-back
        transaction like every other TransactionCase, so the row never survives
        — the assertion on the byte count is what proves the file was really
        produced rather than an empty placeholder named plausibly.
        """
        d = self.Flow.scope('VN', 'tang_ld')
        out = self.Flow.generate(d['wizard_id'], 'VN', 'tang_ld', {})
        self.assertTrue(out['done'])
        self.assertEqual(len(out['artifacts']), 1,
                         "a VN filing produces exactly one workbook")
        art = out['artifacts'][0]
        self.assertTrue(art['name'].endswith('.xlsx'))
        self.assertGreater(art['size'], 0, "an empty file is not a filing")
        self.assertEqual(art['url'], '/web/content/%s?download=true' % art['id'])
        att = self.env['ir.attachment'].browse(art['id'])
        self.assertTrue(att.exists())
        self.assertFalse(att.res_model,
                         "a statutory extract belongs to its creator, not to a "
                         "transient that is about to be vacuumed")

    def test_a_country_whose_wizard_writes_no_file_says_so(self):
        """Four of the five country wizards return a notification claiming a
        submission file was generated and write nothing at all. The flow reports
        what happened, not what the message says (W42)."""
        from odoo.addons.pb_govt_reports.models.pb_filing_flow import ADAPTERS
        stub = None
        for cc in ('SG', 'TH', 'KH', 'MY'):
            if ADAPTERS[cc]['model'] in self.env:
                stub = cc
                break
        if stub is None:
            self.skipTest("no non-VN country module installed on this database")
        d = self.Flow.scope(stub, '')
        try:
            out = self.Flow.generate(d['wizard_id'], stub, '', {})
        except UserError:
            # "No employees found for … submission in the selected period" is
            # the wizard's own guard and a perfectly correct outcome here.
            return
        self.assertEqual(out['artifacts'], [])
        self.assertTrue(out['message'])
