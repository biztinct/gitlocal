# -*- coding: utf-8 -*-
"""LEARNING L1 — demo certificates on payobook (handover §6). Idempotent.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l1_demo_seed.py

What it does (every new record named "DEMO …" and put on the demo register):
  1. Gives survey 17 ("DEMO Agronomist basics — test") 12 months' validity and
     re-runs the certificate back-fill, which stamps document 145's
     valid-until date (issue date + 12 months).
  2. Files three certificates for two DEMO employees: a forklift licence that
     expires in 20 days (statutory, checked), a first-aid certificate that
     expires in 75 days (uploaded, not checked) and a pesticide permit that
     expired 10 days ago (statutory, checked).
  3. Runs the morning job ONCE INSIDE A SAVEPOINT THAT IS ROLLED BACK ("test
     mode"): it prints what the job would have done — renewal courses, and
     certificate reminders — and then undoes all of it, so no email is queued
     and no assignment is left behind.
Nothing here contains a password or a real person's data.
"""
import base64
import logging

from datetime import timedelta

from odoo import fields

_logger = logging.getLogger('l1_demo_seed')

LABEL = 'DEMO Learning L1 certificates'
SURVEY_ID = 17
DOC_145 = 145
PREFERRED_EMPLOYEES = (20208, 20209)

PDF = base64.b64decode(
    b'JVBERi0xLjQKMSAwIG9iajw8L1R5cGUvQ2F0YWxvZy9QYWdlcyAyIDAgUj4+ZW5kb2JqCjIg'
    b'MCBvYmo8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PmVuZG9iagozIDAgb2Jq'
    b'PDwvVHlwZS9QYWdlL1BhcmVudCAyIDAgUi9NZWRpYUJveFswIDAgMjAwIDIwMF0+PmVuZG9i'
    b'agp0cmFpbGVyPDwvUm9vdCAxIDAgUj4+CiUlRU9GCg==')


def say(msg, *args):
    print('L1 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
today = fields.Date.today()
Cert = env['pb.training.certificate'].sudo()
Doc = env['pb.employee.document'].sudo().with_context(active_test=False)
seed = env.get('pb.demo.seed')

# ---------------------------------------------------------------- 1. validity
survey = env['survey.survey'].sudo().browse(SURVEY_ID).exists()
if survey and (survey.title or '').startswith('DEMO'):
    survey.certification_validity_months = 12
    say('survey %s "%s" now valid for 12 months', survey.id, survey.title)
else:
    say('survey %s is not the DEMO test here — validity left alone', SURVEY_ID)
counts = Cert._backfill()
say('back-fill: %s', counts)
doc145 = Doc.browse(DOC_145).exists()
if doc145:
    say('document 145 "%s": source %s, issued %s, valid until %s (%s)',
        doc145.name, doc145.training_source, doc145.issue_date,
        doc145.expiry_date, doc145.valid_words)

# ---------------------------------------------------------------- 2. three docs
Emp = env['hr.employee'].sudo()
people = Emp.browse(PREFERRED_EMPLOYEES).exists().filtered(
    lambda e: (e.name or '').startswith('DEMO') or e.id in PREFERRED_EMPLOYEES)
if len(people) < 2:
    people = Emp.search([('name', '=like', 'DEMO%'), ('active', '=', True)],
                        limit=2)
if len(people) < 2:
    say('fewer than two DEMO employees found — no certificates filed')
    people = Emp.browse()
else:
    say('filing for %s', ', '.join('%s (%s)' % (p.name, p.id) for p in people))

plan = [
    # (employee index, name, kind, source, issued days ago, expires in days)
    (0, 'DEMO Forklift operator licence', 'LIC', 'statutory', 345, 20),
    (1, 'DEMO First aid certificate', 'CERT', 'upload', 290, 75),
    (1, 'DEMO Pesticide handling permit', 'LIC', 'statutory', 375, -10),
]
made = Doc.browse()
for idx, name, kind, source, ago, left in plan if people else []:
    emp = people[idx]
    existing = Doc.search([('employee_id', '=', emp.id), ('name', '=', name)],
                          limit=1)
    if existing:
        say('already there: %s on %s (document %s)', name, emp.name,
            existing.id)
        continue
    doc = Cert._create_upload(emp, {
        'name': name, 'kind': kind,
        'issuer': 'DEMO Training Authority',
        'reference': 'DEMO-%s' % (len(made) + 1),
        'issue_date': fields.Date.to_string(today - timedelta(days=ago)),
        'expiry_date': fields.Date.to_string(today + timedelta(days=left)),
    }, ('%s.pdf' % name, PDF), source)
    if source == 'statutory':
        doc._pb_training_verify()
    made |= doc
    say('filed %s on %s (document %s): %s', name, emp.name, doc.id,
        doc.valid_words)
if made and seed is not None:
    seed.register(made.mapped('attachment_id'), LABEL, last=True)
    seed.register(made, LABEL)
    say('registered %s document(s) on the demo register', len(made))
env.cr.commit()

# ---------------------------------------------------------------- 3. test mode
Auto = env['pb.training.automation'].sudo()
renewal_docs = Auto._renewal_candidates(today)
say('renewal candidates today (window %s days): %s',
    env['ir.config_parameter'].sudo().get_param(
        'pb_training.renew_before_days', '60'),
    ', '.join('%s "%s" expires %s' % (d.id, d.name, d.expiry_date)
              for d in renewal_docs) or 'none')
try:
    with env.cr.savepoint():
        result = Auto._cron_daily()
        say('morning job, test mode: %s', result)
        raise RuntimeError('roll back the test run')
except RuntimeError:
    say('test run rolled back: no email queued, no assignment kept')
