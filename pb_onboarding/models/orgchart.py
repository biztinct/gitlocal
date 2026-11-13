"""Read-only, company-scoped directory. Never serialize an employee record."""
from odoo import models
from odoo.exceptions import AccessError


def normalize_hierarchy(people):
    """Cut missing/cyclic edges, without modifying HR data; O(n) traversal."""
    by_id = {p['id']: p for p in people}
    for person in people:
        if person['manager_id'] not in by_id:
            person['manager_id'] = None
    done = set()
    for person in people:
        path, visiting, node = [], set(), person
        while node and node['id'] not in done:
            if node['id'] in visiting:
                node['manager_id'] = None
                node['hierarchy_note'] = True
                break
            visiting.add(node['id'])
            path.append(node['id'])
            node = by_id.get(node['manager_id'])
        done.update(path)
    return people


class OrgchartHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    def _orgchart_data(self, employee):
        # Private method: not callable through RPC. Validate the session even
        # when called from a controller; sudo is limited to this company.
        employee = employee.sudo().exists()
        if len(employee) != 1 or employee.user_id.id != self.env.uid or not employee.active:
            raise AccessError('An active employee account is required.')
        employees = self.env['hr.employee'].sudo().search_fetch([
            ('company_id', '=', employee.company_id.id), ('active', '=', True),
        ], ['name', 'job_title', 'department_id', 'parent_id', 'work_email'], order='name, id')
        visible = set(employees.ids)
        people = []
        for person in employees:
            manager = person.parent_id.id
            people.append({
                'id': person.id, 'name': person.name or '',
                'job': person.job_title or '',
                'department_id': person.department_id.id or 0,
                'department': person.department_id.name or '',
                'email': person.work_email or '',
                'avatar': '/my/photo/%s/avatar_128' % person.id,
                'manager_id': manager if manager in visible else None,
                'hierarchy_note': bool(manager and manager not in visible),
            })
        return {'me': employee.id, 'company': employee.company_id.name,
                'people': normalize_hierarchy(people)}
