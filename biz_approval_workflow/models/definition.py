# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The workflow definition document: schema, canonical form, validator.

A workflow revision is ONE versioned JSON document (ledger AM1), not a tree of
child rows: the builder edits a route atomically, two revisions are compared
whole-document, and the published snapshot is the runtime truth.

Everything in this file is pure Python except the optional ``env`` hook, which
lets the caller add the two checks that need the database (is this role key
known, is this user still active). With ``env=None`` the validator is a pure
function of its inputs and is safe to call from a preview that must not touch
the registry.

Warning codes are the AM4 list: fast_lane, single_person, independence_off,
coverage_not_run, coverage_gap:<scope>, no_backup:<step>, notify_only_route,
money_single_person. Errors block a publish; warnings are confirmed by the
publisher and stored on the version.
"""

import hashlib
import json

SCHEMA_VERSION = 1

# A step is one of these. `notify` is never counted as an approval; `fast` means
# "no approval needed" and must stand alone.
STEP_KINDS = ('review', 'approve', 'joint', 'any', 'notify', 'fast')
DECISION_KINDS = ('review', 'approve', 'joint', 'any', 'fast')

# How a step finds its people.
WHO_MODES = ('role', 'manager', 'skip', 'people', 'team', 'preparer')

# Typed condition operators. There is deliberately no expression language here:
# a configuration screen must never be able to hand the server something to
# evaluate (ledger — safe_eval has no nocopy on this build).
OPERATORS = ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in')
NUMERIC_OPS = ('gt', 'gte', 'lt', 'lte')
SET_OPS = ('in', 'not_in')

FACT_TYPES = ('bool', 'decimal', 'int', 'percent', 'selection', 'char')
NUMERIC_TYPES = ('decimal', 'int', 'percent')

DUE_KINDS = ('none', 'working_days', 'calendar_day', 'per_request')
REPEATED_MODES = ('different', 'reason')


def default_safeguards():
    return {
        'independent': True,
        'self_exception': {'enabled': False},
        'repeated': 'different',
        'evidence': [],
        'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
        'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
    }


def empty_definition():
    return {
        'schema_version': SCHEMA_VERSION,
        'steps': [],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': default_safeguards(),
    }


# --------------------------------------------------------------- normalising
def normalise(definition):
    """Fill in every optional key so the rest of the engine can index freely."""
    d = json.loads(json.dumps(definition or {}))  # deep copy, JSON-only types
    d.setdefault('schema_version', SCHEMA_VERSION)
    d.setdefault('steps', [])
    tiers = d.setdefault('tiers', {})
    tiers.setdefault('enabled', False)
    tiers.setdefault('fact', None)
    sg = d.setdefault('safeguards', {})
    base = default_safeguards()
    for key, value in base.items():
        sg.setdefault(key, value)
    for key, value in base['due'].items():
        sg['due'].setdefault(key, value)
    for key, value in base['late'].items():
        sg['late'].setdefault(key, value)
    sg['self_exception'].setdefault('enabled', False)
    steps = []
    for index, raw in enumerate(d['steps'] or []):
        step = dict(raw or {})
        step.setdefault('key', 's%d' % (index + 1))
        step.setdefault('kind', 'approve')
        step.setdefault('title', '')
        step.setdefault('who', {})
        step['who'] = dict(step['who'] or {})
        step['who'].setdefault('mode', 'role')
        step.setdefault('min_amount', 0)
        step.setdefault('condition', None)
        steps.append(step)
    d['steps'] = steps
    return d


def decision_steps(definition):
    return [s for s in normalise(definition)['steps'] if s['kind'] != 'notify']


def canonical(definition):
    """Stable text form — the thing a fingerprint is taken of."""
    return json.dumps(normalise(definition), sort_keys=True,
                      separators=(',', ':'), ensure_ascii=False)


def fingerprint(definition):
    return hashlib.sha256(canonical(definition).encode('utf-8')).hexdigest()


# ----------------------------------------------------------------- labelling
def who_label(who, role_names=None, user_names=None):
    """Plain words for one step's "who decides" — no model names, no keys."""
    role_names = role_names or {}
    user_names = user_names or {}
    mode = (who or {}).get('mode')
    if mode == 'role':
        name = role_names.get(who.get('role'), who.get('role') or '')
        scope = who.get('scope') or 'company'
        return '%s%s' % (name, ' for this area' if scope != 'company'
                         else ' · whole company')
    if mode == 'manager':
        return 'Their manager'
    if mode == 'skip':
        return "Their manager's manager"
    if mode == 'people':
        names = [user_names.get(uid, '#%s' % uid)
                 for uid in (who.get('user_ids') or [])]
        joined = ' + '.join(names)
        if len(names) > 1:
            joined += ' · everyone' if who.get('all') else ' · any one'
        return joined
    if mode == 'team':
        return 'Any one of %s' % (who.get('label') or 'the team')
    if mode == 'preparer':
        return 'The person who sent it in'
    return ''


def route_labels(definition, role_names=None, user_names=None, money_fmt=None):
    """Port of the POC's P.routeLabels — the short chips a list row shows."""
    d = normalise(definition)
    out = []
    for step in decision_steps(d):
        if step['kind'] == 'fast':
            out.append('No approval needed')
            continue
        label = who_label(step['who'], role_names, user_names)
        if d['tiers'].get('enabled') and step.get('min_amount'):
            amount = step['min_amount']
            label += ' (%s+)' % (money_fmt(amount) if money_fmt else amount)
        out.append(label)
    return out


def sentence(definition, role_names=None, user_names=None, money_fmt=None,
             fact_labels=None, opening='After it is sent in'):
    """Port of the POC's P.sentence — one readable line describing the route."""
    d = normalise(definition)
    steps = decision_steps(d)
    if not steps:
        return 'Nothing is checked yet. Add a step.'
    fact_labels = fact_labels or {}
    parts = []
    for index, step in enumerate(steps):
        last = index == len(steps) - 1
        if step['kind'] == 'fast':
            parts.append('it is applied immediately and logged')
            continue
        who = step['who']
        if who.get('mode') == 'people' and who.get('all') \
                and len(who.get('user_ids') or []) > 1:
            verb = 'must all approve'
        elif step['kind'] == 'review':
            verb = 'reviews it'
        else:
            verb = 'gives final approval' if last else 'approves'
        tail = ''
        if d['tiers'].get('enabled') and step.get('min_amount'):
            amount = step['min_amount']
            tail += ' when the amount is %s or more' % (
                money_fmt(amount) if money_fmt else amount)
        cond = step.get('condition')
        if cond:
            tail += ', only when %s' % condition_phrase(cond, fact_labels)
        parts.append('%s %s%s' % (
            who_label(who, role_names, user_names), verb, tail))
    line = '%s, %s.' % (opening, parts[0])
    for part in parts[1:]:
        line += ' Then %s.' % part
    if any(s['kind'] == 'notify' for s in d['steps']):
        line += ' Other people are told along the way.'
    return line


_OP_PHRASE = {
    'eq': 'is', 'ne': 'is not', 'gt': 'is more than', 'gte': 'is at least',
    'lt': 'is less than', 'lte': 'is at most', 'in': 'is one of',
    'not_in': 'is not one of',
}


def condition_phrase(condition, fact_labels=None):
    fact_labels = fact_labels or {}
    fact = condition.get('fact')
    label = fact_labels.get(fact, fact)
    value = condition.get('value')
    if isinstance(value, bool):
        return '%s %s' % (label, 'is yes' if value else 'is no')
    if isinstance(value, (list, tuple)):
        value = ', '.join(str(v) for v in value)
    return '%s %s %s' % (label, _OP_PHRASE.get(condition.get('op'), 'is'),
                         value)


# ---------------------------------------------------------------- validation
def _err(errors, code, message, step=None):
    errors.append({'code': code, 'message': message, 'step': step})


def _warn(warnings, code, message, step=None):
    warnings.append({'code': code, 'message': message, 'step': step})


def validate(definition, capabilities=None, env=None, role_info=None):
    """Structural validation of one definition document.

    ``capabilities`` is the adapter's ``_approval_capabilities()`` dict
    (facts/kinds/evidence). ``role_info`` maps a role key to
    ``{'name':…, 'pool': bool}``; when omitted and ``env`` is given it is read
    from the role catalogue. Returns ``{'errors': [...], 'warnings': [...]}``
    with stable codes on every entry.
    """
    errors, warnings = [], []
    capabilities = capabilities or {}
    facts = capabilities.get('facts') or {}

    if role_info is None:
        role_info = {}
        if env is not None:
            for role in env['biz.approval.role'].sudo().search([]):
                role_info[role.key] = {'name': role.name, 'pool': role.is_pool}

    raw = definition or {}
    if not isinstance(raw, dict):
        _err(errors, 'bad_schema', 'This workflow could not be read. '
                                   'Start a new draft.')
        return {'errors': errors, 'warnings': warnings}
    if int(raw.get('schema_version') or SCHEMA_VERSION) != SCHEMA_VERSION:
        _err(errors, 'bad_schema_version',
             'This workflow was written by a newer version of the app and '
             'cannot be opened here.')
        return {'errors': errors, 'warnings': warnings}

    d = normalise(raw)
    steps = d['steps']
    seen_keys = set()
    deciders = set()

    for step in steps:
        key = step.get('key')
        title = step.get('title') or key
        if not key or not isinstance(key, str):
            _err(errors, 'bad_step_key', 'A step is missing its name.', key)
            continue
        if key in seen_keys:
            _err(errors, 'duplicate_step', 'Two steps share the same name: '
                                           '%s.' % title, key)
        seen_keys.add(key)
        kind = step.get('kind')
        if kind not in STEP_KINDS:
            _err(errors, 'bad_kind', 'Step "%s" has a kind this app does not '
                                     'know.' % title, key)
            continue
        who = step.get('who') or {}
        mode = who.get('mode')
        if kind == 'fast':
            continue
        if mode not in WHO_MODES:
            _err(errors, 'bad_who', 'Step "%s" does not say who decides '
                                    'it.' % title, key)
            continue
        if mode == 'preparer' and kind != 'notify':
            _err(errors, 'preparer_decides',
                 'Step "%s" sends the decision back to the person who asked '
                 'for it. Only a "tell someone" step may do that.' % title,
                 key)
        if mode == 'role':
            role_key = who.get('role')
            if not role_key or (role_info and role_key not in role_info):
                _err(errors, 'unknown_role',
                     'Step "%s" uses a responsibility that no longer '
                     'exists.' % title, key)
            deciders.add('role:%s:%s' % (role_key, who.get('scope') or 'company'))
        elif mode == 'people':
            user_ids = [u for u in (who.get('user_ids') or []) if u]
            if not user_ids:
                _err(errors, 'no_people', 'Step "%s" names nobody.' % title,
                     key)
            elif env is not None:
                live = env['res.users'].sudo().browse(user_ids).exists()
                if len(live.filtered('active')) != len(set(user_ids)):
                    _err(errors, 'inactive_person',
                         'Step "%s" names someone whose account is no longer '
                         'in use.' % title, key)
            for uid in user_ids:
                deciders.add('user:%s' % uid)
        elif mode == 'team':
            members = [u for u in (who.get('user_ids') or []) if u]
            if len(members) < 1:
                _err(errors, 'empty_team',
                     'Step "%s" points at a team with nobody in it.' % title,
                     key)
            for uid in members:
                deciders.add('user:%s' % uid)
        elif mode in ('manager', 'skip'):
            if not capabilities.get('manager_mode', True):
                _err(errors, 'no_manager_mode',
                     'Step "%s" uses "their manager", which this kind of '
                     'request cannot work out.' % title, key)
            deciders.add('manager:%s' % mode)

        if kind == 'joint':
            ok = (mode == 'people' and len(who.get('user_ids') or []) >= 2
                  and who.get('all'))
            ok = ok or (mode == 'role'
                        and role_info.get(who.get('role'), {}).get('pool'))
            if not ok:
                _err(errors, 'joint_needs_two',
                     'Step "%s" says everyone must approve, but it has fewer '
                     'than two people.' % title, key)
        if kind == 'any':
            ok = mode == 'team' or (
                mode == 'role'
                and role_info.get(who.get('role'), {}).get('pool'))
            ok = ok or (mode == 'people'
                        and len(who.get('user_ids') or []) >= 2
                        and not who.get('all'))
            if not ok:
                _err(errors, 'any_needs_pool',
                     'Step "%s" says any one person may decide, but it does '
                     'not offer a choice of people.' % title, key)

        condition = step.get('condition')
        if condition:
            _validate_condition(condition, facts, title, key, errors)
        min_amount = step.get('min_amount') or 0
        if min_amount:
            tier_fact = d['tiers'].get('fact')
            if not d['tiers'].get('enabled') or not tier_fact:
                _err(errors, 'tier_without_fact',
                     'Step "%s" only applies above an amount, but this '
                     'workflow does not route by amount.' % title, key)
            elif facts and facts.get(tier_fact, {}).get('type') \
                    not in NUMERIC_TYPES:
                _err(errors, 'tier_fact_not_number',
                     'This workflow routes by something that is not a '
                     'number.', key)

    # fast lane must stand alone
    dsteps = [s for s in steps if s['kind'] != 'notify']
    fast = [s for s in dsteps if s['kind'] == 'fast']
    if fast and len(dsteps) > 1:
        _err(errors, 'fast_not_alone',
             '"No approval needed" cannot sit beside other steps. Remove the '
             'other steps, or remove this one.', fast[0]['key'])

    # ------------------------------------------------------------- warnings
    sg = d['safeguards']
    if sg.get('repeated') not in REPEATED_MODES:
        _err(errors, 'bad_repeated', 'The rule for the same person at two '
                                     'steps could not be read.')
    if (sg.get('due') or {}).get('kind') not in DUE_KINDS:
        _err(errors, 'bad_due', 'The target time for each step could not be '
                               'read.')

    if fast:
        _warn(warnings, 'fast_lane',
              'Nobody checks this before it happens. Every one is still '
              'recorded.')
    elif not dsteps:
        if any(s['kind'] == 'notify' for s in steps):
            _warn(warnings, 'notify_only_route',
                  'This workflow only tells people; nobody approves. Requests '
                  'will be applied immediately and recorded.')
        _warn(warnings, 'fast_lane',
              'There are no steps, so requests will be applied immediately '
              'and recorded.')
    elif len(deciders) < 2:
        _warn(warnings, 'single_person',
              'Only one person signs this off. Two people are safer when '
              'money or pay is involved.')

    if not sg.get('independent'):
        _warn(warnings, 'independence_off',
              'The independence rule is off: the same person may prepare and '
              'approve.')

    return {'errors': errors, 'warnings': warnings}


def _validate_condition(condition, facts, title, key, errors):
    if not isinstance(condition, dict):
        _err(errors, 'bad_condition',
             'The "only when" rule on step "%s" could not be read.' % title,
             key)
        return
    fact = condition.get('fact')
    op = condition.get('op')
    value = condition.get('value')
    if facts and fact not in facts:
        _err(errors, 'unknown_fact',
             'Step "%s" asks about something this kind of request does not '
             'have.' % title, key)
        return
    if op not in OPERATORS:
        _err(errors, 'bad_operator',
             'Step "%s" compares in a way this app does not support.' % title,
             key)
        return
    ftype = (facts.get(fact) or {}).get('type') if facts else None
    if ftype and op in NUMERIC_OPS and ftype not in NUMERIC_TYPES:
        _err(errors, 'operator_type_mismatch',
             'Step "%s" compares sizes of something that is not a '
             'number.' % title, key)
    if op in SET_OPS and not isinstance(value, (list, tuple)):
        _err(errors, 'value_not_list',
             'Step "%s" needs a list of values to compare against.' % title,
             key)
    if ftype == 'bool' and not isinstance(value, bool) and op in ('eq', 'ne'):
        _err(errors, 'value_not_bool',
             'Step "%s" must compare a yes/no answer with yes or no.' % title,
             key)


# ----------------------------------------------------------------- evaluation
def condition_holds(condition, facts):
    """Evaluate one typed condition against frozen facts.

    ``facts`` maps a key to ``{'value': …, 'unit': …}`` (the adapter's shape) or
    directly to a value. A fact that is missing makes the condition false — an
    absent answer is never a silent yes.
    """
    if not condition:
        return True
    raw = (facts or {}).get(condition.get('fact'))
    if raw is None:
        return False
    value = raw.get('value') if isinstance(raw, dict) else raw
    other = condition.get('value')
    op = condition.get('op')
    try:
        if op == 'eq':
            return value == other
        if op == 'ne':
            return value != other
        if op == 'gt':
            return float(value) > float(other)
        if op == 'gte':
            return float(value) >= float(other)
        if op == 'lt':
            return float(value) < float(other)
        if op == 'lte':
            return float(value) <= float(other)
        if op == 'in':
            return value in (other or [])
        if op == 'not_in':
            return value not in (other or [])
    except (TypeError, ValueError):
        return False
    return False


def fact_value(facts, key):
    raw = (facts or {}).get(key)
    if raw is None:
        return None
    return raw.get('value') if isinstance(raw, dict) else raw
