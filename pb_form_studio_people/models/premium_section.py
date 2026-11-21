"""A presentation of native fields, never a separate employee write API.

Project the already postprocessed full form: installed view rules, field ACLs,
translations, Form builder labels and modifiers remain authoritative. Full
Details is not modified or cached under the section's key.
"""
import ast
from copy import deepcopy
from lxml import etree
from odoo import api, models

JOB_FIELDS = ('department_id', 'job_id', 'job_title', 'parent_id',
              'work_location_id', 'address_id')


def _root_fields(arch):
    return arch.xpath('.//field[not(ancestor::field)]')


def _references(expressions, names):
    refs = set()
    for expression in expressions:
        try:
            refs.update(node.id for node in ast.walk(ast.parse(expression, mode='eval'))
                        if isinstance(node, ast.Name) and node.id in names)
        except (SyntaxError, TypeError):
            continue
    return refs


def project_job_form(arch, titles, domains=None):
    source = etree.fromstring(arch)
    root = etree.Element('form', dict(source.attrib))
    root.set('class', 'vu-form-native pb-premium-section')
    root.set('create', 'false')
    root.set('delete', 'false')
    grid = etree.SubElement(root, 'div', {'class': 'pb-job-grid'})
    fields = _root_fields(source)
    selected = set()
    dependencies = {"company_id", "active", "version_id"}
    available = {node.get("name") for node in fields}
    domains = domains or {}
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
            dependencies.update(_references(
                [value for parent in [node, *node.iterancestors()]
                 for attr, value in parent.attrib.items()
                 if attr in ('invisible', 'readonly', 'required', 'domain', 'context')]
                + [domains.get(name, '')], available))
    # Include only dependency fields, not unrelated payroll/private x2many
    # collections. Keeping those collections would require payroll access just
    # to edit a job. Helpers are data for native domains/onchanges, never editors.
    hidden = etree.SubElement(root, 'div', {'invisible': '1'})
    kept = set(selected)
    while dependencies - kept:
        name = (dependencies - kept).pop()
        kept.add(name)
        candidates = [node for node in fields if node.get('name') == name]
        if not candidates:
            continue
        node = candidates[0]
        field = deepcopy(node)
        field.set('invisible', '1')
        for attr in ('id', 'widget', 'required', 'readonly'):
            field.attrib.pop(attr, None)
        hidden.append(field)
        dependencies.update(_references(
            [value for attr, value in field.attrib.items() if attr in ('domain', 'context')]
            + [domains.get(name, '')], available))
    return etree.tostring(root, encoding='unicode')


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id, view_type, **options)
        if view_type == 'form' and options.get('pb_workspace_section') == 'job':
            result = dict(result)
            result['arch'] = project_job_form(result['arch'],
                (self.env._('Role & organisation'), self.env._('Reporting & workplace')),
                {name: field.get('domain', '') for name, field in
                 self.fields_get(attributes=['domain']).items()})
        return result
