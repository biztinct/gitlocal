# -*- coding: utf-8 -*-
"""Shared helpers: the verdict table and "which boxes does this person see"."""

import ast
import csv
import os

from lxml import etree

from odoo.tests import new_test_user
from odoo.tools.safe_eval import safe_eval

from ..models.hr_employee import NO_TIDY

HERE = os.path.dirname(__file__)
COUNTRIES = ('VN', 'ID', 'IN', 'SG')


def verdict_table():
    """`{field_code: (verdict, country)}` — the committed, name-free copy of
    the FIELD AUDIT spreadsheet's per-box verdicts (final: the 5 unsure boxes
    and the old Account Number box are REMOVE FROM SCREEN)."""
    out = {}
    with open(os.path.join(HERE, 'data', 'form_box_verdicts.csv'), newline='') as fh:
        for row in csv.DictReader(fh):
            out[row['field_code']] = (row['verdict'], row['country'])
    return out


def make_hr_users(env, suffix):
    company = env.company
    manager = new_test_user(
        env, login='tidy_e_mgr_%s' % suffix, name='DEMO Tidy manager %s' % suffix,
        groups='base.group_user,hr.group_hr_user,hr.group_hr_manager,'
               'pb_hr_payroll_base.group_payroll_base_user',
        company_id=company.id, company_ids=[company.id])
    officer = new_test_user(
        env, login='tidy_e_off_%s' % suffix, name='DEMO Tidy officer %s' % suffix,
        groups='base.group_user,hr.group_hr_user,'
               'pb_hr_payroll_base.group_payroll_base_user',
        company_id=company.id, company_ids=[company.id])
    return manager, officer


def form_arch(env, tidy=True):
    ctx = dict(env.context)
    if tidy:
        ctx.pop(NO_TIDY, None)
    else:
        ctx[NO_TIDY] = True
    res = env['hr.employee'].with_context(ctx).get_views([(False, 'form')])
    return etree.fromstring(res['views']['form']['arch'])


def _names(expr):
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError:
        return set()
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _value(record, name):
    if name == 'id':
        return record.id
    field = record._fields.get(name)
    if field is None:
        return None
    try:
        value = record[name]
    except Exception:       # noqa: BLE001 — a field this viewer may not read
        return None
    if field.type == 'many2one':
        return value.id or False
    if field.type in ('one2many', 'many2many'):
        return value.ids
    return value


def _hidden(node, record, cache):
    """Is this node hidden for this record (its own or an ancestor's
    `invisible`)? Nodes inside a field's sub-view are not asked."""
    while node is not None:
        expr = (node.get('invisible') or '').strip()
        if expr and expr not in ('0', 'False', 'false'):
            if expr in ('1', 'True', 'true'):
                return True
            if expr not in cache:
                ctx = {'context': {}, 'uid': record.env.uid, 'True': True,
                       'False': False, 'None': None}
                for name in _names(expr):
                    if name not in ctx:
                        ctx[name] = _value(record, name)
                cache[expr] = bool(safe_eval(expr, ctx))
            if cache[expr]:
                return True
        node = node.getparent()
    return False


def visible_boxes(arch, record, names):
    """The subset of ``names`` this record shows on the form ``arch``.

    A box shows when at least one of its nodes (outside x2many sub-views) is
    not hidden.
    """
    cache = {}
    shown = set()
    for node in arch.iter('field'):
        name = node.get('name')
        if name not in names or name in shown:
            continue
        # skip fields that belong to a sub-view (an x2many list inside a field)
        parent, inside_sub = node.getparent(), False
        while parent is not None:
            if parent.tag == 'field':
                inside_sub = True
                break
            parent = parent.getparent()
        if inside_sub:
            continue
        if not _hidden(node, record, cache):
            shown.add(name)
    return shown


def present_boxes(arch, names):
    return {n.get('name') for n in arch.iter('field') if n.get('name') in names}
