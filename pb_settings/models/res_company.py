# -*- coding: utf-8 -*-
"""ACCESS P9 — the company record gains an old→new trail.

WHY HERE AND NOT IN THE FACADE. "Your company" writes through
`pb.company.profile`, so the facade could easily have written its own audit
line. It would have been the wrong place: the platform's own Companies screen
also writes this record, and a trail that only knows about one of the two doors
is a trail that says a change was never made. The mixin sits on the MODEL, so
every write is caught wherever it came from.

WHAT IS WATCHED IS DATA, NOT CODE. `data/biz_audit_rule.xml` names the fields,
and it names exactly the whitelist in `pb_company_profile.py` minus the logo —
a test asserts the two stay in step, because a rule that drifts from the
whitelist audits a field nobody can change or misses one anybody can.

THE LOGO IS DELIBERATELY NOT WATCHED. The generic audit writes a field's value
into a text column; for a picture that is a megabyte of encoded bytes, and two
different pictures of the same size would read as no change at all. The facade
writes one readable line for it instead ("a picture → a new picture").
"""
from odoo import models


class ResCompany(models.Model):
    # The three-line glue the audit engine documents: the model, plus the
    # mixin, and nothing else. No field, no override, no behaviour of our own —
    # the mixin's write() is ormcached per model and returns immediately when
    # no rule watches a field that was touched.
    _name = 'res.company'
    _inherit = ['res.company', 'biz.audit.mixin']

    def _biz_audit_company(self):
        """An entry about a company belongs to THAT company.

        The generic answer is "the record's own company_id, or the acting
        user's company". `res.company` has no `company_id` — it IS one — so
        without this an entry about company B, written by somebody whose own
        company is A, would be filed under A and vanish from B's own history.
        """
        self.ensure_one()
        return self.id
