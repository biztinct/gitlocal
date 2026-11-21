# -*- coding: utf-8 -*-
"""LEARNING L2 — training HOURS, on the course, the assignment and the paper.

Three statutory reports count hours: Vietnam's safety groups (16 / 24 / 48
hours and a refresher at half of it), Singapore's training-hours return, and
every "hours done" column an auditor asks for. Until L2 nothing stored them.

  * `slide.channel.pb_hours` — the course's hours, typed by the training team.
    Empty means "use the content engine's own total" (`total_time`, the sum
    of the lessons' durations, which may well be zero).
  * `pb.training.assignment.hours` — written ONCE, the moment the assignment
    crosses into `done`, from the course's hours at that moment. A course
    whose hours change later does not rewrite what somebody already did.
  * `pb.employee.document.hours` — the certificate record's hours: copied from
    the course for a passed test, typed for an upload (optional).
"""

from odoo import api, fields, models


class SlideChannelHours(models.Model):
    _inherit = 'slide.channel'

    pb_hours = fields.Float(
        string='Hours', digits=(6, 2),
        help='How many hours this course counts for. Leave it empty and the '
             'lessons\' own durations are added up instead.')

    def _pb_hours(self):
        """The course's hours: the typed figure, else the lessons' total."""
        self.ensure_one()
        sudo = self.sudo()
        return float(sudo.pb_hours or sudo.total_time or 0.0)


class PbTrainingAssignmentHours(models.Model):
    _inherit = 'pb.training.assignment'

    hours = fields.Float(
        string='Hours', digits=(6, 2), readonly=True, copy=False,
        help='Written when the course is finished, from the course\'s hours '
             'at that moment.')

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        # ON THE CROSSING ONLY, like the certificate filing beside it: this
        # method runs on every board read.
        if state == 'done' and was != 'done' and not self.hours:
            hours = self.channel_id._pb_hours() if self.channel_id else 0.0
            if hours:
                self.sudo().with_context(
                    tracking_disable=True, mail_notrack=True).write(
                    {'hours': hours})
        return state


class PbEmployeeDocumentHours(models.Model):
    _inherit = 'pb.employee.document'

    hours = fields.Float(
        string='Training hours', digits=(6, 2), copy=False,
        help='How many hours of training this certificate stands for.')


class PbTrainingCertificateHours(models.AbstractModel):
    _inherit = 'pb.training.certificate'

    @api.model
    def file_course_certificate(self, channel, partner):
        document = super().file_course_certificate(channel, partner)
        if document and not document.hours and document.channel_id:
            hours = document.channel_id._pb_hours()
            if hours:
                document.sudo().write({'hours': hours})
        return document

    @api.model
    def _create_upload(self, employee, values, upload, source='upload'):
        document = super()._create_upload(employee, values, upload, source)
        raw = (values or {}).get('hours')
        try:
            hours = max(float(raw or 0.0), 0.0)
        except (TypeError, ValueError):
            hours = 0.0
        if document and hours:
            document.sudo().write({'hours': min(hours, 9999.0)})
        return document
