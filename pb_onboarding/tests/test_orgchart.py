"""Exercise the real route, portal-only access, scope and damaged reporting lines."""
import json
from lxml import html
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from ..models.orgchart import normalize_hierarchy


@tagged('post_install', '-at_install')
class TestOrganisationChart(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Org chart test company'})
        cls.other_company = cls.env['res.company'].create({'name': 'Other chart company'})
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Chart Portal User', 'login': 'test_orgchart_portal',
            'password': 'Chart-Test-Only-2026',
            'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        Emp = cls.env['hr.employee']
        cls.manager = Emp.create({'name': 'Chart Manager', 'company_id': cls.company.id})
        cls.employee = Emp.create({
            'name': 'Chart <script>person</script>', 'company_id': cls.company.id,
            'user_id': cls.user.id, 'parent_id': cls.manager.id,
            'work_email': 'chart@example.invalid', 'private_email': 'private@example.invalid',
        })
        cls.foreign = Emp.create({'name': 'Foreign Secret Manager', 'company_id': cls.other_company.id})
        cls.archived = Emp.create({'name': 'Archived Colleague', 'company_id': cls.company.id, 'active': False})

    def _payload(self):
        return self.env['pb.me.home'].with_user(self.user)._orgchart_data(self.employee)

    def test_portal_scope_and_whitelist(self):
        payload = self._payload()
        self.assertEqual({p['id'] for p in payload['people']}, {self.employee.id, self.manager.id})
        self.assertEqual(payload['me'], self.employee.id)
        self.assertNotIn('private@example.invalid', json.dumps(payload))
        self.assertEqual(set(payload['people'][0]), {
            'id', 'name', 'job', 'department_id', 'department', 'email',
            'avatar', 'manager_id', 'hierarchy_note',
        })

    def test_rejects_another_employees_identity(self):
        with self.assertRaises(AccessError):
            self.env['pb.me.home'].with_user(self.user)._orgchart_data(self.manager)

    def test_foreign_and_archived_managers_are_not_exposed(self):
        for manager in (self.foreign, self.archived):
            # Simulate an imported invalid relation without changing production data.
            self.env.cr.execute('UPDATE hr_employee SET parent_id=%s WHERE id=%s', (manager.id, self.employee.id))
            self.employee.invalidate_recordset(['parent_id'])
            person = next(p for p in self._payload()['people'] if p['id'] == self.employee.id)
            self.assertIsNone(person['manager_id'])
            self.assertTrue(person['hierarchy_note'])
            self.assertNotIn(manager.name, json.dumps(self._payload()))

    def test_cycles_and_deep_hierarchies_terminate(self):
        for graph in ([{'id': 1, 'manager_id': 1}],
                      [{'id': 1, 'manager_id': 2}, {'id': 2, 'manager_id': 1}],
                      [{'id': i, 'manager_id': i - 1} for i in range(1, 5001)]):
            normalized = normalize_hierarchy(graph)
            self.assertTrue(any(p['manager_id'] is None for p in normalized))
            lookup = {p['id']: p for p in normalized}
            for person in normalized[:3]:
                seen = set()
                while person:
                    self.assertNotIn(person['id'], seen)
                    seen.add(person['id']); person = lookup.get(person['manager_id'])

    def test_http_page_and_forged_focus(self):
        self.authenticate(self.user.login, 'Chart-Test-Only-2026')
        for value in (str(self.foreign.id), str(self.archived.id), 'invalid', str(self.employee.id)):
            response = self.url_open('/my/orgchart?focus=' + value)
            self.assertEqual(response.status_code, 200)
            document = html.fromstring(response.content)
            payload = json.loads(document.xpath('//*[@data-orgchart]/@data-orgchart')[0])
            self.assertEqual(payload['focus'], self.employee.id if value == str(self.employee.id) else 0)
            self.assertNotIn(self.foreign.name, response.text)
            self.assertFalse(document.xpath('//script[contains(text(),"Chart <script>")]'))
            self.assertIn('Organisation chart', response.text)
        home = self.url_open('/my')
        self.assertEqual(home.status_code, 200)
        self.assertIn('pborg-home-link', home.text)

    def test_non_employee_has_no_chart(self):
        self.employee.user_id = False
        self.authenticate(self.user.login, 'Chart-Test-Only-2026')
        response = self.url_open('/my/orgchart')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('data-orgchart=', response.text)
