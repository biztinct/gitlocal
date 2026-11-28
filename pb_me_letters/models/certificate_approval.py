# -*- coding: utf-8 -*-
"""The salary certificate's one HR click is a step in the one Approvals inbox.

Only the SALARY certificate travels a route (the employment certificate
carries no pay figure and is issued at once, owner ruling E2). The default
every company gets is ONE step, the HR lead. "Approve" issues it.
"""
import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

CERT_PROCESS_KEY = 'me_certificate'

register_chain(
    'pb.me.certificate', CERT_PROCESS_KEY,
    submit_state='hr_review',
    driven=('issued',),
)


class PbMeCertificateApproval(models.Model):
    _inherit = 'pb.me.certificate'

    _approval_process_key = CERT_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        rec = self.sudo()
        kinds = dict(rec._fields['kind']._description_selection(self.env))
        return _("%(what)s · %(who)s", what=kinds.get(rec.kind, ''),
                 who=rec.employee_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'has_pay_figures': {'value': self.kind == 'salary', 'unit': ''},
            'purpose': {'value': self.purpose or '', 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'has_pay_figures': {'type': 'bool',
                                'label': _('Shows pay figures')},
            'purpose': {'type': 'selection', 'label': _('What it is for')},
        }

    def _chain_revision_values(self):
        self.ensure_one()
        rec = self.sudo()
        return {'employee': rec.employee_id.id, 'kind': rec.kind,
                'purpose': rec.purpose, 'note': rec.purpose_note or '',
                'lang': rec.lang or ''}

    def _approval_detail(self, request):
        self.ensure_one()
        rec = self.sudo()
        purposes = dict(rec._fields['purpose']._description_selection(self.env))
        rows = [{'head': _('What it is for'), 'sub': '',
                 'cells': [purposes.get(rec.purpose, ''),
                           rec.purpose_note or ''], 'tone': 'off'}]
        note = ''
        if rec.kind == 'salary':
            try:
                values = rec._pb_values()
                rows.append({'head': _('Agreed monthly salary'), 'sub': '',
                             'cells': [values.get('salary', ''), ''],
                             'tone': 'on'})
            except Exception as exc:        # noqa: BLE001 — the reason is shown
                note = exc.args[0] if exc.args else ''
        return {'title': _('The certificate'),
                'columns': [_('Asked for'), _('Details')],
                'rows': rows, 'chips': [], 'note': note}

    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead',
                                  'om_hr_payroll.group_hr_payroll_user')
        return Seed.lay(
            company, CERT_PROCESS_KEY, 'Salary certificates',
            route(role_step(_('HR lead'), 'hr_lead')),
            binding_note='HR looks at a salary certificate before it is '
                         'issued, because it shows the agreed salary.',
            model_name='pb.me.certificate',
            role_keys=('hr_lead',),
            reason='Set up when salary certificates were switched on')


class ResCompanyCertificateSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.me.certificate'].sudo()._approval_seed_default(
                        company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_me_letters: %s has no certificate route',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.me.certificate']._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_me_letters: %s has no certificate route',
                              company.name)
    return done
