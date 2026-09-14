# -*- coding: utf-8 -*-
"""Z06 and Z07 — the catalogue tells the truth, and no screen says "Odoo".

Z07 asks that every catalogue row is wired up to something. It is asserted
against the ROWS the product ships rather than a number, so a row added later
either gets an adapter or shows up here by name.

Z06 is the white-label gate, and it is deliberately a REPO-WIDE grep rather
than a check of this module: the rule is that the word never reaches a user,
and the places it has escaped to before were translation files and templates
in modules nobody was thinking about at the time (ledger, standing rules). It
walks every module Phases 1-7 touched, reads every `.po` msgstr and every
shipped `.xml`/`.js` string, and fails with the file and line.
"""

import os
import re

from odoo.tests import tagged

from .common import MatrixCase

#: Every module the Approval Matrix programme has touched, P1-P7. A module in
#: this list ships approval copy, so it is a module whose words a customer
#: reads.
TOUCHED_MODULES = (
    'biz_approval_workflow', 'pb_approval_config',
    # P3-P5
    'pb_payruns', 'pb_hr_payroll_formula', 'pb_pay_delivery', 'pb_records',
    'pb_zoho_bridge', 'pb_timesheet_approval', 'pb_import_batch',
    'pb_import_wizard', 'pb_payrun_wizard', 'pb_hr_fullandfinal',
    # P6
    'pb_assets', 'pb_attendance_flow', 'pb_bank_ocr', 'pb_business_trip',
    'pb_comp_ben', 'pb_contract_lifecycle', 'pb_me_portal', 'pb_offboarding',
    'pb_pay', 'pb_rnr', 'pb_timeoff', 'pb_hr_workforce', 'pb_mission',
    'pb_team', 'biz_access', 'pb_tenancy',
    # P7
    'pb_statutory', 'pb_hr_payroll_vietnam', 'pb_formula_studio',
    'pb_scheme_map', 'pb_group', 'pb_budget', 'pb_tenants', 'pb_demo',
    'pb_demo_seed', 'pb_probation', 'pb_pip', 'pb_lifecycle',
    'pb_people_advanced', 'pb_close', 'pb_govt_reports',
)

#: Where the word is a technical identifier and must NOT be rewritten: an
#: import, a module name, an xml id, a log line, a comment, a path. The rule
#: is about strings a person READS on a screen.
CODE_SUFFIXES = ('.py', '.md', '.txt', '.rst', '.cfg', '.yml', '.yaml',
                 '.json', '.pot')

#: A `.po` header carries "Odoo Server 19.0" in `Project-Id-Version`, which is
#: a real msgstr (ledger AM29). Lines matched by these are reported.
PO_MSGSTR = re.compile(r'^msgstr\s+"(.*)"\s*$')
PO_CONT = re.compile(r'^"(.*)"\s*$')

#: The word, whole and capitalised — how a READER would ever see it.
WORD_ODOO = re.compile(r'\bOdoo\b')
XML_COMMENT = re.compile(r'<!--.*?-->', re.S)
BLOCK_COMMENT = re.compile(r'/\*.*?\*/', re.S)

#: The framework's own vocabulary, which nobody reads: an import path, a
#: module declaration, a backend URL in a developer note.
SAFE_TOKENS = ('@odoo-module', '@odoo/', 'odoo.define', 'odoo.addons',
               'window.odoo', '"odoo"', "'odoo'", '/odoo/action-',
               'odoo.com/documentation')


def _repo_root():
    """The addons root, found from this file rather than from a setting."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


@tagged('post_install', '-at_install')
class TestP7Matrix(MatrixCase):

    # ================================================================ Z07
    def test_z07a_every_wired_up_adapter_owns_its_catalogue_row(self):
        """A row is pointed at its record by the ADAPTER's own seed (AM45).

        Asserted from the registry rather than from a count: on a database
        where only this module is installed most rows correctly name nothing,
        because the module that would point them at a record is not there.
        What must never happen is the other way round — an adapter in the
        registry whose row still names nothing, or names something else.
        """
        Process = self.env['biz.approval.process'].sudo()
        wrong = []
        for name in list(self.env.registry.models):
            model = self.env[name]
            key = getattr(model, '_approval_process_key', None)
            if not key or not hasattr(model, '_approval_seed_default'):
                continue
            row = Process._by_key(key)
            if not row:
                wrong.append('%s: no "%s" row in the catalogue' % (name, key))
            elif row.model_name and row.model_name != name:
                wrong.append('%s: the "%s" row names %s'
                             % (name, key, row.model_name))
        self.assertFalse(wrong, '\n'.join(wrong))

    def test_z07b_the_seven_areas_are_all_there(self):
        areas = set(self.env['biz.approval.process'].sudo().search(
            []).mapped('area'))
        for area in ('pay', 'money', 'data', 'people', 'time', 'setup',
                     'platform'):
            self.assertIn(area, areas)

    def test_z07c_the_p7_rows_exist_and_name_their_model(self):
        expected = {
            'statutory': 'pb.statutory.proposal',
            'bands': 'pb.bands.proposal',
            'fx': 'pb.fx.proposal',
            'schememap': 'pb.schememap.proposal',
            'mappings': 'pb.mapping.proposal',
            'tenant': 'pb.tenant.proposal',
            'demo': 'pb.demo.proposal',
            'verdict': 'pb.verdict.proposal',
            'letters': 'pb.hr.letter',
            'newhire': 'pb.newhire.proposal',
            'unlock': 'pb.unlock.proposal',
            'fnf': 'hr.full.final.settlement',
            'month': 'pb.month.proposal',
            'filing': 'pb.filing.proposal',
        }
        Process = self.env['biz.approval.process'].sudo()
        for key, model in expected.items():
            row = Process._by_key(key)
            self.assertTrue(row, 'the catalogue has lost the "%s" row' % key)
            if row.model_name:
                self.assertEqual(
                    row.model_name, model,
                    '"%s" should point at %s' % (key, model))

    def test_z07d_the_two_new_responsibilities_exist(self):
        Role = self.env['biz.approval.role'].sudo()
        for key in ('finance_controller', 'platform_owner'):
            self.assertTrue(Role.search([('key', '=', key)], limit=1),
                            'the "%s" responsibility is missing' % key)

    def test_z07e_the_matrix_still_answers(self):
        payload = self.as_admin('pb.approval.matrix').get_matrix(False)
        self.assertTrue(payload['areas'])
        rows = [r for area in payload['areas'] for r in area['rows']]
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row['status'], ('live', 'draft', 'needs', 'soon'))

    # ================================================================ Z06
    def test_z06a_no_po_msgstr_anywhere_says_odoo(self):
        """A translation is a string a person reads. The rule binds it."""
        bad = []
        for module in TOUCHED_MODULES:
            folder = os.path.join(_repo_root(), module, 'i18n')
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if not name.endswith('.po'):
                    continue
                bad.extend(self._scan_po(os.path.join(folder, name)))
        self.assertFalse(bad, 'the vendor name reaches a reader here:\n%s'
                              % '\n'.join(bad))

    def test_z06b_no_shipped_template_or_script_says_odoo(self):
        """Every `.xml`, `.js` and `.scss` a browser is served.

        THE RULE IS ABOUT THE WORD A PERSON READS, so the scan is
        case-sensitive on the whole word "Odoo". A lowercase `odoo` in code is
        an identifier — a css class, a provenance key, an import path — and
        the standing rule says explicitly never to rewrite one.

        Comments are stripped first, across lines, because an engineer's note
        about Odoo 19's own behaviour is exactly the kind of sentence the rule
        protects rather than forbids. `static/tests/` is skipped: those files
        are never served to a browser, and two of them assert this very rule.
        """
        bad = []
        for module in TOUCHED_MODULES:
            root = os.path.join(_repo_root(), module)
            if not os.path.isdir(root):
                continue
            for folder, _dirs, files in os.walk(root):
                if '__pycache__' in folder or os.sep + 'i18n' in folder \
                        or os.sep + 'tests' in folder:
                    continue
                for name in sorted(files):
                    if not name.endswith(('.xml', '.js', '.scss')):
                        continue
                    bad.extend(self._scan_markup(os.path.join(folder, name)))
        self.assertFalse(bad, 'the vendor name reaches a reader here:\n%s'
                              % '\n'.join(bad))

    # ------------------------------------------------------------ scanners
    def _scan_po(self, path):
        out = []
        with open(path, encoding='utf-8') as handle:
            lines = handle.readlines()
        in_msgstr = False
        for number, line in enumerate(lines, start=1):
            stripped = line.rstrip('\n')
            match = PO_MSGSTR.match(stripped)
            if match:
                in_msgstr = True
                text = match.group(1)
            elif in_msgstr and PO_CONT.match(stripped):
                text = PO_CONT.match(stripped).group(1)
            else:
                in_msgstr = False
                continue
            if 'odoo' in text.lower():
                out.append('%s:%s  %s' % (path, number, text[:80]))
        return out

    def _scan_markup(self, path):
        """Comment-stripped, whole-word, case-sensitive."""
        out = []
        try:
            with open(path, encoding='utf-8') as handle:
                text = handle.read()
        except (OSError, UnicodeDecodeError):
            return out
        text = XML_COMMENT.sub(lambda m: '\n' * m.group(0).count('\n'), text)
        text = BLOCK_COMMENT.sub(
            lambda m: '\n' * m.group(0).count('\n'), text)
        for number, line in enumerate(text.split('\n'), start=1):
            if line.strip().startswith('//'):
                continue
            for match in WORD_ODOO.finditer(line):
                fragment = line[max(0, match.start() - 30):match.end() + 30]
                if any(token in fragment for token in SAFE_TOKENS):
                    continue
                out.append('%s:%s  %s' % (path, number, line.strip()[:90]))
                break
        return out
