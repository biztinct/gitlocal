# -*- coding: utf-8 -*-
"""RECRUIT P7 — channels and agencies.

  1. Several agencies per role: the old single column
     `pb_hiring_requisition.agency_vendor_id` (now a computed read of the
     first agency, so the ORM leaves the column in place) is copied into
     `pb_hiring_requisition_agency_rel`. Safe to run again.
  2. Duplicate utm sources (`facebook` beside `Facebook`) are merged into the
     seeded / oldest row (`channels_p7.merge_duplicate_sources`).
  3. Every company gets its six channels (the data `<function>` does it too).
  4. Existing candidates are tagged with the channel their source belongs to.
  5. "An agency is working on this role" names the agency ADDED (noupdate,
     RC41): rewritten from the data file only where the old words remain.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists, table_exists

_logger = logging.getLogger(__name__)


def _copy_agencies(cr):
    if not column_exists(cr, 'pb_hiring_requisition', 'agency_vendor_id') \
            or not table_exists(cr, 'pb_hiring_requisition_agency_rel'):
        return 0
    cr.execute("""
        INSERT INTO pb_hiring_requisition_agency_rel (requisition_id, vendor_id)
        SELECT r.id, r.agency_vendor_id
          FROM pb_hiring_requisition r
          JOIN pb_vendor v ON v.id = r.agency_vendor_id
         WHERE r.agency_vendor_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM pb_hiring_requisition_agency_rel x
                            WHERE x.requisition_id = r.id AND x.vendor_id = r.agency_vendor_id)
    """)
    return cr.rowcount


def _template(env):
    from lxml import etree
    from odoo.modules.module import get_module_path
    tpl = env.ref('pb_hiring.mail_template_requisition_agency', raise_if_not_found=False)
    if not tpl:
        return 0
    body = str(tpl.with_context(lang='en_US').body_html or '')
    if 'agency_vendor_id.name' not in body:
        return 0
    tree = etree.parse(get_module_path('pb_hiring') + '/data/mail_template_offer.xml')
    rec = tree.xpath("//record[@id='mail_template_requisition_agency']")
    if not rec:
        return 0
    for field in rec[0].findall('field'):
        if field.get('name') == 'body_html':
            tpl.sudo().write({'body_html': ''.join(
                etree.tostring(c, encoding='unicode') for c in field)})
            return 1
    return 0


def _tag_channels(env):
    cr = env.cr
    cr.execute("""
        UPDATE hr_applicant a
           SET pb_channel_id = c.id
          FROM pb_hiring_channel c
         WHERE a.pb_channel_id IS NULL
           AND a.source_id = c.utm_source_id
           AND a.company_id = c.company_id
    """)
    return cr.rowcount


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.pb_hiring.models.channels_p7 import merge_duplicate_sources
    copied = _copy_agencies(cr)
    merged = merge_duplicate_sources(env)
    made = env['pb.hiring.channel']._seed_all()
    tagged = _tag_channels(env)
    rewritten = _template(env)
    _logger.info('pb_hiring P7: %s agency links copied, %s duplicate sources merged, '
                 '%s channels made, %s candidates tagged with a channel, '
                 '%s template rewritten', copied, merged, made, tagged, rewritten)
