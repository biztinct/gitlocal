import json

from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.pb_pay_builder.models.builder import amount

MONEY_GROUP = 'pb_hiring.group_hiring_user'


class Offer(models.Model):
    _inherit = 'pb.hiring.offer'

    pbpb_values = fields.Text(string='Agreed pay amounts', groups=MONEY_GROUP, readonly=True, copy=False)
    pbpb_net = fields.Monetary(string='Monthly take-home', groups=MONEY_GROUP, readonly=True, copy=False)
    pbpb_has_net = fields.Boolean(string='Has a take-home amount', groups=MONEY_GROUP, readonly=True, copy=False)
    pbpb_gross = fields.Monetary(string='Monthly gross pay', groups=MONEY_GROUP, readonly=True, copy=False)
    pbpb_letter_table = fields.Boolean(string='Show the pay table in the offer letter', default=True, groups=MONEY_GROUP)

    def _pbpb_letter(self, table):
        self.ensure_one()
        if not self.pbpb_values:
            return table
        gross = self._money(self.pbpb_gross)
        if not self.pbpb_letter_table:
            return Markup('<p>%s</p>') % _('Gross pay of %s a month.', gross)
        result = Markup('%s<p><strong>%s %s</strong></p>') % (table, _('Gross pay'), gross)
        if self.pbpb_has_net:
            result += Markup('<p>%s</p>') % _('Take-home after the usual deductions is about %s a month.', self._money(self.pbpb_net))
        return result

    def _lines_table(self):
        return self._pbpb_letter(super()._lines_table())


class OfferPayBuilder(models.AbstractModel):
    _inherit = 'pb.pay.builder'

    def _draft_offer(self, offer_id, lock=False):
        offer = self.env['pb.pay.package']._offer_get(offer_id)
        if lock:
            offer.lock_for_update()
            offer.invalidate_recordset()
        if offer.state != 'draft':
            raise UserError(_("This offer has been sent for sign-off, and the numbers are what somebody is agreeing to. Ask whoever it is waiting on to send it back, then change it and send it again."))
        return offer

    def _subject(self, home, ref):
        if home != 'offer':
            return super()._subject(home, ref)
        offer = self._draft_offer(ref.get('offer_id'))
        schemes = self.env['pb.pay.package']._offer_schemes(offer)
        selected = int(ref.get('scheme_id') or 0)
        cfg = schemes.filtered(lambda c: c.id == selected) if selected else (offer.pb_total_config_id & schemes) or schemes[:1]
        if selected and not cfg:
            raise UserError(_("This pay scheme is not available."))
        if cfg and cfg.currency_id != offer.currency_id:
            raise UserError(_("This offer is in %(offer)s but the pay scheme pays in %(scheme)s. Change the offer's money or pick another scheme.",
                              offer=offer.currency_id.name, scheme=cfg.currency_id.name))
        return {'offer': offer, 'config': cfg, 'currency': offer.currency_id, 'base': {}, 'existing': False,
                'day': offer.start_date or fields.Date.context_today(self), 'name': (offer.candidate_name or '').partition(' ')[0],
                'can_edit': True, 'can_open': self._can_open()}

    @api.model
    def offer_builder_open(self, offer_id):
        offer = self._draft_offer(offer_id)
        schemes = self.env['pb.pay.package']._offer_schemes(offer)
        selected = (offer.pb_total_config_id & schemes) or schemes[:1]
        values = json.loads(offer.pbpb_values or '{}') if selected == offer.pb_total_config_id else {}
        return {'schemes': [{'id': c.id, 'name': c.name} for c in schemes], 'scheme_id': selected.id,
                'values': values, 'letter_table': offer.pbpb_letter_table}

    @api.model
    def offer_builder_letter(self, offer_id, show):
        offer = self._draft_offer(offer_id, lock=True)
        offer.pbpb_letter_table = show is True
        return True

    @api.model
    def offer_builder_use(self, offer_id, scheme_id, values, letter_table=True):
        offer = self._draft_offer(offer_id, lock=True)
        subject = self._subject('offer', {'offer_id': offer.id, 'scheme_id': scheme_id})
        cfg = subject['config']
        if not cfg:
            raise UserError(_("Choose a pay scheme first."))
        answer = self._answer(subject, values)
        if answer['state'] != 'ok' or answer.get('has_failed') or answer['totals']['gross'] is None:
            raise UserError(_("These figures cannot be used on the offer."))
        allowed = set(answer['typed_codes']) | {'wage'}
        if not isinstance(values, dict) or any(code not in allowed or amount(value) is None for code, value in values.items()):
            raise UserError(_("Check the amounts and try again."))
        typed = {code: amount(value) for code, value in values.items()}
        typed.update({answer['head']['code']: answer['head']['value'], 'wage': answer['head']['monthly']})
        earning = next((s['lines'] for s in answer['sections'] if s['key'] == 'earn'), [])
        rows = [{'offer_id': offer.id, 'sequence': i, 'name': row['name'], 'kind': 'earning', 'period': 'monthly',
                 'amount': row['amount'], 'pb_item_code': row['code'], 'pb_from_total': True,
                 'pb_item_wage': row['kind'] == 'wage'} for i, row in enumerate(earning, 1) if (row['amount'] or 0) > 0]
        if not rows:
            raise UserError(_("This pay scheme has no monthly earnings to put on the offer."))
        offer.line_ids.filtered(lambda line: line.pb_from_total and line.period == 'monthly').unlink()
        self.env['pb.hiring.offer.line'].sudo().create(rows)
        offer.write({'pb_total_config_id': cfg.id, 'pb_total_note': False, 'pbpb_values': json.dumps(typed),
                     'pbpb_has_net': answer['totals']['net'] is not None, 'pbpb_net': answer['totals']['net'] or 0, 'pbpb_gross': answer['totals']['gross'],
                     'pbpb_letter_table': letter_table is True})
        return {'ok': True, 'lines': len(rows)}

    def _pbpb_offer_values(self, offer):
        if not offer.pbpb_values or not offer.pb_total_config_id:
            return {}
        return {'scheme': offer.pb_total_config_id, 'currency': offer.currency_id,
                'values': json.loads(offer.pbpb_values)}


class HiringOfferRow(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _offer_row(self, offer, full=False):
        row = super()._offer_row(offer, full=full)
        if full and not row.get('money_locked'):
            row['pbpb_letter_table'] = offer.sudo().pbpb_letter_table
            row['pbpb_has_values'] = bool(offer.sudo().pbpb_values)
        return row
