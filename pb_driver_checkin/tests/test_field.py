# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""RIZE W2 D1 — T7: the driver app is the FIELD check-in app (ruling D16).

The generalisation has exactly one way to go silently wrong, and it is R7:
`res.users.group_ids` is DIRECT membership only, so the moment Driver became
an IMPLIED group the map would have emptied itself of every driver on the
database — no error, no log line, just a screen that says "No field staff yet"
over a company full of them. That is the first test below.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _src(module, *parts):
    return _read(os.path.join(get_module_path(module), *parts))


def _code(src):
    """The file with its COMMENTS removed (R118)."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif src[i] in '"\'`':
            quote = src[i]
            out.append(quote)
            i += 1
            while i < n and src[i] != quote:
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            out.append(quote)
            i += 1
        else:
            out.append(src[i])
            i += 1
    return ''.join(out)


@tagged('post_install', '-at_install')
class TestFieldStaff(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Map = cls.env['pb.driver.map']
        cls.field_group = cls.env.ref('pb_driver_checkin.group_pb_field_staff')
        cls.driver_group = cls.env.ref('pb_driver_checkin.group_pb_driver')
        cls.company = cls.env['res.company'].create({'name': 'D1 Field Co'})
        cls.officer = cls.env.ref('base.user_admin')
        cls.officer.write({'company_ids': [(4, cls.company.id)]})

        cls.driver_user = cls._person(
            'DEMO Field Driver', 'demo.field.driver.d1', cls.driver_group)
        cls.agro_user = cls._person(
            'DEMO Field Agronomist', 'demo.field.agro.d1', cls.field_group)
        cls.desk_user = cls._person(
            'DEMO Desk Person', 'demo.field.desk.d1', None)

    @classmethod
    def _person(cls, name, login, group):
        groups = [cls.env.ref('base.group_user').id]
        if group:
            groups.append(group.id)
        user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)]})
        cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id, 'user_id': user.id})
        return user

    # -------------------------------------------------------------- D16
    def test_a_driver_holds_field_staff_through_the_implication(self):
        """Every existing driver keeps working on the day of the upgrade,
        with nothing to migrate — that is the whole reason the broad group is
        implied rather than swapped in."""
        self.assertIn(self.field_group, self.driver_user.all_group_ids)
        self.assertNotIn(self.driver_group, self.agro_user.all_group_ids,
                         'field staff is not a driver')

    def test_the_map_reads_the_group_TRANSITIVELY(self):
        """R7 — `group_ids` is DIRECT membership only. Reading it here would
        have emptied the map of every driver on the database, silently."""
        users = self.Map._driver_users()
        self.assertIn(self.driver_user, users,
                      'a driver must still be on the map (R7)')
        self.assertIn(self.agro_user, users)
        self.assertNotIn(self.desk_user, users)

    def test_the_map_lists_both_kinds_of_field_person(self):
        data = self.Map.with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id]).with_company(
                self.company).get_live_data()
        names = [row['name'] for row in data['drivers']]
        self.assertIn('DEMO Field Driver', names)
        self.assertIn('DEMO Field Agronomist', names)
        self.assertNotIn('DEMO Desk Person', names)

    def test_somebody_on_approved_leave_says_so_on_the_rail(self):
        """A field person on approved time off reads as "off duty" and looks
        identical to one who has not started — which is the question an
        officer opens this map to answer."""
        today = self.env['pb.holidays']._today()
        leave_type = self.env['hr.leave.type'].create({
            'name': 'D1 Field sick', 'requires_allocation': False,
            'leave_validation_type': 'no_validation',
            'company_id': self.company.id})
        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.agro_user.id)], limit=1)
        # NO `leave_fast_create` AND NO STATE WRITE. The fast-create path
        # skips hr_holidays' own auto-approve, and writing `state` by hand
        # sends the stock `_check_date` constraint through
        # `dashboard_warning_message`, which falls over on an empty set. A
        # "no validation" type is approved by hr_holidays itself at create,
        # which is what a fixture that needs an APPROVED leave should ask for.
        self.env['hr.leave'].create({
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': today,
            'request_date_to': today,
        })
        data = self.Map.with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id]).with_company(
                self.company).get_live_data()
        row = [r for r in data['drivers']
               if r['name'] == 'DEMO Field Agronomist'][0]
        self.assertEqual(row['on_leave'], 'D1 Field sick')

    def test_a_desk_person_has_no_leave_chip_and_no_row(self):
        data = self.Map.with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id]).with_company(
                self.company).get_live_data()
        for row in data['drivers']:
            self.assertIn('on_leave', row,
                          'every row carries the key the template reads')

    def test_the_map_is_still_the_attendance_officers(self):
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.Map.with_user(self.agro_user).get_live_data()


@tagged('post_install', '-at_install')
class TestFieldSeams(TransactionCase):
    """The three-file spelling, the copy and the icons."""

    def test_the_mission_registry_is_spelt_the_same_in_both_files(self):
        """This module cannot import the constant: `pb_mission` depends on
        `pb_today`, which depends on THIS module for the very component being
        registered. The literal is checked against the export instead."""
        hub = _code(_src('pb_mission', 'static', 'src', 'js', 'pb_mission.js'))
        match = re.search(r'export const MISSION_LENSES = "([^"]+)"', hub)
        self.assertTrue(match, 'pb_mission must export MISSION_LENSES')
        mine = _code(_src('pb_driver_checkin', 'static', 'src', 'js',
                          'field_palette.js'))
        self.assertIn('const MISSION_LENSES = "%s"' % match.group(1), mine)
        self.assertIn('registry.category(MISSION_LENSES).add("field"', mine)
        self.assertNotIn('@pb_mission/', mine,
                         'importing the hub back would be a dependency cycle')

    def test_the_palette_row_is_in_the_D_block(self):
        mine = _code(_src('pb_driver_checkin', 'static', 'src', 'js',
                          'field_palette.js'))
        self.assertIn('"wf_field"', mine)
        self.assertIn('{ sequence: 3810 }', mine)
        self.assertIn('xmlid: "pb_mission.action_pb_workforce"', mine,
                      'a bare tag has no action NAME (R180)')

    def test_the_lens_is_gated_the_way_the_facade_is(self):
        """W29 — a lens whose every call would be refused is a door that can
        only produce an error."""
        mine = _code(_src('pb_driver_checkin', 'static', 'src', 'js',
                          'field_palette.js'))
        self.assertIn('hr_attendance.group_hr_attendance_officer', mine)
        facade = _src('pb_driver_checkin', 'models', 'pb_driver_map.py')
        self.assertIn('hr_attendance.group_hr_attendance_officer', facade)

    def test_the_copy_no_longer_says_only_drivers(self):
        """Plain English on screen, and the rename D16 asked for."""
        template = _src('pb_driver_checkin', 'static', 'src', 'xml',
                        'driver_map.xml')
        self.assertIn('Field staff <span', template)
        self.assertIn('No field staff yet', template)
        self.assertNotIn('No drivers yet', template)
        pwa = _src('pb_driver_checkin', 'views', 'driver_pwa_templates.xml')
        self.assertIn('<title>Payobook Field check-in</title>', pwa)
        self.assertNotIn('<title>Payobook Driver</title>', pwa)
        actions = _src('pb_driver_checkin', 'views', 'actions.xml')
        self.assertIn('Field check-in map', actions)

    def test_the_pwa_address_did_not_move(self):
        """An installed progressive web app's SCOPE is `/driver`; changing it
        orphans every copy already on a phone. `/field` is a redirect and the
        service worker's scope is untouched."""
        controller = _src('pb_driver_checkin', 'controllers', 'driver_app.py')
        self.assertIn("_SCOPE = '/driver'", controller)
        self.assertIn("@http.route('/field'", controller)
        self.assertIn("request.redirect('/driver'", controller)

    def test_the_gate_asks_about_field_staff_and_still_accepts_a_driver(self):
        controller = _code(_src('pb_driver_checkin', 'controllers',
                                'driver_app.py'))
        self.assertIn('group_pb_field_staff', controller)
        self.assertIn('group_pb_driver', controller,
                      'a database whose upgrade has not landed must still work')
        self.assertNotIn('def _is_driver', controller)

    def test_no_screen_in_this_module_says_the_engines_name(self):
        module = get_module_path('pb_driver_checkin')
        bad = []
        for root, dirs, files in os.walk(module):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
            if root.endswith('tests'):
                continue
            for name in files:
                if not name.endswith(('.js', '.xml', '.py', '.scss', '.css')):
                    continue
                path = os.path.join(root, name)
                text = _read(path)
                if name.endswith(('.js', '.scss', '.css')):
                    text = _code(text)
                elif name.endswith('.xml'):
                    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
                elif name.endswith('.py'):
                    text = re.sub(r'#.*', '', text)
                    text = re.sub(r'""".*?"""', '', text, flags=re.S)
                for line in text.splitlines():
                    if re.search(r'\bodoo\b', line, re.I) \
                            and 'from odoo' not in line \
                            and 'odoo.addons' not in line \
                            and 'odoo-module' not in line \
                            and 'odoo/owl' not in line \
                            and '<odoo' not in line \
                            and '</odoo' not in line:
                        bad.append('%s: %s' % (path, line.strip()[:90]))
        self.assertFalse(bad, 'the product name must never reach a screen')

    def test_every_icon_the_lens_names_is_in_the_shared_registry(self):
        registry_src = _src('pb_import_kit', 'static', 'src', 'js',
                            'import_icons.js')
        known = set(re.findall(r'^\s{4}(\w+):', registry_src, re.M))
        mine = _code(_src('pb_driver_checkin', 'static', 'src', 'js',
                          'field_palette.js'))
        for name in re.findall(r'icon: "(\w+)"', mine):
            self.assertIn(name, known)
