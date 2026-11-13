# -*- coding: utf-8 -*-
"""Reading a workflow task's answers from a plain HTML form post (WF2 P4a).

Pure parsing: every value is then checked by the SAME validators the app
uses (`workflow_definition.validate_answers` / `validate_outcome`). Nothing
here decides whether an answer is acceptable.
"""
import re

_NUMBER = re.compile(r'^-?\d+(\.\d+)?$')
_MAX_TEXT = 10000


def _number(raw):
    raw = (raw or '').strip().replace(',', '')
    if not raw:
        return None
    if _NUMBER.match(raw):
        return int(raw) if '.' not in raw else float(raw)
    return raw          # the validator says "Enter a number."


def parse_answers(fields, form, keep_files=None):
    """{field id: value} from a werkzeug form (MultiDict), for one form.

    `keep_files` (employee home only) maps a file field to the attachment ids
    already uploaded for it; lookups are never read from a page."""
    values = {}
    for f in fields or []:
        fid, kind = f.get('id'), f.get('type')
        name = 'f_%s' % fid
        if kind in ('section', 'lookup') or f.get('unsupported') and kind != 'file':
            continue
        if kind in ('text', 'textarea', 'email', 'date', 'select'):
            raw = (form.get(name) or '').strip()[:_MAX_TEXT]
            if raw:
                values[fid] = raw
        elif kind == 'number':
            value = _number(form.get(name))
            if value is not None:
                values[fid] = value
        elif kind == 'boolean':
            raw = form.get(name)
            if raw in ('yes', 'no'):
                values[fid] = raw == 'yes'
        elif kind == 'multiselect':
            picked = [v for v in form.getlist(name) if v]
            if picked:
                values[fid] = picked[:100]
        elif kind == 'rows':
            texts = form.getlist('rows_%s_description' % fid)
            amounts = form.getlist('rows_%s_amount' % fid)
            rows = []
            for i, text in enumerate(texts[:100]):
                text = (text or '').strip()[:1000]
                amount = _number(amounts[i] if i < len(amounts) else '')
                if not text and amount is None:
                    continue
                rows.append({'description': text, 'amount': amount})
            if rows:
                values[fid] = rows
        elif kind == 'file' and keep_files is not None:
            ids = list((keep_files or {}).get(fid) or [])
            if ids:
                values[fid] = ids[:10]
    return values


def parse_outcome(form):
    out = {}
    if form.get('outcome'):
        out['outcome'] = str(form.get('outcome'))[:80]
    comment = (form.get('comment') or '').strip()
    if comment:
        out['comment'] = comment[:2000]
    return out
