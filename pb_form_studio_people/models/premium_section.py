"""A presentation of native fields, never a separate employee write API.

Project the already postprocessed full form: installed view rules, field ACLs,
translations, Form builder labels and modifiers remain authoritative. Full
Details is not modified or cached under the section's key.
"""
from copy import deepcopy
from lxml import etree
from odoo import api, models

JOB_FIELDS = ('department_id', 'job_id', 'job_title', 'parent_id',
              'work_location_id', 'address_id')


def _root_fields(arch):
    return arch.xpath('.//field[not(ancestor::field)]')


def project_job_form(arch, titles):
    source = etree.fromstring(arch)
    root = etree.Element('form', dict(source.attrib))
    root.set('class', 'vu-form-native pb-premium-section')
    root.set('create', 'false')
    root.set('delete', 'false')
    grid = etree.SubElement(root, 'div', {'class': 'pb-job-grid'})
    fields = _root_fields(source)
    selected = set()
    for title, names in zip(titles, (('department_id', 'job_id', 'job_title'),
                                    ('parent_id', 'work_location_id', 'address_id'))):
        card = etree.SubElement(grid, 'section', {'class': 'pb-job-card'})
        etree.SubElement(card, 'h3').text = title
        for name in names:
            candidates = [node for node in fields if node.get('name') == name]
            if not candidates:
                continue  # Never recreate a field removed by access or view rules.
            node = next((n for n in candidates if n.get('invisible') not in ('1', 'True', 'true')), candidates[0])
            holder = card
            # Preserve ancestor visibility/security. Each wrapper retains its own
            # group semantics, rather than incorrectly flattening them into OR.
            for ancestor in reversed(list(node.iterancestors())):
                attrs = {k: ancestor.get(k) for k in ('invisible', 'groups') if ancestor.get(k)}
                if attrs:
                    holder = etree.SubElement(holder, 'div', attrs)
            attrs = {'class': 'pb-job-field'}
            if node.get('invisible'):
                attrs['invisible'] = node.get('invisible')
            holder = etree.SubElement(holder, 'div', attrs)
            field = deepcopy(node)
            field.set('id', 'premium_job_' + name)
            label = {'for': 'premium_job_' + name}
            if node.get('string'):
                label['string'] = node.get('string')
            etree.SubElement(holder, 'label', label)
            holder.append(field)
            selected.add(name)
    # Keep the original form's onchange/dependency graph. Non-displayed fields
    # do not become editors, but dependent domains and native computed fields
    # still receive the values the full form would receive.
    hidden = etree.SubElement(root, 'div', {'invisible': '1'})
    for node in fields:
        if node.get('name') in selected:
            continue
        field = deepcopy(node)
        field.set('invisible', '1')
        field.attrib.pop('id', None)
        field.attrib.pop('widget', None)
        hidden.append(field)
    return etree.tostring(root, encoding='unicode')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type == 'form' and options.get('pb_workspace_section') == 'job':
            result = dict(result)
            result['arch'] = project_job_form(result['arch'],
                (self.env._('Role & organisation'), self.env._('Reporting & workplace')))
        return result
