# -*- coding: utf-8 -*-
{
    'name': 'Payobook Employment contract documents',
    'summary': 'Employment contracts per country, printed from the contract panel',
    'description': """
Employment contract documents (DOCSTUDIO programme, phase A2).

* A document kind "Employment contract" in the Document studio, with its
  own gallery group, contract fields (reference, term, trial period,
  working time, pay, employer representative, the employee's papers and
  address, the customer's own fields) and two conditions (fixed term or
  open-ended; trial period).
* Starting wording, neutral and structural: one English original for every
  country of work, and bilingual copies for Vietnam (Vietnamese | English)
  and Indonesia (Indonesian | English). The designer marks them as starting
  wording to be checked against local labour law.
* "Contract document" in the contract side panel: the finished contract
  for that contract, in its language, with what is missing listed above
  the page; Download PDF; Save to documents as a running version (earlier
  versions are kept); Change the wording for people allowed.

No e-signature. Silent install: no job, no mail, no data written on any
existing record. See docs/handovers/docstudio/DOCSTUDIO_A2_REPORT.md.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_doc_studio', 'pb_contracts', 'pb_employee_vault'],
    'data': [
        'report/contract_frame.xml',
        'data/contract_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_doc_contracts/static/src/scss/contract_doc.scss',
            'pb_doc_contracts/static/src/scss/contract_paper.scss',
            'pb_doc_contracts/static/src/js/contract_doc.js',
            'pb_doc_contracts/static/src/xml/contract_doc.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
