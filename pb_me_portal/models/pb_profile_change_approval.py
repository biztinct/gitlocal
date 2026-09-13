# -*- coding: utf-8 -*-
"""A person's own details change through a route the business chose.

WHAT WAS TRUE BEFORE. One rung in code: an HR payroll user said yes and the
employee record was written.

WHAT IS TRUE NOW. The same rung ships as the default — **the HR lead** — and
every request carries WHAT KIND of change it is, so a business that wants a
new phone number applied at once and an emergency contact checked can say so
with a condition instead of a developer.

WHY THE DEFAULT STILL CHECKS EVERYTHING. The handover asked for a fast lane
for phone and address. Every field this screen can propose IS a contact
detail on this build (`_MASTER_FIELDS`), so a condition of "only check the
ones that are not contact details" would waive all of them — which is not
today's ladder, and the ruling is that day one behaves like day zero. The
fact is there, the condition is one press away in the builder, and the
business makes that choice rather than inheriting it.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

MASTER_PROCESS_KEY = 'master'

#: The fields that are somebody's own contact details and nobody else's
#: business — the family a fast lane would usually be about.
CONTACT_FIELDS = ('x_phone', 'x_private_email', 'x_address',
                  'x_emergency_contact', 'x_emergency_phone')

register_chain(
    'pb.profile.change.request', MASTER_PROCESS_KEY,
    submit_state='hr_review',
    driven=('approved',),
)


class PbProfileChangeRequestApproval(models.Model):
    _inherit = 'pb.profile.change.request'

    _approval_process_key = MASTER_PROCESS_KEY

    def _changed_fields(self):
        """Which proposed values really differ from what is recorded now."""
        self.ensure_one()
        changed = []
        for field in CONTACT_FIELDS:
            if field not in self._fields:
                continue
            current = 'cur_%s' % field[2:]
            if (self[field] or '') != (self[current] or '') and self[field]:
                changed.append(field)
        return changed

    def _chain_title(self):
        self.ensure_one()
        return _("Details · %s", self.employee_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        changed = self._changed_fields()
        contact_only = bool(changed) and all(
            field in CONTACT_FIELDS for field in changed)
        return {
            'fields_class': {'value': 'contact' if contact_only else 'other',
                             'unit': ''},
            'fields_changed': {'value': len(changed), 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'fields_class': {'type': 'selection',
                             'label': _('What kind of detail')},
            'fields_changed': {'type': 'int',
                               'label': _('How many values change')},
        }

    @api.model
    def _chain_kinds(self):
        return [{'key': 'contact', 'label': _('Contact details only')},
                {'key': 'other', 'label': _('Something else')}]

    def _approval_detail(self, request):
        self.ensure_one()
        labels = {
            'x_phone': _('Private phone'),
            'x_private_email': _('Private email'),
            'x_address': _('Address'),
            'x_emergency_contact': _('Emergency contact'),
            'x_emergency_phone': _('Emergency phone'),
        }
        rows = []
        for field in self._changed_fields():
            rows.append({
                'head': labels.get(field, field), 'sub': '',
                'cells': [self['cur_%s' % field[2:]] or _('Empty'),
                          self[field] or _('Empty')],
                'tone': 'on'})
        if not rows:
            return None
        return {'title': _('What would change'),
                'columns': [_('Now'), _('Proposed')], 'rows': rows,
                'chips': [], 'note': (self.note or '')[:240]}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead',
                                  'om_hr_payroll.group_hr_payroll_user')
        return Seed.lay(
            company, MASTER_PROCESS_KEY, 'Employee record changes',
            route(role_step(_('HR lead'), 'hr_lead')),
            binding_note='The route every change somebody makes to their own '
                         'details follows.',
            model_name='pb.profile.change.request',
            role_keys=('hr_lead',),
            reason='Set up when record-change approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.profile.change.request']._approval_seed_default(
                    company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_me_portal: %s has no record-change route',
                              company.name)
    return done
