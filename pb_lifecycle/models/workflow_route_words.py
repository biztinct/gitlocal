"""WF2 P6a (closeout item 12): Approvals' route words in Studio, translated and
in plain words.

Studio's "Already happens" shows the approval route of a record type as chips
("Their manager, then Any one of HR") and one sentence (`detail`). Both came
from Approvals' own label helpers (`biz_approval_workflow/models/definition.py`
`route_labels` / `sentence`), which are English only and print a condition with
its technical fact and raw values ("…, only when validation_type is one of
manager, both").

Here Studio asks the engine for those words with a context flag
(`_pb_wf_route_model`) and the engine (extended by inheritance from this
module, ledger G76 — `biz_approval_workflow` is shared and not edited) answers
with a port of the same two helpers whose fixed words go through `_()`, and
whose condition names the fact by the area's own label and each value by the
area's own words (`_approval_capabilities()`: facts, kinds). English output is
byte-identical to Approvals' helpers for every route without a condition (test
p6a_r1); a condition now reads "…, only when What this kind of time off asks
for is one of Approved by the manager, Approved by both" — the one plain-words
fix of the phase (R1 audit). Nothing else in Approvals changes: the Matrix
screens and the stored route summary are untouched.

No local is called `user` or `uid` in a function that calls `_()` (G12).
"""
from odoo import api, models

from odoo.addons.biz_approval_workflow.models import definition as AD


def _who_words(env, who, role_names, user_names):
    """`AD.who_label`, translated."""
    _ = env._
    role_names = role_names or {}
    user_names = user_names or {}
    mode = (who or {}).get('mode')
    if mode == 'role':
        name = role_names.get(who.get('role'), who.get('role') or '')
        scope = who.get('scope') or 'company'
        return _('%s for this area', name) if scope != 'company' else _('%s · whole company', name)
    if mode == 'manager':
        return _('Their manager')
    if mode == 'skip':
        return _("Their manager's manager")
    if mode == 'people':
        names = [user_names.get(pid, '#%s' % pid) for pid in (who.get('user_ids') or [])]
        joined = ' + '.join(names)
        if len(names) > 1:
            joined = _('%s · everyone', joined) if who.get('all') else _('%s · any one', joined)
        return joined
    if mode == 'team':
        return _('Any one of %s', who.get('label') or _('the team'))
    if mode == 'preparer':
        return _('The person who sent it in')
    return ''


def route_words(env, definition, role_names=None, user_names=None):
    """`AD.route_labels`, translated (no money format: Studio passes none)."""
    _ = env._
    d = AD.normalise(definition)
    out = []
    for step in AD.decision_steps(d):
        if step['kind'] == 'fast':
            out.append(_('No approval needed'))
            continue
        label = _who_words(env, step['who'], role_names, user_names)
        if d['tiers'].get('enabled') and step.get('min_amount'):
            label = _('%(who)s (%(amount)s+)', who=label, amount=step['min_amount'])
        out.append(label)
    return out


def _value_words(value, words):
    if isinstance(value, (list, tuple)):
        return ', '.join(str(words.get(str(v), v)) for v in value)
    return str(words.get(str(value), value))


def condition_words(env, condition, facts, values):
    """`AD.condition_phrase` in plain words: the area's label for the fact,
    the area's words for each value, translated operators."""
    _ = env._
    fact = condition.get('fact')
    label = facts.get(fact) or fact
    value = condition.get('value')
    if isinstance(value, bool):
        return _('%s is yes', label) if value else _('%s is no', label)
    ops = {'eq': _('%(fact)s is %(value)s'), 'ne': _('%(fact)s is not %(value)s'),
           'gt': _('%(fact)s is more than %(value)s'), 'gte': _('%(fact)s is at least %(value)s'),
           'lt': _('%(fact)s is less than %(value)s'), 'lte': _('%(fact)s is at most %(value)s'),
           'in': _('%(fact)s is one of %(value)s'), 'not_in': _('%(fact)s is not one of %(value)s')}
    return ops.get(condition.get('op'), ops['eq']) % {'fact': label, 'value': _value_words(value, values)}


def sentence_words(env, definition, role_names=None, user_names=None, facts=None, values=None):
    """`AD.sentence`, translated, with plain-words conditions."""
    _ = env._
    d = AD.normalise(definition)
    steps = AD.decision_steps(d)
    if not steps:
        return _('Nothing is checked yet. Add a step.')
    parts = []
    for index, step in enumerate(steps):
        last = index == len(steps) - 1
        if step['kind'] == 'fast':
            parts.append(_('it is applied immediately and logged'))
            continue
        who = step['who']
        name = _who_words(env, who, role_names, user_names)
        if who.get('mode') == 'people' and who.get('all') and len(who.get('user_ids') or []) > 1:
            part = _('%s must all approve', name)
        elif step['kind'] == 'review':
            part = _('%s reviews it', name)
        else:
            part = _('%s gives final approval', name) if last else _('%s approves', name)
        if d['tiers'].get('enabled') and step.get('min_amount'):
            part = _('%(step)s when the amount is %(amount)s or more', step=part, amount=step['min_amount'])
        cond = step.get('condition')
        if cond:
            part = _('%(step)s, only when %(rule)s', step=part,
                     rule=condition_words(env, cond, facts or {}, values or {}))
        parts.append(part)
    line = _('After it is sent in, %s.', parts[0])
    for part in parts[1:]:
        line += _(' Then %s.', part)
    if any(s['kind'] == 'notify' for s in d['steps']):
        line += _(' Other people are told along the way.')
    return line


class ApprovalEngineRouteWords(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    def _pb_wf_route_vocabulary(self, model):
        """({fact: label}, {value key: words}) the area gives for its route
        conditions (`_approval_capabilities`), empty when it gives none."""
        facts, values = {}, {}
        if not model or model not in self.env:
            return facts, values
        records = self.env[model]
        caps = records._approval_capabilities() if hasattr(records, '_approval_capabilities') else {}
        for key, spec in ((caps or {}).get('facts') or {}).items():
            if isinstance(spec, dict) and spec.get('label'):
                facts[key] = str(spec['label'])
        for kind in (caps or {}).get('kinds') or []:
            if isinstance(kind, dict) and kind.get('key') and kind.get('label'):
                values[str(kind['key'])] = str(kind['label'])
        return facts, values

    @api.model
    def route_labels(self, definition):
        model = self.env.context.get('_pb_wf_route_model')
        if not model:
            return super().route_labels(definition)
        self._require_config()
        roles, names = self._naming(definition)
        return route_words(self.env, definition, roles, names)

    @api.model
    def summary(self, definition):
        model = self.env.context.get('_pb_wf_route_model')
        if not model:
            return super().summary(definition)
        self._require_config()
        roles, names = self._naming(definition)
        facts, values = self._pb_wf_route_vocabulary(model)
        return sentence_words(self.env, definition, roles, names, facts, values)


class WorkflowRouteWords(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    def _approval_effects(self, model, company, contract):
        # The route's chips and sentence in the reader's language and in
        # plain words (see the module docstring).
        return super(WorkflowRouteWords, self.with_context(_pb_wf_route_model=model)) \
            ._approval_effects(model, company, contract)
