# -*- coding: utf-8 -*-
"""CARD BUILDERS — the only thing the chat client interprets.

Contract (P1_HANDOVER §Card JSON contract):

    {kind: 'plan'|'done'|'blocked'|'refused'|'clarify',
     task_id, tier, title, subtitle,
     slots: [{key, label, value_label, origin, editable}],
     notes: [{tone, text}],
     actions: [{id, label, style, door_id?, hub?, url?, auto?, text?}],
     chips: [{label, sublabel, value}],
     result: [{value, label}],
     groups: [{tone, label, items: [{label, example}]}],   # "What can you do?"
     audit_line}

The client never decides a tier or a right: it draws what it is given and
calls back by `task_id`. Every string here is already plain English.
"""
from odoo.tools.translate import LazyTranslate

from .i18n import T

_lt = LazyTranslate(__name__)


def card(kind, task=None, tier='look', title='', subtitle='', **kw):
    out = {
        'kind': kind,
        'task_id': task.id if task else 0,
        'tier': tier,
        'title': T(title or ''),
        'subtitle': T(subtitle or ''),
        'slots': kw.pop('slots', []),
        'notes': kw.pop('notes', []),
        'actions': kw.pop('actions', []),
        'chips': kw.pop('chips', []),
        'result': kw.pop('result', []),
        'groups': kw.pop('groups', []),
        'audit_line': T(kw.pop('audit_line', '') or ''),
    }
    out.update(kw)
    return out


def note(tone, text):
    return {'tone': tone, 'text': T(text)}


def door_action(door_id, label, style='outline', hub=None, auto=False):
    act = {'id': 'door', 'door_id': door_id, 'label': T(label), 'style': style}
    if hub:
        act['hub'] = hub
    if auto:
        act['auto'] = True
    return act


def ask_action(text, label=None, style='outline'):
    """A button that asks PayAI the given sentence (a follow-up)."""
    return {'id': 'ask', 'text': T(text), 'label': T(label or text),
            'style': style}


def what_can_you_do_chip():
    return {'label': T(_lt("What can you do?")), 'sublabel': '',
            'value': '', 'ask': T(_lt("What can you do?"))}
