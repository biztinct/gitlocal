# -*- coding: utf-8 -*-
"""RECRUIT P8 — every candidate email through one mechanism, and the
automations.

  1. Every company gets the ten new candidate emails (interview invitation,
     day before, half hour, video link, called off, next round, interview
     reject, papers ask and reminder, the offer) as rows of the company's
     Candidate emails, in English, Vietnamese and Bahasa Indonesia; the three
     old rows that only had English (assignment, on hold, CV reject) get
     their other languages where the product's words are untouched.
  2. The ten English-only candidate `mail.template` records they replace are
     archived — except the four interview mails the panel and the recruiter
     still receive (their candidate copy moved). Nobody had edited one on the
     three databases (checked 2026-10-01: every write was by the system), so
     there is nothing to carry across.
  3. Every company gets its four starting automations (Calendly ON — P5's
     rule, same behaviour; the assignment brief, the first-look nudge and the
     buddy to-do OFF).
  4. The switches the built-in rows map to default in code (`auto_received`,
     `auto_chase`, `auto_doc_remind`, `auto_check_todo`,
     `auto_close_finalists`, `auto_week_before`, `auto_share_mail` = on); none
     is written here, so a database keeps whatever it already chose.

The data `<function>` (`data/recruit_p8.xml`) runs the same idempotent seed on
every upgrade; this file runs it once more and logs what changed.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    out = env['pb.hiring']._seed_p8()
    _logger.info('pb_hiring 19.0.2.7.0: candidate emails made %s, language versions '
                 'written %s, old English-only templates archived %s, automations '
                 'seeded %s', out.get('made'), out.get('filled'), out.get('archived'),
                 out.get('rules'))
