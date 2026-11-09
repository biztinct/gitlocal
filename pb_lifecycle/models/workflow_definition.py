"""Pure, bounded workflow/form validation. No eval and no database writes."""
import copy
import datetime
import json
import math
import re

SCHEMA = 'payobook.workflow/1'
GROUPS = ('branch', 'parallel', 'subprocess')
TYPES = ('trigger', 'task', 'input', 'matrix', 'email', 'wait', 'branch',
         'parallel', 'subprocess', 'action', 'reference')
FORM_TYPES = ('text', 'textarea', 'number', 'date', 'email', 'select',
              'multiselect', 'boolean', 'file', 'rows', 'section')
OPS = ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'contains', 'set')
IDENT = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,79}$')
MAX_NODES, MAX_FIELDS = 200, 80


def fresh(name='New workflow'):
    return {'schema': SCHEMA, 'name': name, 'stages': [
        {'name': 'Prepare'}, {'name': 'Do the work'}, {'name': 'Finish'}],
        'order': ['trigger'], 'nodes': [
            {'id': 'trigger', 'type': 'trigger', 'title': 'Start', 'stage': 0}],
        'scope': {'match': 'all', 'rules': []},
        'trigger': {'kind': 'manual', 'fields': [], 'date_field': '',
                    'delay': 0, 'unit': 'day'}}


def containers(d):
    yield {'key': 'main', 'ids': d.get('order', [])}
    for n in d.get('nodes', []):
        for b in n.get('branches', []):
            yield {'key': b['id'], 'ids': b.get('steps', []), 'parent': n}
        if n.get('type') == 'subprocess':
            yield {'key': n['id'], 'ids': n.get('steps', []), 'parent': n}


def descendants(d, ident):
    nodes = {n['id']: n for n in d['nodes']}
    seen, result = set(), []
    def visit(key):
        if key in seen or key not in nodes:
            return
        seen.add(key)
        result.append(key)
        n = nodes[key]
        for b in n.get('branches', []):
            for child in b.get('steps', []):
                visit(child)
        for child in n.get('steps', []):
            visit(child)
    visit(ident)
    return result


def matches(rule, values):
    value, expected = values.get(rule.get('field')), rule.get('value')
    op = rule.get('op')
    if op == 'set':
        return value is not None and value != '' and value != []
    if value is None:
        return False
    if op == 'eq':
        return type(value) is type(expected) and value == expected or (
            type(value) in (int, float) and type(expected) in (int, float)
            and value == expected)
    if op == 'ne':
        return not matches(dict(rule, op='eq'), values)
    if op == 'contains':
        return (isinstance(value, (str, list)) and
                isinstance(expected, str) and expected in value)
    if type(value) not in (int, float) or type(expected) not in (int, float):
        return False
    return {'gt': value > expected, 'gte': value >= expected,
            'lt': value < expected, 'lte': value <= expected}.get(op, False)


def visible(field, answers):
    rule = field.get('visible_if')
    return not rule or matches(rule, answers)


def form_errors(form):
    errors, known = [], set()
    fields = form.get('fields', []) if isinstance(form, dict) else []
    if not isinstance(fields, list) or len(fields) > MAX_FIELDS:
        return ['Use at most 80 fields in a form.']
    if not fields:
        return ['Add a field to the form.']
    for f in fields:
        if not isinstance(f, dict):
            return ['A form field is not valid.']
        key = f.get('id', '')
        if not IDENT.fullmatch(key) or key in known:
            errors.append('Give each field a unique identifier.')
        if not str(f.get('label', '')).strip():
            errors.append('Give each field a label.')
        if f.get('type') not in FORM_TYPES:
            errors.append('Choose a supported field type.')
        rule = f.get('visible_if')
        if rule and (not isinstance(rule, dict) or rule.get('field') not in known
                     or rule.get('op') not in OPS):
            errors.append('Show a field using an earlier answer.')
        if f.get('type') in ('select', 'multiselect'):
            opts = f.get('options', [])
            if (not isinstance(opts, list) or not 1 <= len(opts) <= 100 or
                    any(not isinstance(o, str) or not o.strip() for o in opts)
                    or len(set(opts)) != len(opts)):
                errors.append('Add distinct choices to the dropdown.')
        if f.get('min') is not None and type(f['min']) not in (int, float):
            errors.append('Use a number for the minimum.')
        known.add(key)
    return errors


def validate_answers(form, values, prefills=None, partial=False):
    if not isinstance(values, dict) or len(json.dumps(values)) > 500000:
        return {}, {'_form': 'These answers are too large or not valid.'}
    cleaned, errors = {}, {}
    source = {**values, **(prefills or {})}
    for f in form.get('fields', []):
        key, kind = f['id'], f['type']
        if kind == 'section' or not visible(f, cleaned):
            continue
        value = source.get(key)
        empty = value is None or value == '' or value == []
        if empty:
            if f.get('required') and not partial:
                errors[key] = 'Please complete this field.'
            continue
        problem = None
        if kind in ('text', 'textarea', 'email', 'date', 'select'):
            if not isinstance(value, str) or len(value) > 10000:
                problem = 'Enter a shorter text answer.'
            elif kind == 'email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
                problem = 'Enter an email address.'
            elif kind == 'date':
                try:
                    datetime.date.fromisoformat(value)
                except ValueError:
                    problem = 'Choose a valid date.'
            elif kind == 'select' and value not in f.get('options', []):
                problem = 'Choose one of the listed options.'
        elif kind == 'number':
            if type(value) not in (int, float) or not math.isfinite(value):
                problem = 'Enter a number.'
            elif f.get('min') is not None and value < f['min']:
                problem = 'Enter at least %s.' % f['min']
        elif kind == 'boolean' and type(value) is not bool:
            problem = 'Choose Yes or No.'
        elif kind == 'multiselect':
            if (not isinstance(value, list) or len(value) > 100 or
                    any(v not in f.get('options', []) for v in value)):
                problem = 'Choose from the listed options.'
        elif kind == 'file':
            if (not isinstance(value, list) or len(value) > 10 or
                    any(type(v) is not int or v < 1 for v in value)):
                problem = 'Attach a file using the upload control.'
        elif kind == 'rows':
            if not isinstance(value, list) or len(value) > 100:
                problem = 'Use up to 100 line items.'
            elif any(not isinstance(v, dict) or
                     not isinstance(v.get('description'), str) or
                     not v['description'].strip() or
                     type(v.get('amount')) not in (int, float) or
                     not math.isfinite(v['amount']) or v['amount'] < 0
                     for v in value):
                problem = 'Each line needs a description and a positive amount.'
        if problem:
            errors[key] = problem
        else:
            cleaned[key] = value
    return cleaned, errors


def validate(d, source_fields=None, actions=None, approval=False):
    """Return user-facing issues. Shape is checked before any recursive walk."""
    out = []
    def error(node, text):
        out.append({'id': node, 'text': text, 'severity': 'error'})
    if not isinstance(d, dict) or len(json.dumps(d)) > 1000000:
        return [{'id': 'trigger', 'text': 'This workflow is too large.', 'severity': 'error'}]
    if d.get('schema') != SCHEMA:
        error('trigger', 'This workflow format is not supported.')
    raw, stages, order = d.get('nodes'), d.get('stages'), d.get('order')
    if (not isinstance(raw, list) or not 1 <= len(raw) <= MAX_NODES or
            not isinstance(stages, list) or not 1 <= len(stages) <= 40 or
            any(not isinstance(s, dict) or not str(s.get('name', '')).strip() for s in stages) or
            not isinstance(order, list)):
        error('trigger', 'Use 1–40 stages and at most 200 steps.')
        return out
    if not str(d.get('name', '')).strip():
        error('trigger', 'Give the workflow a name.')
    nodes, groups, branch_ids = {}, {}, set()
    for n in raw:
        if not isinstance(n, dict) or not IDENT.fullmatch(str(n.get('id', ''))):
            error('trigger', 'A step identifier is not valid.')
            return out
        if n['id'] in nodes or n.get('type') not in TYPES:
            error(n['id'], 'Each step needs a unique identifier and supported type.')
        nodes[n['id']] = n
        if (type(n.get('stage')) is not int or not 0 <= n['stage'] < len(stages)
                or not str(n.get('title', '')).strip()):
            error(n['id'], 'Give the step a name and a stage.')
        if n.get('type') in ('branch', 'parallel'):
            bs = n.get('branches')
            if not isinstance(bs, list) or not 2 <= len(bs) <= 10:
                error(n['id'], 'Use two to ten paths in a group.')
                return out
            for b in bs:
                if (not isinstance(b, dict) or not IDENT.fullmatch(str(b.get('id', '')))
                        or b['id'] in branch_ids or not isinstance(b.get('steps'), list)):
                    error(n['id'], 'Each path needs its own identifier and steps.')
                    return out
                branch_ids.add(b['id'])
                groups[b['id']] = (n, b['steps'])
        if n.get('type') == 'subprocess' and not isinstance(n.get('steps'), list):
            error(n['id'], 'A saved group needs a list of steps.')
            return out
    if out:
        return out
    if branch_ids.intersection(nodes):
        error('trigger', 'A path and a step cannot share an identifier.')
    if order[:1] != ['trigger'] or sum(n['type'] == 'trigger' for n in raw) != 1:
        error('trigger', 'Keep one start at the beginning.')
    counts, parents = {}, {}
    for c in containers(d):
        for key in c['ids']:
            if not isinstance(key, str) or key not in nodes:
                error('trigger', 'A step reference is missing.')
                continue
            counts[key] = counts.get(key, 0) + 1
            if c.get('parent'):
                parents[key] = c['parent']['id']
                if nodes[key]['stage'] != c['parent']['stage']:
                    error(key, 'Keep grouped work in its group’s stage.')
    for key in nodes:
        if counts.get(key) != 1:
            error(key, 'Each step must belong to exactly one path.')
    if out:
        return out
    visiting, done = set(), set()
    def cycle(key, depth=0):
        if key in visiting or depth > 12:
            return True
        if key in done:
            return False
        visiting.add(key)
        n = nodes[key]
        children = [x for b in n.get('branches', []) for x in b['steps']] + n.get('steps', [])
        if any(cycle(child, depth+1) for child in children):
            return True
        visiting.remove(key)
        done.add(key)
        return False
    if any(cycle(key) for key in nodes):
        error('trigger', 'A group cannot contain itself. Use at most twelve nested groups.')
        return out
    if any(nodes[a]['stage'] > nodes[b]['stage'] for a, b in zip(order, order[1:])):
        error('trigger', 'Keep steps in their stage order.')
    base = set(source_fields or ()) | {'amount', 'urgent'}
    def condition(rule, available, ident):
        if (not isinstance(rule, dict) or rule.get('field') not in available
                or rule.get('op') not in OPS):
            error(ident, 'Choose an available value and comparison.')
    def walk(ids, available):
        available = set(available)
        for key in ids:
            n = nodes[key]
            kind = n['type']
            if kind in ('task', 'input'):
                owner = n.get('owner', {})
                if not isinstance(owner, dict) or owner.get('kind') not in ('initiator', 'user') or (
                        owner.get('kind') == 'user' and type(owner.get('id')) is not int):
                    error(key, 'Choose who does this step.')
                if type(n.get('due', 2)) is not int or not 1 <= n.get('due', 2) <= 365:
                    error(key, 'Choose a deadline from 1 to 365 days.')
            if kind == 'input':
                for text in form_errors(n.get('form')):
                    error(key, text)
                for f in n.get('form', {}).get('fields', []):
                    if f.get('prefill') and f['prefill'] not in base:
                        error(key, 'Choose an available record field for the prefill.')
                    available.add('step.%s.%s' % (key, f.get('id')))
            if kind == 'matrix':
                if key not in order:
                    error(key, 'Keep approval on the main path.')
            if kind == 'email' and type(n.get('template_id')) is not int:
                error(key, 'Choose an existing email template.')
            if kind == 'wait' and (type(n.get('hours')) not in (int, float) or not 0 < n['hours'] <= 8760):
                error(key, 'Set a wait of up to one year.')
            if kind == 'action' and n.get('action_key') not in (actions or {}):
                error(key, 'Choose an available business action.')
            if kind == 'reference' and not n.get('owner_key'):
                error(key, 'Choose the existing behaviour to reference.')
            if kind in ('branch', 'parallel'):
                branches = n['branches']
                if kind == 'branch' and (branches[-1].get('condition') or
                        sum(not b.get('condition') for b in branches) != 1):
                    error(key, 'Keep one Otherwise path, last.')
                if kind == 'parallel' and (n.get('join') not in ('all', 'any') or
                        any(not b['steps'] for b in branches)):
                    error(key, 'Choose a join and add work to every parallel path.')
                if kind == 'parallel' and n.get('join') == 'any' and any(
                        nodes[x]['type'] in ('matrix', 'email', 'action')
                        for x in descendants(d, key)):
                    error(key, 'Use “Everyone finishes” for paths with approvals or automatic effects.')
                for b in branches:
                    if b.get('condition'):
                        condition(b['condition'], available, key)
                    walk(b['steps'], available)
            if kind == 'subprocess':
                if not n['steps']:
                    error(key, 'Add a step to this saved group.')
                available = walk(n['steps'], available)
        return available
    walk(order, base)
    matrix = [n for n in raw if n['type'] == 'matrix']
    if len(matrix) > 1:
        error('trigger', 'Use one Approval Matrix step.')
    if matrix and matrix[0]['id'] in order:
        at = order.index(matrix[0]['id'])
        if any(nodes[x]['type'] == 'input' for top in order[at+1:] for x in descendants(d, top)):
            error(matrix[0]['id'], 'Keep required information before approval.')
    if approval and not matrix:
        error('trigger', 'Use the existing Approval Matrix for this process.')
    scope = d.get('scope', {})
    if not isinstance(scope, dict) or scope.get('match') not in ('all', 'any') or not isinstance(scope.get('rules'), list):
        error('trigger', 'Choose how the workflow filters should match.')
    else:
        for rule in scope['rules']:
            condition(rule, base, 'trigger')
    trigger = d.get('trigger', {})
    if not isinstance(trigger, dict) or trigger.get('kind') not in ('manual', 'created', 'changed', 'date', 'approval_applied'):
        error('trigger', 'Choose when this workflow starts.')
    elif trigger['kind'] == 'changed' and (not trigger.get('fields') or any(f not in base for f in trigger['fields'])):
        error('trigger', 'Choose the specific fields that start this workflow.')
    return out


def route_preview(d, values):
    """An explicit simulation: no effects, database records or fake approvals."""
    nodes, rows = {n['id']: n for n in d['nodes']}, []
    def visit(ids, path='Main path'):
        for key in ids:
            n = nodes[key]
            rows.append({'id': key, 'title': n['title'], 'type': n['type'], 'path': path})
            if n['type'] == 'branch':
                selected = next(b for b in n['branches'] if not b.get('condition') or matches(b['condition'], values))
                rows[-1]['reason'] = selected['label']
                visit(selected['steps'], selected['label'])
            elif n['type'] == 'parallel':
                for b in n['branches']:
                    visit(b['steps'], b['label'])
            elif n['type'] == 'subprocess':
                visit(n['steps'], n['title'])
    visit(d['order'])
    return rows
