# -*- coding: utf-8 -*-
"""LEARNING L6 — demo data for Numbers and the Overview on payobook
(handover §1 item 6). Idempotent and small: L6 adds no new kind of record,
it reads what L1–L5 seeded.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l6_demo_seed.py

(Locally L6_SEED_COMPANY and L6_SEED_HR override the payobook defaults.)

What it does:
  1. Puts a cost on the two DEMO sessions L4 seeded on "DEMO Site safety walk"
     (only where none is set): next week's 3,500,000, last week's (closed)
     4,500,000 — so Numbers › Cost has a sessions line. The toolbox talk
     "DEMO Lifting safely" stays free.
  2. Changes NO setting: the training pack stays as it is (off), reminders,
     feedback and day one keep their values. The Learning settings screen is
     walked read-and-undo, never saved, on payobook.
  3. Prints, as the HR lead, what the live walk should see: the Numbers
     hours / cost / required-training / did-it-work sentences, the Overview
     headline and what waits, and the Learning settings sentences.
  4. NO EMAIL: nothing here sends; anything queued by the run is cancelled
     (state "cancel", never deleted — the L3 lesson).
Nothing here contains a password or a real person's data.
"""
import os
from datetime import timedelta

from odoo import fields

COMPANY_ID = int(os.environ.get('L6_SEED_COMPANY') or 5)
HR_LEAD = os.environ.get('L6_SEED_HR') or 'demo.hr@example.com'
LABEL = 'DEMO Learning L6 session costs'


def say(msg, *args):
    print('L6 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
seed = env.get('pb.demo.seed')
company = env['res.company'].browse(COMPANY_ID).exists() or env.company
base = {k: v for k, v in env.context.items() if k != 'tz'}
env = env(context=dict(base, allowed_company_ids=[company.id],
                       lang='en_US'))
mails_last = env['mail.mail'].sudo().search(
    [], order='id desc', limit=1).id or 0
today = fields.Date.today()
say('company %s "%s"', company.id, company.name)

# ------------------------------------------------------------- 1. costs
Session = env['pb.training.session'].sudo()
sessions = Session.search([('company_id', '=', company.id),
                           ('channel_id.name', '=', 'DEMO Site safety walk'),
                           ('kind', '!=', 'toolbox')], order='start')
now = fields.Datetime.now()
for sess in sessions:
    if sess.cost:
        say('session %s already has a cost (%s) — left alone', sess.id,
            sess.cost)
        continue
    amount = 4500000.0 if sess.start and sess.start < now else 3500000.0
    sess.write({'cost': amount})
    say('session %s (%s, %s): cost %s %s', sess.id, sess.state,
        fields.Datetime.to_string(sess.start), amount,
        company.currency_id.name)
if seed is not None:
    for sess in sessions:
        try:
            seed.register(sess, LABEL)
        except Exception as err:        # noqa: BLE001 — say it, carry on
            say('could not register %s: %s', sess, err)

# ------------------------------------------------------------- 3. what to see
hr_user = env['res.users'].sudo().search([('login', '=', HR_LEAD)], limit=1)
if hr_user:
    as_hr = env(user=hr_user.id)
    nums = as_hr['pb.training.analytics'].get_numbers(
        fields.Date.to_string(today - timedelta(days=90)),
        fields.Date.to_string(today), {})
    say('Numbers (last 3 months) hours: %s', nums['hours'].get('headline'))
    say('Numbers cost: %s', nums['cost'].get('headline'))
    comp = nums.get('compliance')
    say('Numbers required training: %s', comp and comp.get('headline'))
    eff = nums.get('effect') or {}
    say('Numbers did it work: %s ratings, avg %s, recommend %s%%, work '
        'changed %s/5', eff.get('ratings_count'), eff.get('ratings_avg'),
        eff.get('recommend_pct'), eff.get('followup_effect_avg'))
    over = as_hr['pb.training'].overview()
    say('Overview headline: %s', over.get('headline'))
    say('Overview waiting: %s', [(q['key'], q['count'])
                                 for q in over.get('waiting') or []])
    sets = as_hr['pb.training'].settings_get()
    say('Settings (HR lead) allowed %s, can_write %s', sets.get('allowed'),
        sets.get('can_write'))
    for key, words in (sets.get('words') or {}).items():
        say('  %s: %s', key, words)
else:
    say('no HR lead login %s — skipped the read-out', HR_LEAD)

# ------------------------------------------------------------- 4. no mail
queued = env['mail.mail'].sudo().search([('state', '=', 'outgoing')],
                                        order='id desc', limit=500).filtered(
    lambda m: m.id > mails_last)
queued.write({'state': 'cancel'})
say('mail queued by this run and cancelled: %s', len(queued))
env.cr.commit()
say('done')
