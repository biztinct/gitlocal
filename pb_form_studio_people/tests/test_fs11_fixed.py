# -*- coding: utf-8 -*-
"""FS-11 numbered tests, employee side (FS11_FS12_REPORT.md).

R29: every fixed ("drawn by the screen") section of the Form builder lists
the fields that part of the screen really shows, and a listed field opens the
same settings as the Standard fields tab.

1 map = screen (side panel, both ways; Full details read from the form);
2 the facts behind the chips (hidden, renamed, country, My Payobook, locked);
3 click → hide → Publish → the field leaves the screen.
(4 "Find a field" and 5 phone width are walked in the browser.)
"""
from lxml import etree

from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio.models.form_standard import STD_SKIP_TTYPES
from odoo.addons.pb_form_studio.models.ir_model_fields import PREFIX
from odoo.addons.pb_form_studio_people.models.fixed_sections import VN_DEPENDENT_KEY
from odoo.addons.pb_form_studio_people.models.premium_section import SECTIONS
from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL, NATIVE_VIEW

#: A value of each kind, to fill a person in completely.
SAMPLE = {'char': 'DEMO 1', 'text': 'DEMO note', 'integer': 2, 'float': 1.5,
          'date': '2026-01-15', 'datetime': '2026-01-15 08:00:00', 'boolean': True}


@tagged('post_install', '-at_install', 'pb_form_studio_people', 'fs11')
class TestFs11Fixed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.admin = new_test_user(
            cls.env, 'fs11_admin', name='DEMO FS11 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')
        Emp = cls.env[MODEL]
        cls.emp_vn = Emp.create({'name': 'DEMO FS11 Lan', 'payroll_country': 'VN'})
        cls.emp_id = Emp.create({'name': 'DEMO FS11 Siti', 'payroll_country': 'ID'})
        cls.emp_sg = Emp.create({'name': 'DEMO FS11 Wei', 'payroll_country': 'SG'})
        cls.people = (cls.emp_vn, cls.emp_id, cls.emp_sg)
        cls.map = cls.Studio.with_user(cls.admin)._pbfs_people_panel_map()
        for emp in cls.people:
            cls._fill(emp)
        cls.env.invalidate_all()

    @classmethod
    def _fill(cls, emp):
        """Every map field of a simple kind gets a value, one by one (a box
        that refuses a value is simply left empty)."""
        names = {it['name'] for items in cls.map.values() for it in items if it['name']}
        for name in sorted(names):
            field = emp._fields[name]
            # the contract dates follow the contract (a database check refuses them alone)
            if name in ('payroll_country', 'name', 'contract_date_start', 'contract_date_end') \
                    or field.readonly or (
                    field.compute and not field.inverse) or not field.store and not field.inherited:
                continue
            value = SAMPLE.get(field.type)
            if field.type == 'selection':
                opts = [k for k, _l in field._description_selection(cls.env)]
                value = opts[0] if opts else None
            elif name == 'user_id':
                value = new_test_user(cls.env, 'fs11_u%s' % emp.id, name='DEMO FS11 login').id
            elif field.type == 'many2one':
                value = cls.env[field.comodel_name].search([], limit=1).id or None
            if value is None:
                continue
            try:
                with cls.env.cr.savepoint():
                    emp.write({name: value})
                    emp.env.flush_all()
            except Exception:                           # noqa: BLE001
                emp.invalidate_recordset()

    def panel_keys(self, emp):
        tabs = self.env['pb.people'].with_user(self.admin)._e360_details(emp.with_user(self.admin), True)
        out = set()
        for tab in ('personal', 'job', 'pay'):
            for group in tabs.get(tab) or []:
                for row in group.get('rows') or []:
                    out.add((tab, row['key']))
        # Native section editors replace the corresponding summary rows and
        # add the rest of the fields from Full details.
        for tab in SECTIONS:
            root = etree.fromstring(self.env[MODEL].with_user(self.admin).get_view(
                view_type='form', pb_workspace_section=tab)['arch'])
            out.update((tab, n.get('name')) for n in root.xpath('.//section//field[not(ancestor::field)]')
                       if not any(a.get('invisible') in ('1', 'True', 'true') for a in [n, *n.iterancestors()]))
        return out

    def map_keys(self):
        """(tab, panel row key) of every map line; the Vietnam pay group's
        keys carry a `vnpay.` prefix in the map (the same field can sit in two
        groups), dependent lines a pattern."""
        out = set()
        for tab, items in self.map.items():
            for it in items:
                key = it['key']
                if key.startswith('vnpay.'):
                    key = key[len('vnpay.'):]
                out.add((tab, key))
        return out

    # ------------------------------------------------------------------ 1
    def test_01_panel_map_is_the_screen(self):
        """Every line the side panel draws is in the map, and every field
        the map names is drawn for a filled-in person (VN-paid or not)."""
        shown = set()
        for emp in self.people:
            shown |= self.panel_keys(emp)
        mapped = self.map_keys()
        lacking = {(t, k) for t, k in shown
                   if (t, k) not in mapped and not (k.startswith('dependent_')
                                                    and (t, VN_DEPENDENT_KEY) in mapped)}
        self.assertFalse(lacking, 'the panel shows lines the map lacks: %s' % sorted(lacking))
        filled = set()
        for emp in self.people:
            for tab, items in self.map.items():
                for it in items:
                    if it['name'] and emp[it['name']]:      # an empty link is an empty recordset
                        filled.add((tab, it['key'][len('vnpay.'):] if it['key'].startswith('vnpay.')
                                    else it['key']))
        missing = {k for k in filled if k not in shown}
        self.assertFalse(missing, 'the map names fields the panel does not draw: %s' % sorted(missing))
        self.assertTrue(len(filled) > 20, 'the test person must really be filled in (%s)' % len(filled))

    def test_01b_studio_lists_every_fixed_section(self):
        data = self.Studio.with_user(self.admin).get_studio(HOST)
        fixed = data['fixed']
        locked = [s['id'] for s in data['sections'] if s['kind'] == 'locked']
        self.assertEqual(sorted(fixed), sorted(locked))
        self.assertTrue(fixed['personal'] and fixed['job'] and fixed['pay'] and fixed['profile'])
        self.assertTrue({'id_card', 'driving_license'} <= {it['name'] for it in fixed['documents']})
        # a field line opens the settings of that field
        birthday = next(it for it in fixed['personal'] if it['name'] == 'birthday')
        self.assertEqual(birthday['ref'], 'birthday')
        self.assertIn('stdbox', data['fields']['birthday'])
        # a worked-out line opens nothing
        self.assertTrue(all(not it['ref'] for it in fixed['profile']))
        self.assertTrue(any(it['country'] == 'VN' for it in fixed['pay']))

    def test_01c_full_details_tabs_from_the_form(self):
        """Opened from Full details: the form's tabs are the fixed sections and
        each lists exactly the boxes the form shows there."""
        data = self.Studio.with_user(self.admin).with_context(pbfs_surface='full').get_studio(HOST)
        tabs = [s for s in data['sections'] if s['kind'] == 'locked']
        self.assertTrue(tabs)
        self.assertTrue(all(s['id'].startswith('full_') for s in tabs))
        listed = {it['name'] for s in tabs for it in data['fixed'][s['id']]}
        Emp = self.env[MODEL].sudo().with_context(pbfs_std_raw=True)
        arch, _view = Emp._get_view(self.env.ref(NATIVE_VIEW).id, 'form')

        def visible(node):
            for n in [node] + list(node.iterancestors()):
                if (n.get('invisible') or '').strip() in ('1', 'True', 'true'):
                    return False
            return True
        on_form = {n.get('name') for n in arch.iter('field')
                   if visible(n) and not any(a.tag in ('field', 'button') for a in n.iterancestors())
                   and n.get('name') in Emp._fields and not n.get('name').startswith(PREFIX)
                   and n.get('name') not in self.Studio._pbfs_std_exclude(Emp._name)
                   and Emp._fields[n.get('name')].type not in STD_SKIP_TTYPES
                   # R31: taken off the screens and not shown again → not listed
                   and self.Studio._pbfs_std_builtin_rule(Emp._name, n.get('name')) != 'remove'}
        self.assertEqual(listed, on_form)
        # the open sections still follow the tabs
        self.assertTrue(any(s['kind'] == 'open' for s in data['sections']))

    # ------------------------------------------------------------------ 2
    def test_02_chip_facts(self):
        st = self.Studio.with_user(self.admin)
        st.update_standard(MODEL, 'place_of_birth', {'std_hidden': True})
        st.update_standard(MODEL, 'study_field', {'std_country_ids': [self.env.ref('base.in').id]})
        st.update_standard(MODEL, 'certificate', {'std_labels': {'en_US': 'DEMO Schooling'}})
        st.update_standard(MODEL, 'pb_blood_type', {'portal_show': True})
        data = st.get_studio(HOST)
        f = data['fields']
        self.assertTrue(f['place_of_birth']['stdbox']['hidden'])
        self.assertEqual([c['code'] for c in f['study_field']['stdbox']['countries']], ['IN'])
        self.assertEqual(f['certificate']['stdbox']['labels'].get('en_US'), 'DEMO Schooling')
        self.assertTrue(f['pb_blood_type']['portal']['show'])
        self.assertTrue(f['birthday']['stdbox']['lock'])           # government forms print it
        refs = {it['ref'] for items in data['fixed'].values() for it in items}
        self.assertTrue({'place_of_birth', 'study_field', 'certificate', 'pb_blood_type',
                         'birthday'} <= refs)

    # ------------------------------------------------------------------ 3
    def test_03_hide_from_the_list_then_publish(self):
        self.assertIn(('personal', 'place_of_birth'), self.panel_keys(self.emp_id))
        st = self.Studio.with_user(self.admin)
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        res = st.publish(HOST, {'sections': sections, 'creates': [], 'deletes': [],
                                'updates': {'place_of_birth': {'std_hidden': True}},
                                'base_version': data['version'], 'changes': ['DEMO hide']})
        self.assertTrue(res['ok'])
        self.assertNotIn(('personal', 'place_of_birth'), self.panel_keys(self.emp_id))
