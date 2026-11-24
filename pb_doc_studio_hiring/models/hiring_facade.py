# -*- coding: utf-8 -*-
"""Hiring's offer panel and the Document studio.

* "Which letter" names the copy that really prints when a company or country
  has its own copy of the offer letter, with the studio's plain note.
* The letter's language (owner ruling, A1 follow-up): the panel shows the
  language the letter will be written in and lets the recruiter choose
  another one before it goes out (screen twin of `pbds_letter_lang`). A new
  verb on the board's one door (`pb.hiring.act`), no Hiring file edited.
"""
from odoo import _, api, models
from odoo.exceptions import UserError

#: Offer states in which the letter can still be changed before it goes out.
LANG_OPEN_STATES = ('draft', 'submitted', 'manager_ok', 'hr_ok')


class PbHiringDocStudio(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _offer_row(self, offer, full=False):
        row = super()._offer_row(offer, full=full)
        if not full:
            return row
        tmpl = offer._pbds_offer_template()
        if tmpl and tmpl != offer.letter_template_id.sudo():
            row['template'] = tmpl.name or row.get('template', '')
            row['template_note'] = tmpl._pbds_wording_note() or ''
        names = dict(self.env['res.lang'].sudo().get_installed())
        auto, why = '', ''
        if not offer.pbds_letter_lang:
            auto = offer._pbds_offer_lang()
            why = _("the language they applied in") if offer._pbds_known_lang() \
                else _("the company's language")
        row.update({
            'letter_lang': offer.pbds_letter_lang or '',
            'letter_lang_auto': names.get(auto, auto) if auto else '',
            'letter_lang_why': why,
            'letter_langs': [{'code': c, 'name': n} for c, n in names.items()],
            'letter_lang_open': offer.state in LANG_OPEN_STATES and not self._pbds_signing(offer),
        })
        return row

    @api.model
    def _pbds_signing(self, offer):
        rec = offer.sudo()
        return bool('pb_envelope_id' in rec._fields and rec.pb_envelope_id
                    and rec.pb_sign_status in ('draft', 'pending', 'completed'))

    def _act_offer_letter_lang(self, payload):
        """Choose the language of the offer letter (empty = automatic). A
        letter already written is written again in it."""
        offer = self._offer(payload)
        self._require_recruit(offer.requisition_id)
        if offer.state not in LANG_OPEN_STATES or self._pbds_signing(offer):
            raise UserError(_(
                "The letter has already gone to the candidate, so its language "
                "can no longer change."))
        lang = payload.get('lang') or False
        names = dict(self.env['res.lang'].sudo().get_installed())
        if lang and lang not in names:
            raise UserError(_("That language is not switched on here."))
        offer.sudo().write({'pbds_letter_lang': lang})
        if offer.attachment_id:
            offer.action_prepare_letter()
        used = offer._pbds_offer_lang()
        note = _("The letter will be written in %s.", names.get(used, used)) if lang else _(
            "The letter will be written in %s, chosen automatically.", names.get(used, used))
        return {'id': offer.id, 'offer': self._offer_row(offer, full=True), 'note': note}
