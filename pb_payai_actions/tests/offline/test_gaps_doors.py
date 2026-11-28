# -*- coding: utf-8 -*-
"""GAPS (4b) — PayAI's door buttons read in the READER's language, EXECUTED
offline (no odoo-bin, PA10).

    python3 pb_payai_actions/tests/offline/test_gaps_doors.py

A ⌘K row arrives with its words in the language of the person's screens (the
browser translated them); PayAI answers in the language the chat's language
pill chose. Before this, a Vietnamese reader on English screens read "Mở Home
› Approvals". The real `resolve` and `runner` run over `odoo_stub`; the
browser catalogue is read from the REAL module .po files with Odoo's own rule
(entries marked `odoo-javascript` with a translation).
"""
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import odoo_stub as S  # noqa: E402

S.install()
PAYAI = S.load_payai_package()
resolve = PAYAI.resolve
runner = PAYAI.runner
i18n = PAYAI.i18n

_ENTRY = re.compile(r'^msgid "(.*)"\nmsgstr "(.*)"$', re.M)


def _web_messages(module, lang):
    """Odoo's `code_translations.get_web_translations`, from the .po file."""
    path = os.path.join(S.REPO, module, 'i18n', '%s.po' % lang)
    out = []
    if not os.path.exists(path):
        return {'messages': ()}
    for block in re.split(r'\n\s*\n', open(path, encoding='utf-8').read()):
        if 'odoo-javascript' not in block or block.lstrip().startswith('#~'):
            continue
        m = _ENTRY.search(block)
        if m and m.group(2):
            out.append({'id': m.group(1), 'string': m.group(2)})
    return {'messages': tuple(out)}


sys.modules['odoo.tools.translate'].code_translations = types.SimpleNamespace(
    get_web_translations=_web_messages)

def _installed():
    return sorted(d for d in os.listdir(S.REPO)
                  if d in GAPS_MODULES and os.path.isdir(os.path.join(S.REPO, d, 'i18n')))


class _Modules:
    def sudo(self):
        return self

    def search(self, domain):
        return types.SimpleNamespace(mapped=lambda f: _installed())


class _Learn:
    def station(self, key):
        return {'key': key, 'name': {'en': 'Government filings',
                                     'vi': 'Báo cáo nộp cơ quan nhà nước'}}

    def scenario(self, key):
        return None


class _Env(dict):
    def __init__(self, lang):
        super().__init__({'ir.module.module': _Modules(), 'learn.content': _Learn()})
        self.user = types.SimpleNamespace(lang=lang)
        self.registry = object()
        self.context = {}


def _rows(screens='en'):
    if screens == 'vi':
        # The browser sends the words under the translation (`label_src`).
        return [{'id': 'homehub_approvals', 'label': 'Phê duyệt', 'sublabel': 'Trang chủ',
                 'label_src': 'Approvals', 'sublabel_src': 'Home', 'kind': 'lens'},
                # An older browser sent none: "Phê duyệt" is two English
                # phrases (Approvals, Sign-off) — never guessed; "Trang chủ" is one.
                {'id': 'homehub_old', 'label': 'Phê duyệt', 'sublabel': 'Trang chủ', 'kind': 'lens'},
                {'id': 'payruns', 'label': 'Các đợt lương', 'sublabel': 'Pay Run', 'kind': 'link'}]
    return [{'id': 'homehub_approvals', 'label': 'Approvals', 'sublabel': 'Home', 'kind': 'lens'},
            {'id': 'payruns', 'label': 'Pay Runs', 'sublabel': 'Pay Run', 'kind': 'link'},
            {'id': 'learn.station.filing', 'label': 'Government filings',
             'sublabel': 'Lesson · 5 min · how to', 'kind': 'learn'},
            {'id': 'zz_unknown', 'label': 'Zyxq Board', 'sublabel': '', 'kind': 'link'}]


class _Lang:
    def __init__(self, code):
        self.code = code

    def __enter__(self):
        self.token = i18n.set_lang(self.code)

    def __exit__(self, *exc):
        i18n.reset_lang(self.token)


class TestDoorNames(unittest.TestCase):
    def setUp(self):
        resolve._WEB_TERMS.clear()

    def test_english_screens_vietnamese_reader(self):
        rows = resolve.door_names(_Env('en_US'), _rows())
        by = {r['id']: r for r in rows}
        with _Lang('vi_VN'):
            self.assertEqual(resolve.door_title(by['homehub_approvals']), 'Trang chủ › Phê duyệt')
            # A Learn row: its own name; the composite sublabel ("Lesson · 5
            # min · how to") is the screens' language only, so it is left off.
            self.assertEqual(resolve.door_title(by['learn.station.filing']),
                             'Báo cáo nộp cơ quan nhà nước')
            # A word nobody translated stays as it is — never blank.
            self.assertEqual(resolve.door_title(by['zz_unknown']), 'Zyxq Board')
            self.assertEqual(resolve._door_choice(by['homehub_approvals']),
                             {'value': 'homehub_approvals', 'label': 'Phê duyệt',
                              'sublabel': 'Trang chủ'})
        with _Lang('en_US'):
            self.assertEqual(resolve.door_title(by['homehub_approvals']), 'Home › Approvals')
            self.assertEqual(resolve.door_title(by['learn.station.filing']),
                             'Lesson · 5 min · how to › Government filings')
        # The row's own words are kept for matching what the person typed.
        self.assertEqual((by['homehub_approvals']['label'], by['homehub_approvals']['sublabel']),
                         ('Approvals', 'Home'))

    def test_vietnamese_screens_english_reader(self):
        rows = resolve.door_names(_Env('vi_VN'), _rows('vi'))
        by = {r['id']: r for r in rows}
        with _Lang('en_US'):
            self.assertEqual(resolve.door_title(by['homehub_approvals']), 'Home › Approvals')
            self.assertEqual(resolve.door_title(by['homehub_old']), 'Home › Phê duyệt')
        with _Lang('vi_VN'):
            self.assertEqual(resolve.door_title(by['homehub_old']), 'Trang chủ › Phê duyệt')
            self.assertEqual(resolve.door_title(by['homehub_approvals']), 'Trang chủ › Phê duyệt')
            self.assertEqual(resolve.door_title(by['payruns']), 'Đợt lương › Các đợt lương')

    def test_every_palette_row_of_ours_has_vietnamese(self):
        """Every ⌘K label / sublabel our modules register reads in Vietnamese
        (its own module's catalogue, or any installed one's — the browser
        falls back to every module's words)."""
        vi = resolve._web_terms(_Env('en_US'), 'vi_VN')
        missing = []
        rx = re.compile(r'\b(?:label|sublabel|SUB)\s*[:=]\s*_t\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
        for root, _dirs, files in os.walk(S.REPO):
            if '/static/src' not in root or '/node_modules' in root or '/tests' in root:
                continue
            for name in files:
                if not name.endswith('.js'):
                    continue
                path = os.path.join(root, name)
                src = open(path, encoding='utf-8').read()
                # A file that ADDS rows to the ⌘K registry (not one that reads it).
                if not re.search(r'(?:category\("pb_hub_palette"\)|\bpalette)\s*\.add\(', src):
                    continue
                mod = os.path.relpath(path, S.REPO).split(os.sep)[0]
                if not mod.startswith(resolve._OWN_PREFIXES) or mod not in GAPS_MODULES:
                    continue
                for m in rx.finditer(src):
                    if m.group(1) not in vi:
                        missing.append('%s: %s' % (os.path.relpath(path, S.REPO), m.group(1)))
        self.assertFalse(missing, '\n'.join(missing))

    def test_the_request_context_names_every_door(self):
        """runner.Ctx gives every door row both languages, once per request."""
        env = _Env('en_US')
        env['payroll.ai.conversation'] = types.SimpleNamespace(browse=lambda *a: [])
        conv = types.SimpleNamespace(user_id='me', payai_doors=lambda: _rows())
        engine = types.SimpleNamespace(env=env, _conversation=lambda ctx: conv)
        env.user = types.SimpleNamespace(lang='en_US')
        conv.user_id = env.user
        ctx = runner.Ctx(engine, {})
        row = ctx.door_row('homehub_approvals')
        self.assertIn('names', row)
        with _Lang('vi_VN'):
            self.assertEqual(resolve.door_title(row), 'Trang chủ › Phê duyệt')


#: The modules whose ⌘K rows PayAI can be handed on payobook (installed there;
#: checked against the live database 2026-10-16). Others are checked when they
#: ship to a database with PayAI.
GAPS_MODULES = frozenset("""
biz_access biz_approval_chain biz_approval_workflow biz_audit_trail biz_debrand biz_deroute
biz_deroute_website biz_doc_ocr biz_errors biz_geo_tracking biz_mail_debrand biz_theme
biz_week_grid pb_approval pb_approval_config pb_ask_hr pb_assets pb_attendance_flow pb_audit
pb_bank_ocr pb_blueprint pb_budget pb_business_trip pb_close pb_comp_ben pb_compliance_hub
pb_contract_lifecycle pb_contracts pb_dashboard pb_decision_room pb_demo pb_demo_portal
pb_demo_seed pb_driver_checkin pb_employee_vault pb_ess_workforce pb_explorer pb_formula_studio
pb_goals pb_govt_reports pb_group pb_hiring pb_home_hub pb_hr_comm pb_hr_flow pb_hr_fullandfinal
pb_hr_govt pb_hr_payroll_analytics pb_hr_payroll_base pb_hr_payroll_demand pb_hr_payroll_formula
pb_hr_payroll_vietnam pb_hr_workforce pb_hub pb_import pb_import_advanced pb_import_batch
pb_import_kit pb_import_wizard pb_insights pb_insights_hub pb_integrations pb_learn pb_lifecycle
pb_login_language pb_me_expense pb_me_portal pb_me_portal_comm pb_me_portal_website
pb_me_project_time pb_me_trip pb_mission pb_offboarding pb_onboarding pb_pack_id pb_pack_in
pb_pack_my pb_pack_sg pb_pack_th pb_pack_vn pb_pay pb_pay_delivery pb_payai_actions pb_payhub
pb_payroll_ai_insights pb_payroll_templates pb_payrun_ledgers pb_payrun_results pb_payrun_wizard
pb_payruns pb_payslip pb_payslip_review pb_people pb_people_advanced pb_people_hub pb_pip
pb_probation pb_records pb_rnr pb_schedule pb_scheme_map pb_settings pb_sidebar pb_source_atlas
pb_statutory pb_structures pb_team pb_tenancy pb_tenants pb_theme pb_time_hub pb_timeoff
pb_timesheet_approval pb_today pb_training pb_trip_expense_bridge pb_trip_payroll_bridge
pb_vendor_access pb_website pb_wf_kit pb_workforce_insights pb_workforce_payroll_bridge
pb_workseg pb_young_worker pb_zoho_bridge pb_zoho_sso
""".split())


if __name__ == '__main__':
    unittest.main()
