# -*- coding: utf-8 -*-
"""The Document studio's renderer: pure functions, no ORM.

1. "Show only when" paragraphs: every element carrying the CSS class
   `pbds-when` and a rule class `pbds-r-<id>` is kept (unwrapped) or removed
   according to its rule. Classes are used because the HTML sanitizer keeps
   them (ledger DS-1); `data-*` attributes would not survive.
2. Fields: `${key}` is replaced by the escaped value, exactly as the letter
   engine does (`string.Template` grammar: `$$` is a dollar sign, `$key`
   without braces is left alone when unknown).

Rules compare typed values through a fixed operator table. Nothing is ever
evaluated (rail R2). A rule that cannot be read KEEPS its paragraph: wording
is never dropped by accident.
"""
import datetime
import logging
import re
from string import Template

from lxml import etree, html as lxml_html
from markupsafe import escape

_logger = logging.getLogger(__name__)

#: `${name}` exactly as the letter engine accepts it.
BRACED_RE = re.compile(r'\$\{([_a-zA-Z][_a-zA-Z0-9]*)\}')
RULE_ID_RE = re.compile(r'^[a-z][a-z0-9]{0,15}$')
WHEN_CLASS = 'pbds-when'
RULE_PREFIX = 'pbds-r-'


class UnknownRule(Exception):
    """A rule, a field or an operator this renderer cannot read."""


# ------------------------------------------------------------------ fields
def field_keys(body):
    """Every `${key}` named in a body, in order of first appearance."""
    out = []
    for match in BRACED_RE.finditer(body or ''):
        if match.group(1) not in out:
            out.append(match.group(1))
    return out


def substitute(body, values, missing=None):
    """Fill the holes of `body`.

    `values` maps a key to its HTML-ready (already escaped) text. A braced key
    with no value, or with an empty one, gets `missing(key)` — the empty
    string in a real letter (rail R3: never print `${x}`), a chip in the
    preview. `$$` and a bare `$key` keep the letter engine's meaning.
    """
    pattern = Template.pattern

    def convert(mo):
        braced = mo.group('braced')
        named = mo.group('named')
        if braced is not None:
            val = values.get(braced)
            if val not in (None, ''):
                return str(val)
            return missing(braced) if missing else ''
        if named is not None:
            if named in values:
                return str(values[named])
            return mo.group()
        if mo.group('escaped') is not None:
            return '$'
        return mo.group()

    return pattern.sub(convert, body or '')


# ------------------------------------------------------------------ rules
def _norm_choice(value):
    if value in (None, False, ''):
        return None
    return str(value)


def _to_number(value):
    # `0 in (None, False)` is True in Python: test identity, 0 is a value.
    if value is None or value is False or value == '':
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise UnknownRule('not a number: %r' % (value,))


def _to_date(value):
    if value in (None, False, ''):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        raise UnknownRule('not a date: %r' % (value,))


def _to_text(value):
    if value in (None, False):
        return ''
    return str(value).strip().casefold()


def line_holds(line, facts, meta):
    """One condition. `meta[field]['type']` says how to compare."""
    if not isinstance(line, dict):
        raise UnknownRule('line is not a dict')
    key = line.get('field')
    op = line.get('op')
    spec = meta.get(key)
    if not spec:
        raise UnknownRule('unknown field %r' % (key,))
    kind = spec['type']
    from .doc_common import OPS
    if op not in OPS.get(kind, ()):
        raise UnknownRule('operator %r not allowed for %s' % (op, kind))
    actual = facts.get(key)
    want = line.get('value')

    if kind == 'bool':
        return bool(actual) == bool(want)

    if kind in ('choice', 'text'):
        norm = _norm_choice if kind == 'choice' else _to_text
        have = norm(actual)
        empty = have in (None, '')
        if op == 'empty':
            return empty
        if op == 'filled':
            return not empty
        if op == 'in':
            wanted = want if isinstance(want, (list, tuple)) else [want]
            return (not empty) and have in {norm(w) for w in wanted}
        target = norm(want)
        if op == 'is':
            return have == target
        if op == 'is_not':
            return have != target
        raise UnknownRule(op)

    conv = _to_number if kind == 'number' else _to_date
    have = conv(actual)
    if op == 'empty':
        return have is None
    if op == 'filled':
        return have is not None
    target = conv(want)
    if target is None:
        raise UnknownRule('no value to compare with')
    if have is None:
        # "is not 5" holds for a person with nothing recorded; the others do
        # not.
        return op == 'is_not'
    if op == 'is':
        return have == target
    if op == 'is_not':
        return have != target
    if op == 'gt':
        return have > target
    if op == 'lt':
        return have < target
    raise UnknownRule(op)


def rule_holds(rule, facts, meta):
    """A whole rule: all of its lines (`match: all`) or any of them."""
    if not isinstance(rule, dict):
        raise UnknownRule('rule is not a dict')
    lines = rule.get('lines') or []
    if not lines:
        raise UnknownRule('rule has no condition')
    results = [line_holds(line, facts, meta) for line in lines]
    if rule.get('match') == 'any':
        return any(results)
    return all(results)


def _rule_id(el):
    for cls in (el.get('class') or '').split():
        if cls.startswith(RULE_PREFIX):
            return cls[len(RULE_PREFIX):]
    return None


def _drop_keep_tail(el):
    """Remove `el` but keep the text that follows it."""
    parent = el.getparent()
    tail = el.tail
    if tail:
        prev = el.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or '') + tail
        else:
            parent.text = (parent.text or '') + tail
    parent.remove(el)


def apply_rules(body, rules, facts, meta, ghost=False, log_ref=''):
    """Keep or remove every "Show only when" block of `body`.

    Returns `(html, hidden, unreadable)`. With `ghost=True` (the preview) a
    hidden block stays in the page with the class `pbds-ghost` so the screen
    can show it faded; the real letter removes it.
    """
    if not body or WHEN_CLASS not in body:
        return body or '', 0, 0
    try:
        root = lxml_html.fragment_fromstring(body, create_parent='div')
    except (etree.ParserError, ValueError):
        _logger.warning('pb_doc_studio %s: body could not be read for rules; '
                        'kept as written', log_ref)
        return body, 0, 0
    hidden = unreadable = 0
    xpath = ".//*[contains(concat(' ', normalize-space(@class), ' '), ' %s ')]" % WHEN_CLASS
    while True:
        found = root.xpath(xpath)
        if not found:
            break
        el = found[0]
        rid = _rule_id(el)
        try:
            if not rid or rid not in (rules or {}):
                raise UnknownRule('no rule %r' % (rid,))
            keep = rule_holds(rules[rid], facts, meta)
        except UnknownRule as exc:
            _logger.warning('pb_doc_studio %s: rule %s kept its paragraph (%s)',
                            log_ref, rid, exc)
            unreadable += 1
            keep = True
        if keep:
            el.drop_tag()
        elif ghost:
            el.set('class', 'pbds-ghost')
            hidden += 1
        else:
            _drop_keep_tail(el)
            hidden += 1
    out = (root.text or '') if root.text else ''
    out = str(escape(out)) if out else ''
    for child in root:
        out += lxml_html.tostring(child, encoding='unicode')
    return out, hidden, unreadable
