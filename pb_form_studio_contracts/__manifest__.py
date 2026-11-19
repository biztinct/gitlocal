# -*- coding: utf-8 -*-
{
    'name': 'Payobook Form builder: contracts',
    'summary': "Your own fields on the contract screens",
    'description': """
Form builder on the contract screens (FORM STUDIO programme, phase FS-3).

Registers the contract as a Form builder screen and shows the administrator's
own contract fields ("Company details") in the contract side panel (edited
there, through the same approval as the other contract terms), on the
contract page and on the full contract form (whose top bar gets a "Form
builder" button for the administrator, R22); carries them to the new contract
on every renewal; and offers the choice, yes/no, link and date ones as filters
on the Contracts board.

Bridge only: reaches pb_contracts and pb_people_advanced by inheritance and
patches, edits neither. Silent install: no field, layout, page, job or mail is
created until the administrator publishes.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_form_studio', 'pb_contracts', 'pb_people_advanced'],
    'data': [],
    'assets': {
        # After both parents: the patches import their components.
        'web.assets_backend': [
            'pb_form_studio_contracts/static/src/scss/contracts_fs.scss',
            'pb_form_studio_contracts/static/src/js/contract_drawer_patch.js',
            'pb_form_studio_contracts/static/src/js/contract_detail_patch.js',
            'pb_form_studio_contracts/static/src/xml/contract_drawer_patch.xml',
            'pb_form_studio_contracts/static/src/xml/contract_detail_patch.xml',
            # R22: the "Form builder" button on the full contract form.
            'pb_form_studio_contracts/static/src/js/full_form_button.js',
            'pb_form_studio_contracts/static/src/xml/full_form_button.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
