# -*- coding: utf-8 -*-
{
    'name': 'PayAI does it — actions',
    # PAYAI P1 (2026-10-12). Foundation + the Green tier: a server-owned
    # catalogue of named Actions, slot resolvers, the two-part gate (Access
    # home screen + the method's own right), the `payai.task` audit row, the
    # cards the chat draws, the company switches and the "Ask PayAI to…" row.
    # PAYAI P2 (2026-10-12): the Amber tier — run payroll (driven in the
    # browser through the wizard's own chain, `@pb_payrun_wizard/js/run_driver`),
    # send for approval, change a pay value, send payslips, prepare a filing;
    # plan card → Do it → progress → result → undo.
    # PAYAI P3 (2026-10-12): the Red tier — approve, send back, reject what is
    # waiting for the person's OWN decision, confirmed by a typed word checked
    # on the server; "Remind <name>" when it is not theirs; "Learn to do this
    # yourself" on run / submit / approve done cards; the Audit console's
    # "Typed confirmation" badge.
    # PAYAI P4 (2026-10-13): Vietnamese — every card, refusal and setting
    # (i18n/vi_VN.po), Vietnamese phrasings for every Action (payai/
    # phrases_vi.py), Vietnamese months/amounts/dates, confirm words DUYỆT /
    # TRẢ LẠI / TỪ CHỐI beside the English ones; approvals doors open the one
    # request (pb_focus); P4-W1/W2 walk fixes.
    'version': '19.0.4.1.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Ask PayAI to open a screen, show a run, or prepare work you then confirm',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_payroll_ai_insights',
        'pb_hub',
        'pb_sidebar',
        'biz_access',
        'pb_payruns',
        'pb_payrun_wizard',
        'pb_audit',
        'base_setup',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/payai_security.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payai_actions/static/src/scss/cards.scss',
            'pb_payai_actions/static/src/xml/cards.xml',
            'pb_payai_actions/static/src/xml/audit_badge.xml',
            'pb_payai_actions/static/src/js/chat_patch.js',
            'pb_payai_actions/static/src/js/coach_patch.js',
            'pb_payai_actions/static/src/js/payai_palette.js',
            'pb_payai_actions/static/src/js/settings_card.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
