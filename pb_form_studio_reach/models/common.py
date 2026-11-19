# -*- coding: utf-8 -*-
"""Shared names for the FS-5 bridge.

The record types the reach covers are the two the programme puts custom
fields on (FS-2 employee, FS-3 contract). Everything below asks the engine
(`pb.form.studio.fields_for` / `_pbfs_values_for` / `_pbfs_meta`) which
custom fields exist and who may see them; nothing here reads a custom
field's value with a plain `read` / `search_read` loop (FS hosts ADDENDUM 1).
"""
from odoo.addons.pb_form_studio.models.ir_model_fields import PREFIX  # noqa: F401

EMP = 'hr.employee'
CON = 'hr.contract'
#: model -> the word in a payroll-source key.
REACH_MODELS = {EMP: 'employee', CON: 'contract'}
#: Payroll-source keys of Form-builder fields: `custom.employee.x_pbfs_…` /
#: `custom.contract.x_pbfs_…`. An OWN prefix on purpose: the engine's value
#: path refuses `employee.` / `contract.` names outside its curated tuples
#: (FS_HOST_FACTS §D).
SOURCE_PREFIX = 'custom.'


def source_key(model, name):
    word = REACH_MODELS.get(model)
    return '%s%s.%s' % (SOURCE_PREFIX, word, name) if word and name else ''


def parse_source_key(key):
    """`(model, field name)` of a Form-builder payroll-source key, else
    `(None, None)`."""
    key = (key or '').strip()
    if not key.startswith(SOURCE_PREFIX):
        return None, None
    word, _sep, name = key[len(SOURCE_PREFIX):].partition('.')
    for model, w in REACH_MODELS.items():
        if w == word and name.startswith(PREFIX):
            return model, name
    return None, None
