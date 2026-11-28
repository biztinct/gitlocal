from odoo import _, fields, models
from odoo.exceptions import AccessError
from odoo.tools import format_amount

# Only the controller which verified the joining session can supply this object.
_JOINING_PAY = object()


class JoiningPay(models.AbstractModel):
    _inherit = 'pb.pay.builder'

    def _subject(self, home, ref):
        if home != 'joining':
            return super()._subject(home, ref)
        if ref.get('proof') is not _JOINING_PAY:
            raise AccessError(_('You can look at this person but not at their pay.'))
        joining = ref['joining']
        if not (joining.state == 'added' or joining.proposal_id.state == 'applied'):
            return {}
        settings = self.env['pb.pay.settings'].sudo().search([('company_id', '=', joining.company_id.id)], limit=1)
        if settings and not settings.portal_enabled:
            return {}
        day = max(joining.first_day, joining._today())
        person = joining.employee_id
        if person and person.company_id == joining.company_id:
            contract = self.env['hr.contract'].sudo().search([
                ('employee_id', '=', person.id), ('company_id', '=', joining.company_id.id),
                ('state', '=', 'open'), ('date_start', '<=', day),
                '|', ('date_end', '=', False), ('date_end', '>=', day)],
                order='date_start desc, id desc', limit=1)
            if not contract:
                if joining.proposal_id.state == 'applied':
                    approved_id = joining.proposal_id.result().get('contract_id')
                    contract = self.env['hr.contract'].sudo().search([
                        ('id', '=', approved_id or 0), ('employee_id', '=', person.id),
                        ('company_id', '=', joining.company_id.id), ('state', '=', 'draft')], limit=1)
                if not contract and joining.offer_id.state in ('signed', 'joined'):
                    agreed = joining.offer_id.contract_id
                    if agreed.state == 'draft' and agreed.employee_id == person and agreed.company_id == joining.company_id:
                        contract = agreed
            if contract:
                return self._contract_subject(contract, day)
        offer = joining.offer_id
        if offer and offer.company_id == joining.company_id and offer.state in ('signed', 'joined'):
            saved = self._pbpb_offer_values(offer)
            if saved and saved['scheme'].currency_id == saved['currency'] and (
                    not saved['scheme'].company_id or saved['scheme'].company_id == joining.company_id):
                return {'config': saved['scheme'], 'currency': saved['currency'], 'base': {}, 'values': saved['values'],
                        'existing': False, 'day': day, 'name': joining._first(), 'can_edit': False, 'can_open': False}
        return {}

    def _joining_card(self, joining, proof):
        subject = self._subject('joining', {'joining': joining, 'proof': proof})
        if not subject or not subject['config']:
            return None
        cfg = subject['config']
        layout = cfg._pbpb_layout()
        codes = [r['code'] for r in layout['rows'] if r['section'] in ('earn', 'ded') and r['kind'] in ('calc', 'wage')]
        answer = self._answer(subject, subject.get('values', {}), open_codes=codes)
        if answer['state'] != 'ok':
            return None

        def money(value):
            return format_amount(self.env, value, subject['currency']) if value is not None else '—'

        def chips(parts):
            out = []
            for part in parts:
                if part['t'] == 'range':
                    out.extend(chips(part['members']))
                elif part['t'] == 'ref':
                    out.append(_('%(name)s %(value)s', name=part['name'], value=part.get('text') or money(part['amount'])))
                elif part['t'] == 'fix':
                    out.append(_('%(name)s %(value)s', name=part['name'], value=part['text']))
                else:
                    out.append(part.get('text', ''))
            return out

        sections = []
        for group in answer['sections']:
            if group['key'] not in ('earn', 'ded'):
                continue
            rows = []
            for line in group['lines']:
                if line['in_bar'] or (line['kind'] == 'calc' and line['zero']):
                    continue
                exp = answer['explains'].get(line['code']) or {}
                rows.append({'name': line['name'], 'amount': money(line['amount']),
                             'icon': 'calculator' if exp else 'calendar' if line['kind'] == 'each' else 'pencil',
                             'hint': _('Tap to see how') if exp else _('Changes each month') if line['kind'] == 'each' else _('As agreed'),
                             'sentence': exp.get('sentence') or exp.get('failed_words') or '',
                             'chips': chips(exp.get('parts', [])), 'expand': bool(exp)})
            if rows:
                sections.append({'label': _('Earnings') if group['key'] == 'earn' else _('Deductions'),
                                 'rows': rows, 'total': money(group['total']), 'total_name': group['total_name']})
        if not sections:
            return None
        return {'sections': sections, 'net': money(answer['totals']['net']), 'net_label': _('Take-home'),
                'title': _('Your pay'), 'intro': _('A full month, as agreed. Tap a line to see how it is worked out.'),
                'note': _('A full month, with each-month lines at their usual amount.')}
