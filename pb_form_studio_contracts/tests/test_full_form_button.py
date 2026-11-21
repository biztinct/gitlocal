# -*- coding: utf-8 -*-
"""R22 (2026-11-20) — the "Form builder" button on the full contract form.

Numbered as in docs/handovers/formstudio/FS_FOLLOWUP1C_REPORT.md §4:
  K1 the button's gate answers yes for the administrator on THE full
     contract form only, no for any other form or a hand-made view id;
  K2 a contract / HR manager without the administrator role: no button, and
     opening the Form builder for this screen (or saving / publishing it) is
     refused by the server;
  K3 the template and its script are in the backend bundle, extend the
     standard form's top bar slot, and read exactly "Form builder";
  K4 the contract form "Advanced form" opens IS that form, and a publish
     re-draws it (what the button reloads after Publish).
"""
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import file_path

from odoo.addons.pb_form_studio_contracts.models.form_studio_host import HOST, MODEL, NATIVE_VIEW

MODULE_DIR = Path(__file__).resolve().parent.parent
JS = 'pb_form_studio_contracts/static/src/js/full_form_button.js'
XML = 'pb_form_studio_contracts/static/src/xml/full_form_button.xml'


@tagged('post_install', '-at_install', 'pb_form_studio_contracts')
class TestFullFormButton(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_notrack=True, no_reset_password=True))
        cls.Studio = cls.env['pb.form.studio']
        mgr = ('base.group_user,hr.group_hr_manager,hr_contract.group_hr_contract_manager,'
               'om_hr_payroll.group_hr_payroll_manager')
        cls.admin = new_test_user(cls.env, 'fsr22_admin', groups=mgr + ',base.group_system',
                                  name='DEMO R22 Contract Admin')
        cls.hr_mgr = new_test_user(cls.env, 'fsr22_hrmgr', groups=mgr,
                                   name='DEMO R22 Contract Manager')
        cls.view = cls.env.ref(NATIVE_VIEW)

    def setUp(self):
        super().setUp()
        # The pay-run guard (as test_fs3_contracts): about the button here.
        self.startPatcher(patch.object(type(self.env['pb.form.studio']), '_pbfs_busy',
                                       lambda self_: ''))

    # ------------------------------------------------------------------ K1
    def test_k1_gate_admin_on_full_contract_form_only(self):
        st = self.Studio.with_user(self.admin)
        self.assertTrue(st.can_edit(HOST))
        self.assertTrue(st.fs3_full_form(self.view.id))
        other = self.env['ir.ui.view'].search(
            [('model', '=', MODEL), ('type', '=', 'form'), ('id', '!=', self.view.id)], limit=1)
        if other:
            self.assertFalse(st.fs3_full_form(other.id), 'another contract form')
        self.assertFalse(st.fs3_full_form(self.env.ref('hr.view_employee_form').id),
                         'another record type')
        for bad in (False, 0, None, 'abc', -1):
            self.assertFalse(st.fs3_full_form(bad), bad)

    # ------------------------------------------------------------------ K2
    def test_k2_manager_without_admin_no_button_and_refused(self):
        self.assertFalse(self.hr_mgr.has_group('base.group_system'))
        st = self.Studio.with_user(self.hr_mgr)
        self.assertFalse(st.can_edit(HOST))
        self.assertFalse(st.fs3_full_form(self.view.id))
        with self.assertRaises(AccessError):
            st.get_studio(HOST)
        with self.assertRaises(AccessError):
            st.save_draft(HOST, {'sections': [], 'creates': [], 'changes': []})
        with self.assertRaises(AccessError):
            st.publish(HOST, {'sections': [{'id': 'custom', 'fields': ['new:1']}],
                              'creates': [{'tmp': '1', 'type': 'text', 'label': 'DEMO R22 Refused',
                                           'vis': 'hr'}],
                              'base_version': 0, 'changes': []})
        self.assertFalse(self.env['ir.model.fields'].search(
            [('model', '=', MODEL), ('field_description', '=', 'DEMO R22 Refused')]))

    # ------------------------------------------------------------------ K3
    def test_k3_template_and_script_in_backend_bundle(self):
        paths = [row[0] for row in self.env['ir.asset']._get_asset_paths('web.assets_backend', {})]
        for wanted in (JS, XML):
            self.assertTrue(any(p.endswith(wanted) for p in paths), wanted)
        pos = {w: next(i for i, p in enumerate(paths) if p.endswith(w)) for w in (
            JS, 'pb_form_studio_contracts/static/src/js/contract_drawer_patch.js',
            'pb_form_studio/static/src/js/studio_overlay.js')}
        self.assertGreater(pos[JS], pos['pb_form_studio_contracts/static/src/js/contract_drawer_patch.js'])
        self.assertGreater(pos[JS], pos['pb_form_studio/static/src/js/studio_overlay.js'])

        tree = etree.parse(str(MODULE_DIR / 'static/src/xml/full_form_button.xml'))
        tmpl = tree.getroot().find('t')
        self.assertEqual(tmpl.get('t-inherit'), 'web.FormView')
        self.assertEqual(tmpl.get('t-inherit-mode'), 'extension')
        xp = tmpl.find('xpath')
        self.assertEqual(xp.get('expr'), "//t[@t-set-slot='layout-actions']")
        std = etree.parse(file_path('web/static/src/views/form/form_controller.xml'))
        self.assertTrue(std.xpath("//t[@t-name='web.FormView']//t[@t-set-slot='layout-actions']"))
        btn = xp.find('button')
        self.assertIn('btn-outline-primary', btn.get('class'))
        self.assertIn('ms-2', btn.get('class'))
        self.assertIn('fs3Full.can', btn.get('t-if'))
        self.assertEqual(''.join(btn.itertext()).strip(), 'Form builder')
        self.assertEqual(btn.get('aria-label'), 'Form builder')
        js = (MODULE_DIR / 'static/src/js/full_form_button.js').read_text(encoding='utf-8')
        self.assertIn('"fs3_full_form"', js)
        self.assertIn('const MODEL = "hr.contract"', js)
        self.assertIn('this.env.inDialog', js)

    # ------------------------------------------------------------------ K4
    def test_k4_advanced_form_is_that_form_and_publish_redraws_it(self):
        Contract = self.env[MODEL].with_user(self.admin)
        # "Advanced form" opens `views: [[false, "form"]]` — the default form.
        res = Contract.get_views([(False, 'form')])
        self.assertEqual(res['views']['form']['id'], self.view.id)
        st = self.Studio.with_user(self.admin)
        out = st.publish(HOST, {
            'sections': [{'id': 'custom', 'fields': ['new:1']}],
            'creates': [{'tmp': '1', 'type': 'text', 'label': 'DEMO R22 Bay', 'vis': 'hr'}],
            'base_version': st.get_studio(HOST)['version'], 'changes': []})
        self.assertTrue(out.get('ok'), out)
        name = out['created']['1']
        res = Contract.get_views([(False, 'form')])
        self.assertIn('name="%s"' % name, res['views']['form']['arch'])
        self.assertIn(name, res['models'][MODEL]['fields'])
