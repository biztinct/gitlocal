# -*- coding: utf-8 -*-
"""The contract as a Form builder screen (THE HOST CONTRACT, FS1_REPORT §5).

One host, `contract`, on `hr.contract` — our ported model, never `hr.version`
or `hr.contract.history` (FS_HOST_FACTS §F). Its sections are the contract
side panel's own Terms groups, LOCKED (the panel draws them from its own
table), and one open section, "Company details", where the administrator's
fields go. New fields are created `copied=True` (R7: always carried on a
renewal or a copy).

The full contract form ("Advanced form") gets a "Company details" page kept in
step by the engine's native-view sync. The page is registered LAZILY — the
first time the engine re-draws the contract's pages (on a publish or a
delete) — so installing this module writes nothing at all.
"""
from odoo import api, models

from odoo.addons.pb_contracts.models.pb_contract_360 import term_group_label

HOST = 'contract'
MODEL = 'hr.contract'
NATIVE_VIEW = 'hr_contract.hr_contract_view_form'


class PbFormStudio(models.AbstractModel):
    _inherit = 'pb.form.studio'

    @api.model
    def _pbfs_hosts(self):
        hosts = super()._pbfs_hosts()
        env = self.env
        _ = env._
        note = _('Drawn by the contract screen itself. Fields cannot be placed here.')
        hosts[HOST] = {
            'model': MODEL,
            'title': _('Contract'),
            'icon': 'fileText',
            'sections': [
                {'id': 'money', 'title': term_group_label(env, 'money'), 'icon': 'banknote',
                 'tone': 'green', 'kind': 'locked', 'note': note},
                {'id': 'dates', 'title': term_group_label(env, 'dates'), 'icon': 'calendar',
                 'tone': 'blue', 'kind': 'locked', 'note': note},
                {'id': 'place', 'title': term_group_label(env, 'place'), 'icon': 'mapPin',
                 'tone': 'teal', 'kind': 'locked', 'note': note},
                {'id': 'rules', 'title': term_group_label(env, 'rules'), 'icon': 'shield',
                 'tone': 'amber', 'kind': 'locked', 'note': note},
                {'id': 'agreement', 'title': _('Agreement details'), 'icon': 'fileText',
                 'tone': 'blue', 'kind': 'locked', 'note': note},
                {'id': 'custom', 'title': _('Company details'), 'icon': 'sparkles',
                 'tone': 'brand', 'kind': 'open'},
            ],
            'default_layout': {'custom': []},
            'std_fields': [],
            'custom_section': 'custom',
            # R10: the person's Country of Work, through the contract's employee
            # (computed, never stored — models/hr_contract.py).
            'country_field': 'pb_country_of_work_id',
            'country_view_field': 'pb_country_of_work_id',
            # R7: custom contract fields are carried to the new contract, always.
            'copy_custom': True,
            'native_views': [NATIVE_VIEW],
            # R14 (ADDENDUM 2): contracts are not on My Payobook.
            'portal': False,
        }
        return hosts

    # ------------------------------------------------------------ full form
    @api.model
    def _fs3_page_titles(self):
        titles = {}
        for lang in self._pbfs_langs():
            titles[lang] = self.with_context(lang=lang).env._('Company details')
        return titles

    @api.model
    def _fs3_ensure_native(self):
        """Register the contract's full form with the engine once. Only the
        bookkeeping row: the engine draws (or removes) the page right after."""
        Native = self.env['pb.form.native.view'].sudo()
        if self.env.ref(NATIVE_VIEW, raise_if_not_found=False) is None:
            return False
        rec = Native.search([('model', '=', MODEL), ('parent_xmlid', '=', NATIVE_VIEW)], limit=1)
        if not rec:
            rec = Native.create({'model': MODEL, 'parent_xmlid': NATIVE_VIEW, 'host_key': HOST,
                                 'titles': self._fs3_page_titles()})
        return rec

    @api.model
    def _pbfs_resync_native(self, model, exclude=()):
        if model == MODEL:
            self._fs3_ensure_native()
        return super()._pbfs_resync_native(model, exclude=exclude)

    @api.model
    def fs3_full_form(self, view_id=False):
        """R22: may this person see the "Form builder" button on the form view
        `view_id`? Yes only for THE full contract form (`NATIVE_VIEW`) and only
        through the contract panel wand's own gate (`can_edit`, R2 — the
        administrator). Never raises: the button is simply not drawn. Opening
        the Form builder stays refused by the engine for anybody else
        (`get_studio` / `publish` → `_pbfs_check_admin`)."""
        if not self.can_edit(HOST):
            return False
        try:
            view_id = int(view_id or 0)
        except (TypeError, ValueError):
            return False
        view = self.env.ref(NATIVE_VIEW, raise_if_not_found=False)
        return bool(view and view_id and view.id == view_id)
