# -*- coding: utf-8 -*-
"""Shared fixtures for the CLOCK-1 tests (handover §7).

A fresh company in Asia/Ho_Chi_Minh so no lock, packet or punch already on the
test database can own these days. Employees `885` (badge 885) and `227` (clock
number 227); a machine "Factory 1" with an invented serial. Settings at their
defaults. Codes and times are the shapes from the client's answers — never a
real name, phone, serial or hostname (ledger rule 13).
"""
from datetime import datetime

import pytz

from odoo.tests import TransactionCase


class ClockCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'CLK Test Panels'})
        cls.company.resource_calendar_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tz='Asia/Ho_Chi_Minh'))
        cls.Punch = cls.env['pb.clock.punch']
        cls.Pairing = cls.env['pb.clock.pairing'] \
            if 'pb.clock.pairing' in cls.env else None
        cls.Att = cls.env['hr.attendance']
        cls.tz = pytz.timezone('Asia/Ho_Chi_Minh')
        Emp = cls.env['hr.employee']
        cls.e885 = Emp.create({
            'name': 'CLK Worker 885', 'company_id': cls.company.id,
            'tz': 'Asia/Ho_Chi_Minh', 'barcode': '885'})
        cls.e227 = Emp.create({
            'name': 'CLK Worker 227', 'company_id': cls.company.id,
            'tz': 'Asia/Ho_Chi_Minh', 'pb_clock_code': '227'})
        cls.device = cls.env['pb.clock.device'].create({
            'name': 'Factory 1', 'serial': 'TEST-0001', 'kind': 'terminal',
            'company_id': cls.company.id, 'tz': 'Asia/Ho_Chi_Minh'})
        # a fixed "now" after every fixture punch, so outliers are deterministic
        cls.now = datetime(2026, 11, 20, 3, 0)

    # ------------------------------------------------------------ helpers
    def punch(self, code, local, device=None, **extra):
        """One ledger row from a local time string 'YYYY-MM-DD HH:MM[:SS]'."""
        if len(local) == 16:
            local += ':00'
        vals = {'device_id': (device or self.device).id, 'user_code': code,
                'punch_local': local, 'source': extra.pop('source', 'upload')}
        vals.update(extra)
        return self.Punch.create([vals])

    def run_pairing(self):
        return self.Pairing.run(company_ids=[self.company.id], now=self.now)

    def local(self, dt_utc):
        return pytz.UTC.localize(dt_utc).astimezone(self.tz).replace(tzinfo=None)

    def device_atts(self, employee):
        return self.Att.sudo().search([
            ('employee_id', '=', employee.id),
            ('pb_entry_source', '=', 'device')], order='check_in')

    def hours(self, att):
        return round((att.check_out - att.check_in).total_seconds() / 3600.0, 2)
