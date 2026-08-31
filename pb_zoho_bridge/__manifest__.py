# -*- coding: utf-8 -*-
{
    'name': 'Payobook Zoho Bridge',
    'summary': 'The receiving door: joiners and leavers arrive from the '
               'connected system and start their journey by themselves',
    'description': """
RIZE phase P1 — the inbound door from Zoho People.

WHAT THIS MODULE IS

  * `POST /api/zoho/webhook` — a token-gated public endpoint, shaped exactly
    like the DarwinHR one it is cloned from (`pb_hr_payroll_formula/controllers/
    darwin_webhook.py`). It never trusts the caller further than the connector
    id + api key it presents, and every rejection answers the SAME word so the
    endpoint cannot be probed for which connectors exist.
  * `pb.zoho.event.rule` — the policy, as data. "An employee arrived" opens an
    onboarding journey; "Resigned" opens an exit journey; an unknown word is
    written down for a human rather than guessed at. HR can re-order, disable
    or add rules without a developer.
  * `pb.zoho.inbox` — one row per received record, forever. It is the audit
    trail AND the idempotency key: a payload that arrives twice is recognised
    by its event id and produces exactly nothing the second time.
  * `pb.zoho.pipeline` — the one road every arrival travels, whether it came
    down the webhook or out of a spreadsheet somebody uploaded. One savepoint
    per record, so one bad row cannot take the other ninety-nine with it.
  * `pb.zoho.upload.wizard` — the fallback for the day the push is not wired
    yet, or the tenant will not push at all: the same file HR already exports,
    through the same pipeline, with a preview before anything is written.

THE FIELD OWNERSHIP LINE (blueprint §14 / ruling D8). The connected system owns
who a person is and whether they are still employed. Payobook owns what they are
paid, their probation, their assets, their vendors and their budgets. That line
is enforced HERE, in one place, by `_WHITELIST`: no arriving payload can write a
wage, a bank account or a contract, no matter what it contains. Nothing flows
back OUT of Payobook — outbound is deliberately not built.

THE LOGIN (ruling D6). A portal account is created the moment the person's
record arrives, so it exists and is ready — but the email that tells them about
it is NOT sent then. `send_credentials()` is a separate act, which the joining-day
step of their journey performs. An account that exists in silence is useful; an
account announced three weeks early is a support ticket.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'pb_hub',                   # the global ⌘K palette registry
        'pb_hr_payroll_base',       # the integration user group
        'pb_hr_payroll_formula',    # connectors, the webhook_ingest hook, the raw store
        'pb_lifecycle',             # the journey engine an arrival starts
    ],
    'data': [
        'security/pb_zoho_bridge_security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'data/event_rule_data.xml',
        'views/event_rule_views.xml',
        'views/inbox_views.xml',
        'views/zoho_upload_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_zoho_bridge/static/src/js/zoho_palette.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
