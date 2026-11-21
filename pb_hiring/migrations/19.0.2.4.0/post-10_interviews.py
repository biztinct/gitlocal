# -*- coding: utf-8 -*-
"""RECRUIT P5 — scorecards, Calendly, Google Meet, finalists.

  1. Every company gets the five starting scorecards (the seed also runs from
     `seed_journey`; this is belt and braces for the conversion below).
  2. The A2 opinions: recommendation → decision, the five scored lines →
     answers on an archived "Earlier scorecard", `score_avg` unchanged;
     waiting ones point at their interview's scorecard; one A2 chase becomes
     the first of the daily reminders (`pb.hiring.feedback._pb_migrate_legacy`).
  3. The mail templates whose MEANING changed live in a noupdate block, so
     they are written here from the module's own data file (RC41) — only
     where a company has not reworded them (the product's old words are
     still in them).
  4. Recruiter review's one-line meaning now promises the Calendly link
     (true from this version), where the stage still carries the product's
     old sentence.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

#: template xmlid -> words only the product's OLD version contains
TEMPLATES = {
    'mail_template_interview_candidate': 'There is a calendar file attached',
    'mail_template_interview_panel': 'Afterwards you will get your',
    'mail_template_interview_recruiter': 'anybody who is late, once',
    'mail_template_interview_tomorrow': 'A reminder that the interview for',
    'mail_template_interview_soon': 'The interview with',
    'mail_template_feedback_ask': 'Five lines to score',
    'mail_template_feedback_urgent': 'only reminder you will get',
}

OLD_PHONE = {'en_US': 'A 30-minute conversation with the recruiter.',
             'vi_VN': 'Một cuộc trao đổi 30 phút với chuyên viên tuyển dụng.'}


def _templates(env):
    from lxml import etree
    from odoo.modules.module import get_module_path
    tree = etree.parse(get_module_path('pb_hiring') + '/data/mail_template_interviews.xml')
    done = 0
    for xmlid, marker in TEMPLATES.items():
        tpl = env.ref('pb_hiring.' + xmlid, raise_if_not_found=False)
        rec = tree.xpath("//record[@id='%s']" % xmlid)
        if not tpl or not rec:
            continue
        body = str(tpl.with_context(lang='en_US').body_html or '')
        if marker not in body or 'pb_join_url' in body or 'pb_link_url' in body:
            continue                    # reworded by the company, or done
        vals = {}
        for field in rec[0].findall('field'):
            name = field.get('name')
            if name in ('subject',):
                vals[name] = (field.text or '').strip()
            elif name == 'body_html':
                vals[name] = ''.join(etree.tostring(c, encoding='unicode') for c in field)
        tpl.sudo().write(vals)
        done += 1
    return done


def _phone_meaning(env):
    from odoo.addons.pb_hiring.models.journey import MEANINGS, VI_MEANINGS
    stage = env['hr.recruitment.stage']._pb_stage('phone')
    if not stage:
        return 0
    if (stage.with_context(lang='en_US').pb_meaning or '') != OLD_PHONE['en_US']:
        return 0
    todo = {'en_US': MEANINGS['phone']}
    if stage.with_context(lang='vi_VN').pb_meaning == OLD_PHONE['vi_VN']:
        todo['vi_VN'] = VI_MEANINGS['phone']
    langs = set(env['res.lang'].sudo().search([('active', '=', True)]).mapped('code'))
    stage.with_context(lang='en_US').write({'pb_meaning': MEANINGS['phone']})
    todo = {k: v for k, v in todo.items() if k in langs and k != 'en_US'}
    if todo:
        stage.update_field_translations('pb_meaning', todo)
    return 1


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    made = env['pb.hiring.scorecard']._ensure_seeds()
    moved = env['pb.hiring.feedback']._pb_migrate_legacy()
    tpls = _templates(env)
    meaning = _phone_meaning(env)
    _logger.info('pb_hiring 2.4.0: %s scorecards seeded; opinions %s; %s templates '
                 'rewritten; Recruiter review meaning updated: %s',
                 made, moved, tpls, meaning)
