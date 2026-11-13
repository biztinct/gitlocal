# -*- coding: utf-8 -*-
"""FILLIN P2 C3 — the studio edits a component's usual answer and its words.

`hr.formula.rule.default_value` is the usual answer a NEW contract starts with
(FILLIN ledger D1), and `value_labels` ("0=No;1=Yes") are the words a screen
shows for each number (D4). The component editor writes both through the
existing `save_component` allow-list, extended here — `pb_formula_studio.py`
itself is never edited (ledger rule 7).

The words are display only: the engine, the pay data file and every formula
keep the numbers.
"""
from odoo import _, api, models

from odoo.addons.pb_hr_payroll_formula.models.contract_fill_in import (
    parse_value_labels,
)


class StudioFillIn(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @property
    def _EDIT_FIELDS(self):
        # A class attribute on the parent; extended once, by name.
        return super()._EDIT_FIELDS + ('value_labels',)

    @api.model
    def _fillin_label_view(self, text, value_kind):
        """`{control, options}` for a draft's words, judged by the rule's OWN
        method on an unsaved record, so the studio and the contract panel can
        never disagree about what is a Yes / No."""
        Rule = self.env['hr.formula.rule']
        if not hasattr(Rule, 'value_label_control'):
            return {'control': '', 'options': []}
        draft = Rule.new({'value_labels': text or False,
                          'value_kind': value_kind or 'money'})
        control = draft.value_label_control() or ''
        options = draft.value_label_options() or []
        if control == 'toggle' and not options:
            options = [{'value': 1.0, 'label': _("Yes")},
                       {'value': 0.0, 'label': _("No")}]
        if control == 'toggle':
            options = sorted(options, key=lambda o: -o['value'])
        return {'control': control, 'options': options}

    @api.model
    def get_component_edit(self, rule_id):
        data = super().get_component_edit(rule_id)
        if not data.get('ok'):
            return data
        rule = self.env['hr.formula.rule'].browse(int(rule_id))
        labels = getattr(rule, 'value_labels', '') or ''
        data['value_labels'] = labels
        data['value_kind'] = rule.value_kind or 'money'
        data['value_label_view'] = self._fillin_label_view(
            labels, rule.value_kind)
        return data

    @api.model
    def studio_value_labels(self, text, value_kind=None):
        """The words as typed, read back: `{ok, control, options, msg}`.
        Called while the person types, so the usual-answer control follows
        the words before anything is saved. A read; it writes nothing."""
        text = (text or '').strip()
        if text and not parse_value_labels(text):
            return {'ok': False, 'control': '', 'options': [],
                    'msg': _("These words do not read yet. Write each value "
                             "as number=words, separated by semicolons, for "
                             "example 0=No;1=Yes.")}
        view = self._fillin_label_view(text, value_kind)
        return dict(view, ok=True, msg='')

    @api.model
    def save_component(self, rule_id, vals):
        vals = dict(vals or {})
        if 'value_labels' in vals:
            text = (vals.get('value_labels') or '').strip()
            if text and not parse_value_labels(text):
                return {'ok': False,
                        'msg': _("The words for each value do not read. "
                                 "Write them like 0=No;1=Yes.")}
            vals['value_labels'] = text or False
        return super().save_component(rule_id, vals)
