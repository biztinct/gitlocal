# -*- coding: utf-8 -*-
"""The dev host's record type — a tiny model of its own.

NOT res.partner: `res.users` `_inherits` `res.partner`, so a field made on a
partner would reach the user model too, which the safety rails forbid. This
model exists only so the Form builder can be exercised end to end before a
real screen hosts it. Nothing is created at install; the dev screen makes one
sample record on first open (administrator only).
"""
from odoo import fields, models


class PbFormSample(models.Model):
    _name = 'pb.form.sample'
    _description = 'Form builder sample record'
    _order = 'id'

    name = fields.Char(string='Full name', required=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    city = fields.Char(string='City')
    country_id = fields.Many2one('res.country', string='Country of work')
    date_start = fields.Date(string='Start date')
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
