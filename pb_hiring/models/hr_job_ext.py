# -*- coding: utf-8 -*-
"""`hr.job` — the one answer to "can somebody apply for this role here?".

The application form refuses a role that is not public, belongs to another
company or website, or whose request is not open (or is a sensitive
replacement). The careers page must ask the SAME question before it offers an
"Apply" button, otherwise a signed-in person — who is shown unpublished roles —
presses Apply and lands on "page not found". Both ask here.

No leading underscore on purpose: page templates cannot call private names.
It only reads, so being callable from outside costs nothing.
"""
from odoo import models


class HrJob(models.Model):
    _inherit = 'hr.job'

    def pb_hiring_accepts_applications(self, website):
        job = self.sudo().exists()
        if len(job) != 1 or not job.active or not job.is_published:
            return False
        if job.company_id != website.company_id:
            return False
        if job.website_id and job.website_id != website:
            return False
        req = self.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', job.id)], order='id desc', limit=1)
        return not req or (req.state == 'open'
                           and req.role_type != 'sensitive_replacement')
