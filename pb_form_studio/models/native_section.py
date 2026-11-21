"""Project processed native fields into premium cards; never write records."""
import ast
from copy import deepcopy
from lxml import etree


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


def project_section_form(arch, groups, domains=None, blocks=(), excluded=()):
    source = etree.fromstring(arch)
    root = etree.Element('form', dict(source.attrib))
    root.set('class', 'vu-form-native pb-premium-section')
    root.set('create', 'false')
    root.set('delete', 'false')
    grid = etree.SubElement(root, 'div', {'class': 'pb-job-grid'})
    excluded = set(excluded)
    fields = [n for n in _root_fields(source) if n.get('name') not in excluded]
    selected = set()
    dependencies = {"company_id", "active", "version_id"}
    available = {node.get("name") for node in fields}
    domains = domains or {}
    for title, names in groups:
        card = etree.SubElement(grid, 'section', {'class': 'pb-job-card'})
        etree.SubElement(card, 'h3').text = title
        visibility = []
        for name in names:
            candidates = [node for node in fields if node.get('name') == name]
            if not candidates:
                continue  # Never recreate a field removed by access or view rules.
            node = next((n for n in candidates if n.get('invisible') not in ('1', 'True', 'true')), candidates[0])
            hidden_rules = [a.get('invisible') for a in [node, *node.iterancestors()] if a.get('invisible')]
            visibility.append(' or '.join('(' + v + ')' for v in hidden_rules) or 'False')
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
            # The name keeps its native widget/validation, not hero typography.
            if name == 'name':
                field.attrib.pop('style', None)
            label = {'for': 'premium_job_' + name}
            if node.get('string'):
                label['string'] = node.get('string')
            etree.SubElement(holder, 'label', label)
            holder.append(field)
            selected.add(name)
            dependencies.update(node.get(attr) for attr in ('filename', 'currency_field') if node.get(attr) in available)
            dependencies.update(_references(
                [value for parent in [node, *node.iterancestors()]
                 for attr, value in parent.attrib.items()
                 if attr in ('invisible', 'readonly', 'required', 'domain', 'context')]
                + [domains.get(name, '')], available))
        if visibility and 'False' not in visibility:
            card.set('invisible', ' and '.join('(' + v + ')' for v in visibility))
        if not card.xpath('.//field'):
            grid.remove(card)
    for title, selector in blocks:
        for node in source.xpath(selector):
            block_names = {n.get('name') for n in _root_fields(node)}
            if node.tag == 'field':
                block_names.add(node.get('name'))
            if block_names & excluded:
                continue
            card = etree.SubElement(grid, 'section', {'class': 'pb-job-card pb-native-block'})
            etree.SubElement(card, 'h3').text = title
            holder = card
            for ancestor in reversed(list(node.iterancestors())):
                attrs = {k: ancestor.get(k) for k in ('invisible', 'groups') if ancestor.get(k)}
                if attrs:
                    holder = etree.SubElement(holder, 'div', attrs)
            block = deepcopy(node)
            if block.tag in ('page', 'group'):
                block.tag = 'div'
                for attr in ('string', 'name', 'col', 'colspan'):
                    block.attrib.pop(attr, None)
            holder.append(block)
            hidden_rules = [a.get('invisible') for a in [node, *node.iterancestors()] if a.get('invisible')]
            if hidden_rules:
                card.set('invisible', ' or '.join('(' + v + ')' for v in hidden_rules))
            selected.update(n.get('name') for n in _root_fields(card))
    # Widgets and preserved action blocks have dependencies too (including
    # file-name fields, hidden siblings and context expressions).
    for node in root.iter():
        dependencies.update(_references([v for k, v in node.attrib.items()
            if k in ('invisible', 'readonly', 'required', 'domain', 'context', 'options')], available))
        if node.tag == 'field' and not any(a.tag == 'field' for a in node.iterancestors()):
            dependencies.update(_references([domains.get(node.get('name'), '')], available))
            dependencies.update(node.get(attr) for attr in ('filename', 'currency_field') if node.get(attr) in available)
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

