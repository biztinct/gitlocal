# -*- coding: utf-8 -*-
"""Ready-made kinds of leave per country (WDGAP S5-A, owner ruling L1).

The data is ``data/starters.json`` inside THIS module — never ``pb_pack_*``
(ledger D2) — read on demand. Nothing is created by installing the module.

Applying a country to a company creates its kinds SWITCHED OFF (archived) and
"waiting for review", each with the pay treatment written explicitly and the
source of every figure kept on the kind for the drawer. HR reviews each one
and switches it on. A kind is matched by ``pb_ls_starter_key`` per company
(``VN.annual``), archived ones included, so applying the same country twice
never makes a second copy. ``pb_policy_code`` and ``pb_policy_category`` are
never written (Rize-only meanings, and the code is globally unique).
"""
import json
import os

from odoo import _, api, models, tools
from odoo.exceptions import UserError

COUNTRIES = ('VN', 'ID', 'IN', 'SG', 'TH', 'KH', 'MY')
_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'starters.json')
_CACHE = {}


def load_starters():
    if 'data' not in _CACHE:
        with tools.file_open(_PATH, 'r') as fh:
            _CACHE['data'] = json.load(fh)
    return _CACHE['data']


def pick_lang(texts, lang):
    """The note in the reader's language, else English."""
    if not isinstance(texts, dict):
        return texts or ''
    short = (lang or 'en_US').split('_')[0]
    return texts.get(short) or texts.get('en') or ''


class PbLeaveStarters(models.AbstractModel):
    _name = 'pb.leave.starters'
    _description = 'Ready-made kinds of leave'

    @api.model
    def _country_kinds(self, code):
        code = (code or '').upper()
        if code not in COUNTRIES:
            raise UserError(_('Ready-made kinds are offered for Vietnam, Indonesia, India, '
                              'Singapore, Thailand, Cambodia and Malaysia.'))
        return load_starters()['countries'].get(code, {}).get('kinds', [])

    @api.model
    def _existing(self, code, company):
        Kind = self.env['hr.leave.type'].sudo().with_context(active_test=False)
        rows = Kind.search([('pb_ls_starter_key', '=like', code.upper() + '.%'),
                            ('company_id', '=', company.id)])
        return {r.pb_ls_starter_key: r for r in rows}

    @api.model
    def _summary(self, spec):
        """One plain line for the review list: what the kind gives."""
        bits = []
        if spec.get('counted'):
            days = spec.get('days') or 0
            if spec.get('earning') == 'monthly':
                bits.append(_('%s days a year, built up each month', '{:g}'.format(days)))
            elif spec.get('earning') == 'yearly':
                bits.append(_('%s days a year, all at once', '{:g}'.format(days)))
            if spec.get('waiting'):
                bits.append(_('after %s months of service', spec['waiting']))
            if spec.get('steps'):
                bits.append(_('more with long service'))
        else:
            bits.append(_('Not counted against an allowance'))
        treatment = (spec.get('pay') or ['unconfigured'])[0]
        bits.append({'paid': _('paid'), 'unpaid': _('unpaid'), 'partial': _('partly paid'),
                     'unconfigured': _('pay to decide')}.get(treatment, ''))
        return ' · '.join(b for b in bits if b)

    @api.model
    def _review_rows(self, code, company):
        lang = self.env.lang
        have = self._existing(code, company)
        rows = []
        for spec in self._country_kinds(code):
            key = '%s.%s' % (code.upper(), spec['key'])
            made = have.get(key)
            rows.append({
                'key': key,
                'name': pick_lang(spec.get('name'), lang),
                'summary': self._summary(spec),
                'sources': [pick_lang(v, lang) for v in (spec.get('sources') or {}).values()],
                'pay_open': (spec.get('pay') or ['unconfigured'])[0] == 'unconfigured',
                'made': bool(made),
                'made_id': made.id if made else 0,
                'made_on': bool(made and made.active),
            })
        return rows

    @api.model
    def _vals(self, code, company, spec):
        treatment, fraction, funding, employer = (spec.get('pay') or
                                                  ['unconfigured', 1, 'unconfigured', 0])
        country = self.env['res.country'].search([('code', '=', code.upper())], limit=1)
        names = spec.get('name') or {}
        vals = {
            'name': names.get('en') or spec['key'],
            'company_id': company.id,
            'country_id': country.id or False,
            'pb_policy_country_id': country.id or False,
            'active': False,                       # switched OFF until HR reviews it
            'pb_ls_review': True,
            'pb_ls_starter_key': '%s.%s' % (code.upper(), spec['key']),
            'pb_ls_starter_version': load_starters().get('version') or '',
            'pb_ls_sources': spec.get('sources') or {},
            'request_unit': spec.get('unit') or 'day',
            'requires_allocation': bool(spec.get('counted')),
            'pb_ls_earning': (spec.get('earning') or 'none') if spec.get('counted') else 'none',
            'pb_ls_days_per_year': float(spec.get('days') or 0.0),
            'pb_ls_waiting_months': int(spec.get('waiting') or 0),
            'pb_ls_max_balance': float(spec.get('max') or 0.0),
            'pb_ls_expire_months': int(spec.get('expire') or 0),
            'pb_ls_hr_only': bool(spec.get('hr_only')),
            'support_document': bool(spec.get('doc')),
            'pb_backdate_ok': bool(spec.get('backdate')),
            'unpaid': bool(spec.get('unpaid')),
            'pb_pay_treatment': treatment,
            'pb_paid_fraction': float(fraction),
            'pb_pay_funding': funding,
            'pb_employer_paid_fraction': float(employer),
            'pb_ls_step_ids': [(0, 0, {'after_years': int(y), 'extra_days': float(d)})
                               for y, d in (spec.get('steps') or [])],
        }
        return vals

    @api.model
    def _apply(self, code, company, keys=None):
        """Create the picked kinds (all when `keys` is None) that this company
        does not have yet. Returns ``{'created': [...ids], 'skipped': n}``."""
        code = code.upper()
        have = self._existing(code, company)
        # created in English; the vi/id names are written as translations below
        Kind = self.env['hr.leave.type'].sudo().with_context(active_test=False, lang='en_US')
        langs = {code_ for code_, _n in self.env['res.lang'].get_installed()}
        created, skipped = [], 0
        for spec in self._country_kinds(code):
            key = '%s.%s' % (code, spec['key'])
            if keys is not None and key not in keys:
                continue
            if key in have:
                skipped += 1
                continue
            kind = Kind.create(self._vals(code, company, spec))
            names = spec.get('name') or {}
            tr = {}
            if 'vi_VN' in langs and names.get('vi'):
                tr['vi_VN'] = names['vi']
            if 'id_ID' in langs and names.get('id'):
                tr['id_ID'] = names['id']
            if tr:
                # a translated field: the vi/id names go into the field's own
                # translations, not only a .po (LOOK: a translation fix is TWO)
                kind.update_field_translations('name', tr)
            created.append(kind.id)
        return {'created': created, 'skipped': skipped}
