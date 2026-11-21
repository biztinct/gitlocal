# -*- coding: utf-8 -*-
"""RECRUIT P6 — from signed to joined.

  1. Joined offers (the old `closed`): the expected date and the day they
     started are the offer's start date (the old closure anchored the
     contract on it), status confirmed.
  2. The single signed copy becomes the first signed document on every offer
     that has one; on a joined offer it is matched to the vault row the old
     closure filed ("Signed offer <ref>"), so nothing is filed twice.
  3. An offer that is SIGNED but not joined (none on the live databases at
     the time of writing) goes to Post-offer with its list, quietly.
  4. `filled_count` is recomputed (it now counts `joined`).
  5. "Somebody is joining" now says they STARTED (noupdate, RC41): rewritten
     from the data file only where the product's old words are still in it.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _template(env):
    from lxml import etree
    from odoo.modules.module import get_module_path
    tpl = env.ref('pb_hiring.mail_template_offer_closed', raise_if_not_found=False)
    if not tpl:
        return 0
    body = str(tpl.with_context(lang='en_US').body_html or '')
    if 'has signed and joins as' not in body:
        return 0
    tree = etree.parse(get_module_path('pb_hiring') + '/data/mail_template_offer.xml')
    rec = tree.xpath("//record[@id='mail_template_offer_closed']")
    if not rec:
        return 0
    vals = {}
    for field in rec[0].findall('field'):
        name = field.get('name')
        if name == 'subject':
            vals[name] = (field.text or '').strip()
        elif name == 'body_html':
            vals[name] = ''.join(etree.tostring(c, encoding='unicode') for c in field)
    tpl.sudo().write(vals)
    return 1


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Offer = env['pb.hiring.offer'].sudo().with_context(tracking_disable=True,
                                                       mail_notrack=True)
    Doc = env['pb.hiring.offer.document'].sudo()
    joined = Offer.search([('state', '=', 'joined')])
    for offer in joined:
        offer.write({'expected_join_date': offer.expected_join_date or offer.start_date,
                     'joined_on': offer.joined_on or offer.start_date,
                     'join_status': 'confirmed'})
    made = 0
    for offer in Offer.search([('signed_attachment_id', '!=', False)]):
        att = offer.signed_attachment_id
        if Doc.search_count([('offer_id', '=', offer.id), ('attachment_id', '=', att.id)]):
            continue
        doc = Doc.create({'offer_id': offer.id, 'attachment_id': att.id,
                          'kind': 'offer_letter', 'signed_on': offer.signed_on,
                          'recorded_by_id': offer.signed_by_id.id or False})
        made += 1
        if offer.state == 'joined' and offer.employee_id:
            vault = env['pb.employee.document'].sudo().search([
                ('employee_id', '=', offer.employee_id.id),
                ('name', '=', doc._vault_name())], limit=1)
            if vault:
                doc.write({'vault_doc_id': vault.id})
    signed = Offer.search([('state', '=', 'signed')])
    for offer in signed:
        offer._on_signed(quiet=True)
    reqs = Offer.search([]).mapped('requisition_id')
    if reqs:
        env.add_to_compute(reqs._fields['filled_count'], reqs)
        env.add_to_compute(reqs._fields['offer_out_count'], reqs)
        reqs._recompute_recordset(['filled_count', 'offer_out_count'])
    rewritten = _template(env)
    _logger.info('pb_hiring P6: %s joined offers stamped, %s signed documents made, '
                 '%s signed offers moved to Post-offer, %s roles recounted, '
                 '%s template rewritten', len(joined), made, len(signed), len(reqs),
                 rewritten)
