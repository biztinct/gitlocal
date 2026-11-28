# -*- coding: utf-8 -*-
"""R22 (2026-11-20) — the "Form builder" button on Full details.

Numbered as in docs/handovers/formstudio/FS_FOLLOWUP1C_REPORT.md §4:
  P1 the button's gate answers yes for the administrator on THE Full details
     form only, no for any other form or a hand-made view id;
  P2 an HR manager without the administrator role: no button, and opening
     the Form builder for this screen (or saving / publishing it) is refused
     by the server;
  P3 the template and its script are in the backend bundle, extend the
     standard form's top bar slot, and read exactly "Form builder";
  P4 the employee form a "Full details" click opens IS that form, and a
     publish re-draws it (what the button reloads after Publish).
The browser walk (button beside "Set up workflow", overlay, publish, page
updates without a reload, absent for HR) is in the report.
"""
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import file_path

from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL, NATIVE_VIEW

MODULE_DIR = Path(__file__).resolve().parent.parent
JS = 'pb_form_studio_people/static/src/js/full_form_button.js'
XML = 'pb_form_studio_people/static/src/xml/full_form_button.xml'


@tagged('post_install', '-at_install', 'pb_form_studio_people')
class TestFullFormButton(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.admin = new_test_user(
            cls.env, 'pbfr22_admin', name='DEMO R22 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager')
        # Everything HR can be, except the administrator.
        cls.hr_mgr = new_test_user(
            cls.env, 'pbfr22_hrmgr', name='DEMO R22 HR Manager',
            groups='base.group_user,hr.group_hr_manager,om_hr_payroll.group_hr_payroll_manager')
        cls.emp = cls.env[MODEL].create({'name': 'DEMO R22 Person', 'payroll_country': 'VN'})
        cls.view = cls.env.ref(NATIVE_VIEW)

    def setUp(self):
        super().setUp()
        # The pay-run guard refuses a publish while a pay run is busy; this
        # suite is about the button, not the guard (engine tests 8, 31).
        self.startPatcher(patch.object(type(self.env['pb.form.studio']), '_pbfs_busy',
                                       lambda self_: ''))

    # ------------------------------------------------------------------ P1
    def test_p1_gate_admin_on_full_details_only(self):
        st = self.Studio.with_user(self.admin)
        self.assertTrue(st.can_edit(HOST))
        self.assertTrue(st.pbfs_people_full_form(self.view.id))
        other = self.env['ir.ui.view'].search(
            [('model', '=', MODEL), ('type', '=', 'form'), ('id', '!=', self.view.id)], limit=1)
        if other:
            self.assertFalse(st.pbfs_people_full_form(other.id), 'another employee form')
        contract_form = self.env.ref('hr_contract.hr_contract_view_form', raise_if_not_found=False)
        if contract_form:
            self.assertFalse(st.pbfs_people_full_form(contract_form.id), 'another record type')
        for bad in (False, 0, None, 'abc', -1):
            self.assertFalse(st.pbfs_people_full_form(bad), bad)

    # ------------------------------------------------------------------ P2
    def test_p2_hr_manager_without_admin_no_button_and_refused(self):
        self.assertFalse(self.hr_mgr.has_group('base.group_system'))
        st = self.Studio.with_user(self.hr_mgr)
        self.assertFalse(st.can_edit(HOST))
        self.assertFalse(st.pbfs_people_full_form(self.view.id))
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

    # ------------------------------------------------------------------ P3
    def test_p3_template_and_script_in_backend_bundle(self):
        paths = [row[0] for row in self.env['ir.asset']._get_asset_paths('web.assets_backend', {})]
        for wanted in (JS, XML):
            self.assertTrue(any(p.endswith(wanted) for p in paths), wanted)
        # After the panel patch it imports (the host key) and the engine.
        idx = {w: next(i for i, p in enumerate(paths) if p.endswith(w)) for w in (
            JS, 'pb_form_studio_people/static/src/js/people_form_patches.js',
            'pb_form_studio/static/src/js/studio_overlay.js')}
        self.assertGreater(idx[JS], idx['pb_form_studio_people/static/src/js/people_form_patches.js'])
        self.assertGreater(idx[JS], idx['pb_form_studio/static/src/js/studio_overlay.js'])

        tree = etree.parse(str(MODULE_DIR / 'static/src/xml/full_form_button.xml'))
        tmpl = tree.getroot().find('t')
        self.assertEqual(tmpl.get('t-inherit'), 'web.FormView')
        self.assertEqual(tmpl.get('t-inherit-mode'), 'extension')
        xp = tmpl.find('xpath')
        self.assertEqual(xp.get('expr'), "//t[@t-set-slot='layout-actions']")
        # The slot is there in the standard form (the place "Set up workflow" uses).
        std = etree.parse(file_path('web/static/src/views/form/form_controller.xml'))
        self.assertTrue(std.xpath("//t[@t-name='web.FormView']//t[@t-set-slot='layout-actions']"))
        btn = xp.find('button')
        self.assertIn('btn-outline-primary', btn.get('class'))
        self.assertIn('ms-2', btn.get('class'))
        self.assertIn('pbfsFull.can', btn.get('t-if'))
        self.assertEqual(''.join(btn.itertext()).strip(), 'Form builder')
        self.assertEqual(btn.get('aria-label'), 'Form builder')
        js = (MODULE_DIR / 'static/src/js/full_form_button.js').read_text(encoding='utf-8')
        self.assertIn('"pbfs_people_full_form"', js)
        self.assertIn('this.env.inDialog', js)

    # ------------------------------------------------------------------ P4
    def test_p4_full_details_is_that_form_and_publish_redraws_it(self):
        Emp = self.env[MODEL].with_user(self.admin)
        # "Full details" opens `views: [[false, "form"]]` — the default form.
        res = Emp.get_views([(False, 'form')])
        self.assertEqual(res['views']['form']['id'], self.view.id)
        st = self.Studio.with_user(self.admin)
        out = st.publish(HOST, {
            'sections': [{'id': 'custom', 'fields': ['new:1']}],
            'creates': [{'tmp': '1', 'type': 'text', 'label': 'DEMO R22 Locker', 'vis': 'hr'}],
            'base_version': st.get_studio(HOST)['version'], 'changes': []})
        self.assertTrue(out.get('ok'), out)
        name = out['created']['1']
        arch = Emp.get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('name="%s"' % name, arch)
        self.assertIn(name, Emp.get_views([(False, 'form')])['models'][MODEL]['fields'])
