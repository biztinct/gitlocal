# -*- coding: utf-8 -*-
"""NEWHIRE P3b — `/my/welcome`'s data and its row on the My Payobook home
(handover §2.4). The page itself is `controllers/welcome.py`.

Everything reads `pb.new.hire.ask.summary` (the ONE reader, refreshed
first). The person sees only their own asks: the employee is always the
session's own (`_ess_employee`); no route takes an employee id.
"""
import logging

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

#: Each ask's picture on the page (names `pb_me_portal.ess_icon` draws).
ICONS = {
    'personal': 'user',
    'emergency': 'heart',
    'id_number': 'user-check',
    'bank': 'banknote',
    'tax_number': 'receipt',
    'tax_status': 'receipt',
    'tax_regime': 'receipt',
    'tax_fund': 'receipt',
}


class PbNewHireWelcomePage(models.AbstractModel):
    _name = 'pb.new.hire.welcome'
    _description = 'New hire studio: the welcome page of the new person'

    @api.model
    def _hint(self, row):
        """One plain line under each card: what to do on the page it opens."""
        key = row.key
        if row.state == 'done':
            return _("Done. Thank you.")
        if row.state == 'waiting':
            return _("You sent it. HR checks it before it is saved.")
        if key in ('personal', 'emergency'):
            return _("Type it on your profile and send it to HR.")
        if key == 'bank':
            return _("Add your account and a photo of a bank paper. A second person approves it.")
        if key.startswith('tax_'):
            return _("Type it and add a photo of the paper that shows it.")
        if row.url == '/my/documents' and row.category_id:
            # the one place the vault's own word is named: it is what the
            # upload page's list shows
            return _("Upload a scan or a photo and choose “%s” as the kind of paper.",
                     row.category_id.name or '')
        return _("Type it and add a photo of the paper.")

    @api.model
    def page(self, employee):
        """The page's values (or None: nothing was asked → the home)."""
        emp = employee.sudo()
        Ask = self.env['pb.new.hire.ask'].sudo()
        summary = Ask.summary(emp)
        if not summary['total']:
            return None
        rows = {r.key: r for r in Ask.search([('employee_id', '=', emp.id)])}
        day = self.env['pb.new.hire.invite']._first_day(emp)
        today = fields.Date.context_today(self)
        cards = []
        for item in summary['items']:
            row = rows.get(item['key'])
            cards.append(dict(item, icon=ICONS.get(item['key'], 'file-text'),
                              hint=self._hint(row) if row else '',
                              link=item['state'] != 'done' and bool(item['url'])))
        done = summary['done']
        total = summary['total']
        open_n = summary['open']
        minutes = max(2, round(open_n * 1.5)) if open_n else 0
        when = format_date(self.env, day, date_format='EEE d MMM') if day else ''
        started = bool(day and day <= today)
        if done == total:
            lead = _("That is everything. See you on %s.", when) if when and not started \
                else _("That is everything. Thank you.")
        elif not open_n:
            lead = _("You sent everything. HR checks each one before it is saved.")
        else:
            things = _("1 thing") if open_n == 1 else _("%s things", open_n)
            lead = _("%(things)s to finish before %(day)s. Each one takes a minute or two.",
                     things=things, day=when) if when and not started else \
                _("%s to finish. Each one takes a minute or two.", things)
        return {
            'first': (emp.name or '').split(' ')[0] or emp.name or '',
            'company': emp.company_id.name or '',
            'lead': lead,
            'day': when,
            'started': started,
            'cards': cards,
            'done': done, 'total': total, 'open': open_n, 'waiting': summary['waiting'],
            'all_done': done == total,
            'ring': int(round(done * 360.0 / total)) if total else 0,
            'minutes': minutes,
        }


class PbMeHomeNewHire(models.AbstractModel):
    """The home's "Needs you" row: back to `/my/welcome` while anything is
    open or waiting (pb_me_portal's own hook, never its files)."""
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        # this row FIRST: the hook chain runs in one savepoint and any sibling
        # that raises loses every row put after it (NH41); a row already put
        # survives because `put` only fills the caller's dict
        shown = False
        try:
            shown = self._pbnh_needs_row(emp, put)
        except Exception:                       # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_new_hire: the joining details row failed', exc_info=True)
        if shown and self._pbnh_asks_tax_number(emp):
            # P8 C: the joining details row already asks for the tax number, so
            # the tax area's own "Add your tax number" row would say it twice.
            # It comes back by itself once the joining row is gone.
            def put_once(key, *args, **kwargs):
                if key == 'tax_number_missing':
                    return None
                return put(key, *args, **kwargs)
            super()._pbme_needs_extra(emp, put_once)
            return
        super()._pbme_needs_extra(emp, put)

    @api.model
    def _pbnh_asks_tax_number(self, emp):
        """True while the person's joining details still include the tax
        number (asked and not done)."""
        try:
            return bool(self.env['pb.new.hire.ask'].sudo().search_count([
                ('employee_id', '=', emp.id), ('key', '=', 'tax_number'),
                ('state', '!=', 'done')], limit=1))
        except Exception:                       # noqa: BLE001
            return False

    @api.model
    def _pbnh_needs_row(self, emp, put):
        """Put the joining details row; True when it was put."""
        Ask = self.env['pb.new.hire.ask'].sudo()
        if not Ask.search_count([('employee_id', '=', emp.id), ('state', '!=', 'done')], limit=1):
            return False
        summary = Ask.summary(emp)
        open_n, waiting = summary['open'], summary['waiting']
        if open_n:
            put('nh_welcome', open_n, '/my/welcome',
                label=_("Finish your joining details"),
                sub=_("1 thing to finish") if open_n == 1 else _("%s things to finish", open_n),
                icon='list-checks', tone='indigo',
                sentence=_("A few joining details are still open."))
        elif waiting:
            put('nh_welcome', waiting, '/my/welcome',
                label=_("Your joining details"),
                sub=_("Sent. HR checks them before they are saved."),
                icon='list-checks', tone='slate',
                sentence=_("Your joining details are with HR."))
        return bool(open_n or waiting)
