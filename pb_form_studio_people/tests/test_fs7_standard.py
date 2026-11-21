# -*- coding: utf-8 -*-
"""FS-7 numbered tests, employee side (docs/handovers/formstudio/FS7_REPORT.md).

R23: the administrator hides and renames STANDARD employee fields, per
Country of Work. A screen rule only — values, formulas, imports, Mapping and
reports keep the field. Tests 7 (markup before/after the install), 8
(payslips), 9 (upgrade of the host modules) and 10's two-worker half are run
by the scripts the report names.
"""
import time

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.pb_form_studio.models.form_standard import STD_RAW
from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL, NATIVE_VIEW


@tagged('post_install', '-at_install', 'pb_form_studio_people', 'fs7')
class TestFs7EmployeeStandard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.People = cls.env['pb.people']
        cls.vn, cls.india, cls.idn = cls.env.ref('base.vn'), cls.env.ref('base.in'), cls.env.ref('base.id')
        cls.admin = new_test_user(
            cls.env, 'fs7_admin', name='DEMO FS7 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')
        cls.hr = new_test_user(cls.env, 'fs7_hr', name='DEMO FS7 HR Manager',
                               groups='base.group_user,hr.group_hr_manager,'
                                      'om_hr_payroll.group_hr_payroll_manager')
        Emp = cls.env[MODEL]
        cls.emp_vn = Emp.create({'name': 'DEMO Lan Nguyen', 'payroll_country': 'VN',
                                 'pb_blood_type': 'O+', 'pb_job_level': 'L3',
                                 'visa_no': 'DEMO-V-VN'})
        cls.emp_in = Emp.create({'name': 'DEMO Arjun Rao', 'payroll_country': 'IN',
                                 'pb_blood_type': 'B+', 'pb_job_level': 'L4',
                                 'visa_no': 'DEMO-V-IN'})
        cls.emp_id = Emp.create({'name': 'DEMO Siti Rahma', 'payroll_country': 'ID',
                                 'pb_job_level': 'L2', 'pb_family_card_number': 'DEMO-KK-1'})

    # ---------------------------------------------------------------- utils
    def publish_std(self, updates, user=None):
        """The Form builder's own path: draft → Publish with `updates`."""
        st = self.Studio.with_user(user or self.admin)
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        st.save_draft(HOST, {'sections': sections, 'updates': updates, 'changes': ['x'],
                             'base_version': data['version']})
        t0 = time.time()
        res = st.publish(HOST, {'sections': sections, 'updates': updates, 'creates': [],
                                'deletes': [], 'base_version': data['version'],
                                'changes': ['DEMO change']})
        self.assertTrue(res.get('ok'), res)
        return time.time() - t0

    def arch(self, lang=None, user=None):
        Emp = self.env[MODEL].with_user(user or self.hr)
        if lang:
            Emp = Emp.with_context(lang=lang)
        return etree.fromstring(Emp.get_view(self.env.ref(NATIVE_VIEW).id, 'form')['arch'])

    def nodes(self, arch, name):
        return [n for n in arch.iter('field') if n.get('name') == name
                and not any(a.tag == 'field' for a in n.iterancestors())]

    def hidden_for(self, node, emp):
        expr = node.get('invisible') or ''
        if expr.strip() in ('1', 'True', 'true'):
            return True
        if not expr.strip():
            return False
        ctx = {'pbfs_country_of_work_id': emp.pbfs_country_of_work_id.id or False,
               'payroll_country': emp.payroll_country or False, 'id': emp.id}
        for _try in range(20):
            try:
                return bool(safe_eval(expr, dict(ctx)))
            except (NameError, ValueError) as err:
                missing = str(err).split("'")
                if len(missing) < 2:
                    raise
                ctx[missing[1]] = False       # any other box: empty on this record
        raise AssertionError(expr)

    def panel_rows(self, emp, user=None):
        tabs = self.People.with_user(user or self.hr).get_employee_360(emp.id).get('details') or {}
        return {r['key']: r['label'] for tab in tabs.values() for g in tab for r in g['rows']}

    # ------------------------------------------------------------------- 1
    def test_01_hide_for_everyone(self):
        before = self.emp_vn.pb_blood_type
        label_row = self.env['ir.model.fields']._get(MODEL, 'pb_blood_type').field_description
        self.assertIn('pb_blood_type', self.panel_rows(self.emp_vn))
        self.publish_std({'pb_blood_type': {'std_hidden': True}})
        arch = self.arch()
        nodes = self.nodes(arch, 'pb_blood_type')
        self.assertTrue(nodes, 'Blood type is on Full details')
        for node in nodes:
            self.assertTrue(self.hidden_for(node, self.emp_vn))
            self.assertTrue(self.hidden_for(node, self.emp_in))
        self.assertNotIn('pb_blood_type', self.panel_rows(self.emp_vn))
        self.assertNotIn('pb_blood_type', self.panel_rows(self.emp_in))
        # the value and the field itself are untouched (formulas, imports,
        # Mapping read the field, not the screen)
        self.emp_vn.invalidate_recordset()
        self.assertEqual(self.emp_vn.pb_blood_type, before)
        self.assertEqual(self.env['ir.model.fields']._get(MODEL, 'pb_blood_type').field_description,
                         label_row)
        self.assertEqual(self.env[MODEL]._fields['pb_blood_type'].get_description(self.env)['string'],
                         'Blood type')
        # the form as the modules draw it still has it plain
        raw, _view = self.env[MODEL].with_context(**{STD_RAW: True})._get_view(
            self.env.ref(NATIVE_VIEW).id, 'form')
        self.assertFalse(any(self.hidden_for(n, self.emp_vn) for n in self.nodes(raw, 'pb_blood_type')))
        # not a table column (People list) and not offered as one
        self.assertNotIn('pb_blood_type', [c['key'] for c in self.People.with_user(self.hr).pbf_columns()['columns']])
        # one history line
        audit = self.env['pb.form.audit'].search([('field_name', '=', 'pb_blood_type')], limit=1)
        self.assertIn('hidden for everyone', audit.summary)

    # ------------------------------------------------------------------- 2
    def test_02_hide_for_india_only(self):
        self.publish_std({'visa_no': {'std_country_ids': [self.india.id]}})
        nodes = self.nodes(self.arch(), 'visa_no')
        self.assertTrue(nodes)
        self.assertTrue(all(self.hidden_for(n, self.emp_in) for n in nodes))
        self.assertFalse(any(self.hidden_for(n, self.emp_vn) for n in nodes))
        self.assertNotIn('visa_no', self.panel_rows(self.emp_in))
        self.assertIn('visa_no', self.panel_rows(self.emp_vn))
        # a card left with no box is hidden with it, never shown empty
        # (FS-10: Job level is read by pay formulas now, so Visa No stands in)
        group = self.nodes(self.arch(), 'visa_no')[0].getparent()
        if group.tag == 'group' and not [n for n in group.iter('field')
                                         if n.get('name') != 'visa_no'
                                         and not self.hidden_for(n, self.emp_in)]:
            self.assertTrue(self.hidden_for(group, self.emp_in))
            self.assertFalse(self.hidden_for(group, self.emp_vn))
        # a country limit never clears a value
        self.emp_in.invalidate_recordset()
        self.assertEqual(self.emp_in.visa_no, 'DEMO-V-IN')

    # ---------------------------------------------------------- 3 (employee half)
    def test_03_rename_per_language(self):
        self.publish_std({'pb_job_level': {'std_labels': {'en_US': 'DEMO Grade'}}})
        nodes = self.nodes(self.arch(), 'pb_job_level')
        self.assertTrue(all(n.get('string') == 'DEMO Grade' for n in nodes))
        self.assertEqual(self.panel_rows(self.emp_vn).get('pb_job_level'), 'DEMO Grade')
        # Vietnamese / Indonesian: the built-in label until one is typed
        for lang in ('vi_VN', 'id_ID'):
            if not self.env['res.lang']._lang_get(lang):
                continue
            vi_nodes = self.nodes(self.arch(lang=lang), 'pb_job_level')
            self.assertTrue(all(n.get('string') != 'DEMO Grade' for n in vi_nodes), lang)
        # Reset: the built-in label is back
        self.publish_std({'pb_job_level': {'std_labels': {}}})
        self.assertTrue(all(n.get('string') != 'DEMO Grade'
                            for n in self.nodes(self.arch(), 'pb_job_level')))
        self.assertEqual(self.panel_rows(self.emp_vn).get('pb_job_level'), 'Job level')

    # ------------------------------------------------------------------- 4
    def test_04_locked_fields(self):
        st = self.Studio.with_user(self.admin)
        data = st.get_studio(HOST)
        for name in ('wage', 'bank_account_ids', 'payroll_country', 'name', 'company_id',
                     'birthday', 'identification_id', 'parent_id', 'user_id'):
            if name not in data['fields']:
                continue
            sd = data['fields'][name].get('stdbox')
            self.assertTrue(sd and sd['lock'], name)
            with self.assertRaises(UserError, msg=name):
                st.update_standard(MODEL, name, {'std_hidden': True})
            with self.assertRaises(UserError, msg=name):
                st.update_standard(MODEL, name, {'std_country_ids': [self.vn.id]})
        # label: wage CAN be renamed; name / company / Country of Work cannot
        st.update_standard(MODEL, 'wage', {'std_labels': {'en_US': 'DEMO Base pay'}})
        for name in ('payroll_country', 'name', 'company_id'):
            with self.assertRaises(UserError, msg=name):
                st.update_standard(MODEL, name, {'std_labels': {'en_US': 'DEMO'}})
        # a field that must be filled in to save is never hideable
        required = [n for n, f in self.env[MODEL]._fields.items()
                    if f.required and n in data['fields']]
        self.assertTrue(required)
        for name in required:
            self.assertTrue(data['fields'][name]['stdbox']['lock'], name)
        # the refusals wrote nothing but the wage's own label
        self.assertEqual(set(self.Studio._pbfs_std_rules(MODEL)), {'wage'})

    def test_04b_lock_after_hide(self):
        """A field hidden before it became locked is shown again at once."""
        st = self.Studio.with_user(self.admin)
        st.update_standard(MODEL, 'visa_no', {'std_hidden': True})
        self.assertTrue(self.Studio._pbfs_std_rules(MODEL)['visa_no']['all'])
        orig = type(self.Studio)._pbfs_standard_locked

        def locked(this, model):
            out = orig(this, model)
            if model == MODEL:
                out['visa_no'] = {'reason': 'DEMO now read by a formula.', 'label': False}
            return out
        self.patch(type(self.Studio), '_pbfs_standard_locked', locked)
        self.env.registry.clear_cache('templates')
        self.assertFalse(self.Studio._pbfs_std_rules(MODEL).get('visa_no'))
        self.assertFalse(any(self.hidden_for(n, self.emp_vn) for n in self.nodes(self.arch(), 'visa_no')))
        desc = st.get_studio(HOST)['fields']['visa_no']['stdbox']
        self.assertTrue(desc['ignored'])
        # it can be cleared (shown), never hidden more
        st.update_standard(MODEL, 'visa_no', {'std_hidden': False, 'std_country_ids': []})
        with self.assertRaises(UserError):
            st.update_standard(MODEL, 'visa_no', {'std_hidden': True})

    # ------------------------------------------------------------------- 5
    def test_05_product_country_rule(self):
        """TIDY-E shows some boxes only where Country of Work is one country.
        The administrator hides such a box for another country too: hidden if
        either says hidden; never shown where the product hides it.

        FS-10: the Indonesian family card is in the pay formula catalogue, so
        it is locked now — the test takes a one-country box that is still
        free (first one in TIDY-E's table, whose country has a test person)."""
        if not hasattr(self.env[MODEL], '_pb_tidy_tab_names'):
            self.skipTest('pb_employee_form_tidy is not installed')
        st = self.Studio.with_user(self.admin)
        fields_ = st.get_studio(HOST)['fields']
        people = {'VN': self.emp_vn, 'IN': self.emp_in, 'ID': self.emp_id}
        pick = None
        for name, rule in self.Studio._pbfs_people_tidy_rules().items():
            desc = (fields_.get(name) or {}).get('stdbox')
            if desc and rule in people and not desc['lock'] and self.nodes(self.arch(), name):
                pick = (name, rule)
                break
        if not pick:
            self.skipTest('no free one-country box on this database')
        name, code = pick
        home = people[code]
        away_code = 'VN' if code != 'VN' else 'IN'
        away = people[away_code]
        away_country = self.env.ref('base.%s' % away_code.lower())
        home_country = self.env.ref('base.%s' % code.lower())
        desc = fields_[name]['stdbox']
        self.assertEqual(desc['rule']['code'], code)
        nodes = self.nodes(self.arch(), name)
        self.assertTrue(all(self.hidden_for(n, away) for n in nodes))       # product
        self.assertFalse(any(self.hidden_for(n, home) for n in nodes))
        self.publish_std({name: {'std_country_ids': [away_country.id]}})
        nodes = self.nodes(self.arch(), name)
        self.assertTrue(all(self.hidden_for(n, away) for n in nodes))
        self.assertFalse(any(self.hidden_for(n, home) for n in nodes))
        # R31 (FS-15): "hidden in <away>" on top of "only <home>" IS "only
        # <home>": nothing is stored as a change, the product's rule stays
        self.assertFalse(self.Studio._pbfs_std_rules(MODEL).get(name))
        # hidden for its own country too → nowhere
        self.publish_std({name: {'std_country_ids': [away_country.id, home_country.id]}})
        nodes = self.nodes(self.arch(), name)
        self.assertTrue(all(self.hidden_for(n, home) for n in nodes))
        # Showing it again never shows it outside its country
        self.publish_std({name: {'std_country_ids': []}})
        nodes = self.nodes(self.arch(), name)
        self.assertTrue(all(self.hidden_for(n, away) for n in nodes))
        self.assertFalse(any(self.hidden_for(n, home) for n in nodes))

    # ------------------------------------------------------------------- 6
    def test_06_only_the_administrator(self):
        st = self.Studio.with_user(self.hr)
        for call in (lambda: st.get_studio(HOST), lambda: st.library(),
                     lambda: st.update_standard(MODEL, 'pb_blood_type', {'std_hidden': True}),
                     lambda: st.update_standard(MODEL, 'pb_job_level', {'std_labels': {'en_US': 'X'}}),
                     lambda: st.publish(HOST, {'updates': {'pb_blood_type': {'std_hidden': True}}})):
            with self.assertRaises(AccessError):
                call()
        self.assertFalse(self.Studio._pbfs_std_rules(MODEL))
        # … and they simply see the result
        self.publish_std({'pb_blood_type': {'std_hidden': True}})
        self.assertNotIn('pb_blood_type', self.panel_rows(self.emp_vn, user=self.hr))

    # ------------------------------------------------------------------- 7
    def test_07_silent(self):
        """Nothing hidden or renamed until an administrator acts: no rule
        row, the form is exactly the form the modules draw."""
        Meta = self.env['pb.form.field.meta'].sudo()
        self.assertEqual(Meta.search_count(['|', '|', ('std_hidden', '=', True),
                                            ('std_country_ids', '!=', False),
                                            ('std_labels', '!=', False)]), 0)
        view = self.env.ref(NATIVE_VIEW)
        for lang in (None, 'vi_VN'):
            Emp = self.env[MODEL].with_user(self.hr)
            if lang:
                Emp = Emp.with_context(lang=lang)
            # R31 (FS-15): the "as the modules draw it" read now also draws the
            # boxes the product takes off the screens (the Form builder lists
            # them), so it is no longer the yardstick. Silent = no rule at all
            # reaches the form: the engine adds nothing and TIDY-E applies its
            # own table; the byte-identical markup before/after the upgrade is
            # proven on copies of the five sites (FS15_REPORT §5).
            self.assertFalse(self.Studio._pbfs_std_rules(MODEL))
            arch, _v = Emp._get_view(view.id, 'form')
            self.assertEqual(self.Studio._pbfs_std_apply_arch(arch, MODEL, 'pbfs_country_of_work_id'), [])
        if hasattr(self.env[MODEL], '_pb_tidy_rules'):
            from odoo.addons.pb_employee_form_tidy.models.form_rules import FORM_RULES
            self.assertEqual(self.env[MODEL]._pb_tidy_rules(), FORM_RULES)
        self.assertFalse(self.Studio._pbfs_std_tidy_overrides(MODEL))

    # ------------------------------------------------------------------- 10
    def test_10_draft_publish_history_undo(self):
        st = self.Studio.with_user(self.admin)
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])} for s in data['sections']
                    if s['kind'] == 'open']
        # a draft changes nothing for anybody
        st.save_draft(HOST, {'sections': sections, 'changes': ['x'], 'base_version': data['version'],
                             'updates': {'pb_blood_type': {'std_hidden': True}}})
        self.assertIn('pb_blood_type', self.panel_rows(self.emp_vn))
        self.assertFalse(self.Studio._pbfs_std_rules(MODEL))
        self.publish_std({'pb_blood_type': {'std_hidden': True},
                          'pb_job_level': {'std_labels': {'en_US': 'DEMO Grade'}}})
        self.assertNotIn('pb_blood_type', self.panel_rows(self.emp_vn))
        lines = self.env['pb.form.audit'].search([('model', '=', MODEL), ('field_name', 'in',
                                                  ('pb_blood_type', 'pb_job_level'))])
        self.assertEqual(len(lines), 2)
        self.assertTrue(self.env['pb.form.audit'].search([('action', '=', 'publish')], limit=1))
        # undo = put it back the same way; the history keeps both lines
        self.publish_std({'pb_blood_type': {'std_hidden': False},
                          'pb_job_level': {'std_labels': {}}})
        self.assertIn('pb_blood_type', self.panel_rows(self.emp_vn))
        self.assertEqual(self.panel_rows(self.emp_vn).get('pb_job_level'), 'Job level')
        self.assertEqual(self.env['pb.form.audit'].search_count(
            [('model', '=', MODEL), ('field_name', 'in', ('pb_blood_type', 'pb_job_level'))]), 4)
        # the pay-run guard does not apply: no column is added or dropped
        self.patch(type(self.Studio), '_pbfs_busy', lambda this: 'DEMO busy')
        self.publish_std({'pb_blood_type': {'std_hidden': True}})

    # ------------------------------------------------------------------- 12
    def test_12_fast_and_no_column_change(self):
        self.env.cr.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='hr_employee'")
        cols = self.env.cr.fetchone()[0]
        took = self.publish_std({
            'pb_blood_type': {'std_hidden': True}, 'pb_religion': {'std_hidden': True},
            'visa_no': {'std_country_ids': [self.india.id]},
            'pb_job_level': {'std_labels': {'en_US': 'DEMO Grade'}},
            'pb_visa_status': {'std_labels': {'en_US': 'DEMO Visa'}},
            'additional_note': {'std_labels': {'en_US': 'DEMO HR note'}}})
        self.assertLess(took, 2.0)
        self.env.cr.execute("SELECT count(*) FROM information_schema.columns WHERE table_name='hr_employee'")
        self.assertEqual(self.env.cr.fetchone()[0], cols)

    # ------------------------------------------------------------------- R24 data
    def test_13_standard_tab_data(self):
        """The Standard fields tab is fed by get_studio: every box, by tab,
        its built-in label per language, sorted by screen order."""
        data = self.Studio.with_user(self.admin).get_studio(HOST)
        std = {n: f for n, f in data['fields'].items() if f.get('stdbox')}
        self.assertGreater(len(std), 40)
        self.assertIn('pb_blood_type', std)
        self.assertFalse(std['pb_blood_type']['placeable'] is True
                         and 'pb_blood_type' not in self.Studio._pbfs_std_names(
                             self.Studio._pbfs_hosts()[HOST]))
        self.assertTrue(all(f['stdbox']['tab'] for f in std.values()))
        self.assertIn('lang', data)
        self.assertTrue(set(std['pb_blood_type']['stdbox']['builtins']) >= {'en_US'})
