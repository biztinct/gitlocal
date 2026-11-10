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
              'multiselect', 'boolean', 'file', 'rows', 'section', 'lookup')
OPS = ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'contains', 'icontains', 'not_contains', 'set', 'unset', 'in', 'not_in')
CONTEXT_FIELDS = {'person.user_id', 'person.group_ids', 'workflow.stage', 'workflow.completed_stages'}
IDENT = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{0,79}$')
MAX_NODES, MAX_FIELDS = 200, 80


def fresh(name='New workflow'):
    return {'schema': SCHEMA, 'name': name, 'stages': [
        {'name': 'Prepare'}, {'name': 'Do the work'}, {'name': 'Finish'}],
        'order': ['trigger'], 'nodes': [
            {'id': 'trigger', 'type': 'trigger', 'title': 'Start', 'stage': 0}],
        'scope': {'match': 'all', 'rules': []},
        'trigger': {'kind': 'manual', 'fields': [], 'date_field': '',
                    'delay': 0, 'unit': 'day'},
        # Path decisions read the record as it is when the path is reached.
        # Versions published without this key keep the start snapshot.
        'timing': 'live'}


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
    if not rule:
        return True
    if 'rules' in rule:
        checks = [matches(r, values) for r in rule['rules']]
        return not checks or (all(checks) if rule.get('match') == 'all' else any(checks))
    value, expected = values.get(rule.get('field')), rule.get('value')
    op = rule.get('op')
    if op in ('set', 'unset'):
        filled = value is not None and value != '' and value != []
        return filled if op == 'set' else not filled
    if value is None:
        return False
    if op in ('in', 'not_in'):
        found = isinstance(expected, list) and any(matches(dict(rule, op='eq', value=v), values) for v in expected)
        return found if op == 'in' else not found
    if op == 'eq':
        return type(value) is type(expected) and value == expected or (
            type(value) in (int, float) and type(expected) in (int, float)
            and value == expected)
    if op == 'ne':
        return not matches(dict(rule, op='eq'), values)
    if op in ('contains', 'icontains', 'not_contains'):
        found = (isinstance(value, str) and isinstance(expected, str) and
                 (expected in value if op == 'contains' else expected.casefold() in value.casefold()) or
                 isinstance(value, list) and expected in value)
        return not found if op == 'not_contains' else bool(found)
    if type(value) not in (int, float) or type(expected) not in (int, float):
        if not isinstance(value, str) or not isinstance(expected, str):
            return False
        try:
            value = datetime.datetime.fromisoformat(value)
            expected = datetime.datetime.fromisoformat(expected)
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None) if value.tzinfo else value
            expected = expected.astimezone(datetime.timezone.utc).replace(tzinfo=None) if expected.tzinfo else expected
        except ValueError:
            return False
    return {'gt': value > expected, 'gte': value >= expected,
            'lt': value < expected, 'lte': value <= expected}.get(op, False)


def leaves(rule):
    if not rule:
        return []
    return [r for child in rule.get('rules', []) for r in leaves(child)] if 'rules' in rule else [rule]


def native_domain(rule, types=None):
    """Compile only validated source filters to Odoo's domain language."""
    if not rule or not rule.get('rules', [True]):
        return []
    if 'rules' in rule:
        parts = [native_domain(r, types) for r in rule['rules']]
        return (['&' if rule['match'] == 'all' else '|'] * (len(parts)-1) +
                [term for part in parts for term in part])
    op, value = rule['op'], rule.get('value')
    operator = {'eq': '=', 'ne': '!=', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=',
                'contains': 'like', 'icontains': 'ilike', 'not_contains': 'not ilike', 'in': 'in', 'not_in': 'not in',
                'set': '!=', 'unset': '='}[op]
    if op in ('contains', 'icontains', 'not_contains'):
        value = value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    leaf = [(rule['field'], operator, False if op in ('set', 'unset') else value)]
    # The interpreter treats absent values as non-matches, even for "is not".
    # Native negative domains otherwise also include NULL. Keep both paths equal.
    if op not in ('set', 'unset') and (types or {}).get(rule['field']) in ('char', 'text', 'selection', 'many2one', 'date', 'datetime'):
        return ['&', (rule['field'], '!=', False)] + leaf
    return leaf


def visible(field, answers):
    rule = field.get('visible_if')
    return not rule or matches(rule, answers)


def form_errors(form):
    """Return (code, text) pairs. The code is stable; the text is for people."""
    if not isinstance(form, dict):
        return [('form_missing', 'Add a form with at least one field.')]
    errors, known = [], set()
    fields = form.get('fields', []) if isinstance(form, dict) else []
    if not isinstance(fields, list) or len(fields) > MAX_FIELDS:
        return [('form_too_many_fields', 'Use at most 80 fields in a form.')]
    if not fields:
        return [('form_empty', 'Add a field to the form.')]
    for f in fields:
        if not isinstance(f, dict):
            return [('form_bad_field', 'A form field is not valid.')]
        key = f.get('id', '')
        if not isinstance(key, str) or not IDENT.fullmatch(key) or key in known:
            errors.append(('field_identifier', 'Give each field a unique identifier.'))
        if not str(f.get('label', '')).strip():
            errors.append(('field_label', 'Give each field a label.'))
        if f.get('type') not in FORM_TYPES:
            errors.append(('field_type', 'Choose a supported field type.'))
        rule = f.get('visible_if')
        if rule and (not isinstance(rule, dict) or rule.get('field') not in known
                     or rule.get('op') not in OPS):
            errors.append(('field_visibility', 'Show a field using an earlier answer.'))
        if f.get('type') in ('select', 'multiselect'):
            opts = f.get('options', [])
            if (not isinstance(opts, list) or not 1 <= len(opts) <= 100 or
                    any(not isinstance(o, str) or not o.strip() for o in opts)
                    or len(set(opts)) != len(opts)):
                errors.append(('field_choices', 'Add distinct choices to the dropdown.'))
        if f.get('min') is not None and type(f['min']) not in (int, float):
            errors.append(('field_minimum', 'Use a number for the minimum.'))
        if isinstance(key, str):
            known.add(key)
        if f.get('type') == 'lookup' and not isinstance(f.get('lookup_model'), str):
            errors.append(('field_lookup_model', 'Choose the record type for this field.'))
        if f.get('bind') and f['bind'] not in ('amount', 'urgent'):
            errors.append(('field_binding', 'Choose an available approval value.'))
        if f.get('bind') == 'amount' and f.get('type') != 'number' or f.get('bind') == 'urgent' and f.get('type') != 'boolean':
            errors.append(('field_binding_type', 'Use a number for Amount and a Yes/No field for Urgent.'))
    return errors


def validate_answers(form, values, prefills=None, partial=False):
    if not isinstance(values, dict) or not safe_json(values, 500000):
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
        elif kind == 'lookup' and (type(value) is not int or value < 1):
            problem = 'Choose an available record.'
        elif kind == 'file':
            if (not isinstance(value, list) or len(value) > 10 or
                    any(type(v) is not int or v < 1 for v in value)):
                problem = 'Attach a file using the upload control.'
        elif kind == 'rows':
            if not isinstance(value, list) or len(value) > 100:
                problem = 'Use up to 100 line items.'
            elif any(not isinstance(v, dict) or
                     not isinstance(v.get('description'), str) or
                     not v['description'].strip() or len(v['description']) > 1000 or
                     type(v.get('amount')) not in (int, float) or
                     not math.isfinite(v['amount']) or v['amount'] < 0
                     for v in value):
                problem = 'Each line needs a description and a positive amount.'
        if problem:
            errors[key] = problem
        else:
            cleaned[key] = value
    return cleaned, errors


def _validate(d, source_fields=None, actions=None):
    """Return user-facing issues. Shape is checked before any recursive walk.

    Every issue carries a stable `code`; callers decide by code, never by
    the wording, which is free to change (ledger G2)."""
    out = []
    def error(node, code, text):
        out.append({'id': node, 'code': code, 'text': text, 'severity': 'error'})
    if not isinstance(d, dict) or not safe_json(d, 1000000):
        return [{'id': 'trigger', 'code': 'too_large', 'text': 'This workflow is too large.', 'severity': 'error'}]
    if d.get('schema') != SCHEMA:
        error('trigger', 'bad_schema', 'This workflow format is not supported.')
    if d.get('timing', 'live') != 'live':
        error('trigger', 'bad_timing', 'This workflow timing setting is not supported.')
    raw, stages, order = d.get('nodes'), d.get('stages'), d.get('order')
    if (not isinstance(raw, list) or not 1 <= len(raw) <= MAX_NODES or
            not isinstance(stages, list) or not 1 <= len(stages) <= 40 or
            any(not isinstance(s, dict) or not str(s.get('name', '')).strip() for s in stages) or
            not isinstance(order, list)):
        error('trigger', 'bad_shape', 'Use 1–40 sections and at most 200 steps.')
        return out
    if not str(d.get('name', '')).strip():
        error('trigger', 'missing_name', 'Give the workflow a name.')
    nodes, groups, branch_ids = {}, {}, set()
    for n in raw:
        if not isinstance(n, dict) or not IDENT.fullmatch(str(n.get('id', ''))):
            error('trigger', 'bad_identifier', 'A step identifier is not valid.')
            return out
        if n['id'] in nodes or n.get('type') not in TYPES:
            error(n['id'], 'duplicate_step', 'Each step needs a unique identifier and supported type.')
        nodes[n['id']] = n
        if (type(n.get('stage')) is not int or not 0 <= n['stage'] < len(stages)
                or not str(n.get('title', '')).strip()):
            error(n['id'], 'step_name_section', 'Give the step a name and a section.')
        if n.get('type') in ('branch', 'parallel'):
            bs = n.get('branches')
            if not isinstance(bs, list) or not 2 <= len(bs) <= 10:
                error(n['id'], 'bad_path_group', 'Use two to ten paths in a group.')
                return out
            for b in bs:
                if (not isinstance(b, dict) or not IDENT.fullmatch(str(b.get('id', '')))
                        or b['id'] in branch_ids or not isinstance(b.get('steps'), list)
                        or not isinstance(b.get('label'), str) or not b['label'].strip()):
                    error(n['id'], 'bad_path_group', 'Each path needs its own identifier and steps.')
                    return out
                branch_ids.add(b['id'])
                groups[b['id']] = (n, b['steps'])
        if n.get('type') not in ('branch', 'parallel') and n.get('branches'):
            error(n['id'], 'branches_outside_group', 'Only path groups can contain branches.')
            return out
        if n.get('type') != 'subprocess' and n.get('steps'):
            error(n['id'], 'steps_outside_saved_group', 'Only a saved group can contain a step list.')
            return out
        if n.get('type') == 'subprocess' and not isinstance(n.get('steps'), list):
            error(n['id'], 'bad_saved_group', 'A saved group needs a list of steps.')
            return out
    if out:
        return out
    if branch_ids.intersection(nodes):
        error('trigger', 'shared_identifier', 'A path and a step cannot share an identifier.')
    if not nodes.get('trigger') or nodes['trigger']['type'] != 'trigger':
        error('trigger', 'start_position', 'Keep one start at the beginning.')
        return out
    if order[:1] != ['trigger'] or sum(n['type'] == 'trigger' for n in raw) != 1:
        error('trigger', 'start_position', 'Keep one start at the beginning.')
    counts, parents = {}, {}
    for c in containers(d):
        for key in c['ids']:
            if not isinstance(key, str) or key not in nodes:
                error('trigger', 'step_missing_reference', 'A step reference is missing.')
                continue
            counts[key] = counts.get(key, 0) + 1
            if c.get('parent'):
                parents[key] = c['parent']['id']
                if nodes[key]['stage'] != c['parent']['stage']:
                    error(key, 'group_section_mismatch', 'Keep grouped work in its group’s section.')
    for key in nodes:
        if counts.get(key) != 1:
            error(key, 'one_path_only', 'Each step must belong to exactly one path.')
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
        error('trigger', 'self_nesting', 'A group cannot contain itself. Use at most twelve nested groups.')
        return out
    if any(nodes[a]['stage'] > nodes[b]['stage'] for a, b in zip(order, order[1:])):
        error('trigger', 'section_order', 'Keep steps in their section order.')
    base = set(source_fields) if source_fields is not None else {'amount', 'urgent'}
    def condition(rule, available, ident, depth=0):
        if isinstance(rule, dict) and 'rules' in rule:
            if (depth >= 4 or rule.get('match') not in ('all', 'any') or
                    not isinstance(rule['rules'], list) or not 1 <= len(rule['rules']) <= 20):
                error(ident, 'bad_filter_group', 'Use up to four levels and 20 filters in a group. Remove an empty group.')
                return
            for child in rule['rules']:
                condition(child, available, ident, depth+1)
            return
        if (not isinstance(rule, dict) or rule.get('field') not in available
                or rule.get('op') not in OPS):
            error(ident, 'bad_filter', 'Choose an available value and comparison.')
            return
        if rule['op'] in ('in', 'not_in') and (not isinstance(rule.get('value'), list) or not 1 <= len(rule['value']) <= 100):
            error(ident, 'filter_needs_values', 'Choose one or more values for this filter.')
    def walk(ids, available):
        available = set(available)
        for key in ids:
            n = nodes[key]
            kind = n['type']
            if n.get('when'):
                condition(n['when'], available, key)
                if kind in ('trigger', 'matrix'):
                    error(key, 'filter_not_allowed', 'Start filters belong on Start. Approval decisions belong in the Approval Matrix.')
            if n.get('wait_for'):
                condition(n['wait_for'], available, key)
                if kind != 'wait':
                    error(key, 'wait_condition_misplaced', 'Only a wait step can wait for a condition.')
            if kind in ('task', 'input'):
                owner = n.get('owner', {})
                if not isinstance(owner, dict) or owner.get('kind') not in ('initiator', 'user', 'role', 'manager', 'field') or (
                        owner.get('kind') == 'user' and type(owner.get('id')) is not int):
                    error(key, 'missing_owner', 'Choose who does this step.')
                if type(n.get('due', 2)) is not int or not 1 <= n.get('due', 2) <= 365:
                    error(key, 'bad_deadline', 'Choose a deadline from 1 to 365 days.')
            if kind == 'input':
                problems = form_errors(n.get('form'))
                for code, text in problems:
                    error(key, code, text)
                if problems:
                    continue
                for f in n['form']['fields']:
                    if f.get('prefill') and f['prefill'] not in base:
                        error(key, 'bad_prefill', 'Choose an available record field for the prefill.')
                    available.add('step.%s.%s' % (key, f.get('id')))
            if kind == 'matrix':
                if key not in order:
                    error(key, 'approval_off_main_path', 'Keep approval on the main path.')
                if n.get('mode', 'submit') not in ('follow', 'submit'):
                    error(key, 'bad_approval_mode', 'Choose what this approval step should do.')
            if kind == 'email' and type(n.get('template_id')) is not int:
                error(key, 'email_needs_template', 'Choose an existing email template.')
            if kind == 'wait' and (type(n.get('hours')) not in (int, float) or not 0 < n['hours'] <= 8760):
                error(key, 'bad_wait', 'Set a wait of up to one year.')
            if kind == 'action' and n.get('action_key') not in (actions or {}):
                error(key, 'bad_action', 'Choose an available business action.')
            if kind == 'reference' and not n.get('owner_key'):
                error(key, 'reference_needs_owner', 'Choose the existing behaviour to reference.')
            if kind in ('branch', 'parallel'):
                branches = n['branches']
                if kind == 'branch' and (branches[-1].get('condition') or
                        sum(not b.get('condition') for b in branches) != 1):
                    error(key, 'otherwise_path', 'Keep one Otherwise path, last.')
                if kind == 'parallel' and (n.get('join') not in ('all', 'any') or
                        any(not b['steps'] for b in branches)):
                    error(key, 'parallel_join', 'Choose a join and add work to every parallel path.')
                if kind == 'parallel' and n.get('join') == 'any' and any(
                        nodes[x]['type'] in ('matrix', 'email', 'action')
                        for x in descendants(d, key)):
                    error(key, 'parallel_any_effects', 'Use “Everyone finishes” for paths with approvals or automatic effects.')
                for b in branches:
                    if b.get('condition'):
                        condition(b['condition'], available, key)
                    walk(b['steps'], available)
            if kind == 'subprocess':
                if not n['steps']:
                    error(key, 'empty_saved_group', 'Add a step to this saved group.')
                available = walk(n['steps'], available)
        return available
    walk(order, base | CONTEXT_FIELDS)
    matrix = [n for n in raw if n['type'] == 'matrix']
    if len(matrix) > 1:
        error('trigger', 'one_approval_step', 'Use one Approval Matrix step.')
    if matrix and matrix[0]['id'] in order:
        at = order.index(matrix[0]['id'])
        if any(nodes[x]['type'] == 'input' for top in order[at+1:] for x in descendants(d, top)):
            error(matrix[0]['id'], 'information_after_approval', 'Keep required information before approval.')
    scope = d.get('scope', {})
    if not isinstance(scope, dict) or scope.get('match') not in ('all', 'any') or not isinstance(scope.get('rules'), list):
        error('trigger', 'bad_scope', 'Choose how the workflow filters should match.')
    else:
        for rule in scope['rules']:
            condition(rule, base, 'trigger')
    trigger = d.get('trigger', {})
    if not isinstance(trigger, dict) or trigger.get('kind') not in ('manual', 'created', 'changed', 'date', 'approval_applied'):
        error('trigger', 'bad_trigger', 'Choose when this workflow starts.')
    elif trigger['kind'] == 'changed' and (not isinstance(trigger.get('fields'), list) or not trigger['fields'] or any(not isinstance(f, str) or f not in base for f in trigger['fields'])):
        error('trigger', 'trigger_fields', 'Choose the specific fields that start this workflow.')
    if trigger.get('before'):
        condition(trigger['before'], base, 'trigger')
        if trigger.get('kind') != 'changed':
            error('trigger', 'before_needs_change', 'Before-change filters need a field-change trigger.')
    return out


def route_preview(d, values):
    """An explicit simulation: no effects, database records or fake approvals."""
    nodes, rows = {n['id']: n for n in d['nodes']}, []
    def visit(ids, path='Main path'):
        for key in ids:
            n = nodes[key]
            stage_values = {**values, 'workflow.stage': n['stage']}
            if n.get('when') and not matches(n['when'], stage_values):
                rows.append({'id': key, 'title': n['title'], 'type': n['type'], 'path': path,
                             'reason': 'Skipped · filters do not match', 'skipped': True})
                continue
            rows.append({'id': key, 'title': n['title'], 'type': n['type'], 'path': path})
            if n['type'] == 'branch':
                selected = next(b for b in n['branches'] if not b.get('condition') or matches(b['condition'], stage_values))
                rows[-1]['reason'] = selected['label']
                visit(selected['steps'], selected['label'])
            elif n['type'] == 'parallel':
                for b in n['branches']:
                    if matches(b.get('condition'), stage_values):
                        visit(b['steps'], b['label'])
                    else:
                        rows.append({'id': key, 'title': b['label'], 'type': 'path', 'path': path,
                                     'reason': 'Skipped · path filters do not match', 'skipped': True})
            elif n['type'] == 'subprocess':
                visit(n['steps'], n['title'])
    visit(d['order'])
    return rows


def safe_json(value, limit=1000000):
    try:
        return len(json.dumps(value, allow_nan=False)) <= limit
    except (ValueError, TypeError, RecursionError):
        return False


def validate(d, source_fields=None, actions=None):
    # Invalid drafts are user input, not server errors. The deep JSON check
    # rejects non-finite numbers, cycles and oversized payloads before walking.
    if not safe_json(d):
        return [{'id': 'trigger', 'code': 'invalid_values', 'text': 'The workflow contains invalid or oversized values.', 'severity': 'error'}]
    try:
        return _validate(d, source_fields, actions)
    except (KeyError, TypeError, AttributeError, IndexError, ValueError, RecursionError):
        return [{'id': 'trigger', 'code': 'bad_format', 'text': 'A workflow setting has an invalid format. Check its fields and paths.', 'severity': 'error'}]


# A draft may be unfinished, but never structurally corrupt: these codes stop
# `save_draft`. Every other issue only blocks publishing and activation.
STRUCTURAL = frozenset({
    'too_large', 'invalid_values', 'bad_format', 'bad_schema', 'bad_shape',
    'bad_timing', 'bad_identifier', 'duplicate_step', 'bad_path_group',
    'branches_outside_group', 'steps_outside_saved_group', 'bad_saved_group',
    'shared_identifier', 'start_position', 'step_missing_reference',
    'group_section_mismatch', 'one_path_only', 'self_nesting', 'section_order',
    'field_identifier',
})
