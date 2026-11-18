# -*- coding: utf-8 -*-
"""Tax details on the employee home: the tile under "Me", "Needs you" when
HR sent a tax change back, and the tax rows of "My requests" (pb_me_portal's
hooks; this module never edits pb_me_portal)."""

import logging

from odoo import api, models

from .tax_rules import KINDS_BY_COUNTRY, NUMBER_FIELD, TAX_KINDS

_logger = logging.getLogger(__name__)

TAX_TILE = '/my/tax'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home
    # Under "Me", after pb_me_portal's own rows (seq 1-8), My details (9)
    # and Certificates (10) — ledger S6M-4. pb_me_portal's pinned "Me" list
    # (tests/test_me_home.py test_02) learns '/my/tax' at the merge: see the
    # S2-D report, merge-time task M1.
    pb_me_home.TILES.setdefault(TAX_TILE, {
        'group': 'me',
        'icon': 'shield',
        'tone': 'green',
        'seq': pb_me_home.GROUPS.index('me') * 100 + 11,
    })
except Exception:                           # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_me_tax: the Tax details tile could not be placed',
                    exc_info=True)


class PbMeHomeTax(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        back = self.env['pb.me.detail.request'].sudo().search_count([
            ('employee_id', '=', emp.id), ('kind', 'in', list(TAX_KINDS)),
            ('state', '=', 'draft'), ('decision_note', '!=', False)])
        if back:
            put('tax_sent_back', back, TAX_TILE,
                label=_('HR sent a tax change back') if back == 1
                else _('HR sent %s tax changes back', back),
                sub=_('Read why, then change it and send it again'),
                icon='rotate-ccw', tone='rose',
                sentence=_('HR sent a change to your tax details back.'))
        if self._pbtx_number_missing(emp):
            put('tax_number_missing', 1, TAX_TILE,
                label=_('Add your tax number'),
                sub=_('Your company needs it for your pay'),
                icon='shield', tone='indigo',
                sentence=_('Your tax number is not on file yet.'))

    @api.model
    def _pbtx_number_missing(self, emp):
        """Owner ruling TD1: remind a person whose tax number is not on file
        for the country of their pay set-up — only where this module keeps a
        tax number for that country (VN, ID, IN; not SG), and not while a
        tax-number change is waiting for HR or was sent back (that has its
        own row). A home row only; nothing is emailed."""
        emp = emp.sudo()
        country = emp._pbtx_country()
        field = NUMBER_FIELD.get(country)
        if 'tax_number' not in KINDS_BY_COUNTRY.get(country, ()) \
                or not field or field not in emp._fields or emp[field]:
            return False
        return not self.env['pb.me.detail.request'].sudo().search_count([
            ('employee_id', '=', emp.id), ('kind', '=', 'tax_number'),
            '|', ('state', '=', 'hr_review'),
            '&', ('state', '=', 'draft'), ('decision_note', '!=', False)])

    @api.model
    def _my_requests_rows(self, src, emp):
        """My details' source lists every request of the model; the tax ones
        are named and linked as tax details."""
        rows = super()._my_requests_rows(src, emp)
        if src.get('key') != 'my_details' or not rows:
            return rows
        _ = self.env._
        Req = self.env['pb.me.detail.request'].sudo()
        tax = set(Req.browse([r['id'] for r in rows]).filtered(
            lambda r: r.kind in TAX_KINDS).ids)
        for row in rows:
            if row['id'] in tax:
                row.update({'kind': _('Tax details'), 'icon': 'shield',
                            'url': '/my/tax/request/%s' % row['id']})
        return rows


class PbPeopleTaxGate(models.AbstractModel):
    _inherit = 'pb.people'

    def _e360_gate(self, emp, meta, country):
        """Full details: a country's tax group also shows for a person paid
        by a scheme of that country (not only by nationality)."""
        if super()._e360_gate(emp, meta, country):
            return True
        try:
            return emp._pbtx_country() == country
        except Exception:                   # noqa: BLE001 — never break the drawer
            return False
