# -*- coding: utf-8 -*-
"""The contract side panel, page and board learn the administrator's fields.

Every seam is reached from OUTSIDE pb_contracts (FS_HOST_FACTS §B.2):

* `_cd_terms` — the Terms tab's groups. `super()` + one group per published
  open section, built from `pb.form.studio.render` (the ENGINE decides which
  fields this reader may see and which apply to the person's Country of Work;
  nothing here reads a custom value with a plain read). Because the panel's
  write whitelist (`_cd_writable_map`), its judgement, its preview and its
  save all read `_cd_terms`, saving follows with no second write path.
* `_cd_coerce_term` — a custom field is coerced by the engine's own rules
  (`_pbfs_coerce`: same sentences as everywhere the Form builder writes) and
  its "required" is the Form builder's, not the column's.
* `lookup_contract_m2o` — the picker may also search what a custom "Link to a
  record" field points at, with the READER's rights (the stock whitelist is a
  module constant and is never touched).
* `_cd_propose` — R9: a custom field waits for the approver exactly like the
  money terms do where a contract route is published. See the method.
* `get_contract_detail` — the contract page gets the same sections, look-only.
* `_pbf_spec` / `_pbf_groups` — choice, yes/no, link and date fields become
  filters on the Contracts board, in their own "Company details" group.
"""
import logging

from odoo import api, models

from odoo.addons.pb_contracts.models.contract_approval import CONTRACT_WRITE, MONEY_TERMS
from odoo.addons.pb_contracts.models.pb_contract_360 import _M2O_WHITELIST

from .form_studio_host import HOST, MODEL
from .hr_contract import is_custom, snap_value

_logger = logging.getLogger(__name__)

#: Form builder kind → the side panel's kind. `bool`, `longtext` and `file`
#: are new to the panel (drawn by the patched editor, static/src/js).
KIND = {
    'text': 'text', 'longtext': 'longtext', 'integer': 'integer', 'number': 'number',
    'money': 'money', 'bool': 'bool', 'date': 'date', 'select': 'select', 'm2o': 'm2o',
    'file': 'file', 'readonly': 'readonly',
}
#: The kinds the Contracts board can filter on (handover FS-3 item 5).
FILTER_KINDS = ('select', 'bool', 'm2o', 'date')
GROUP_KEY = 'company_details'


class PbContracts(models.AbstractModel):
    _inherit = 'pb.contracts'

    # ================================================================ read
    @api.model
    def _fs3_render(self, contract):
        """The engine's published sections for this contract, as THIS reader
        may see them. Empty on any failure: a custom field may never cost
        anybody their contract panel."""
        Studio = self.env['pb.form.studio']
        # The layout is the CONTRACT's company's (layouts are per company).
        # An approval is carried out by the system in the main company's
        # context, where the contract's own company's layout would not be
        # found and every custom field would be refused.
        company = contract.company_id
        if company and company != self.env.company and (
                self.env.su or company in self.env.user.company_ids):
            Studio = Studio.with_company(company)
        try:
            return Studio.render(HOST, contract.id)
        except Exception:                               # noqa: BLE001
            _logger.info('Form builder: contract %s could not be drawn', contract.id,
                         exc_info=True)
            return {}

    @api.model
    def _fs3_entry(self, f, can_write):
        kind = KIND.get(f.get('kind'), 'text')
        display = f.get('display')
        entry = {
            'name': f['name'],
            'label': f.get('label') or f['name'],
            'kind': kind,
            'value': f.get('value', False),
            'display': display if display not in (None, '') else '—',
            'required': bool(f.get('required')),
            'writable': bool(can_write and f.get('writable') and kind != 'readonly'),
            'hint': f.get('help') or False,
            'tone': None,
            'pbfs': True,
        }
        if kind == 'select':
            entry['options'] = list(f.get('options') or [])
        elif kind == 'm2o':
            entry['comodel'] = f.get('comodel') or False
            entry['value_label'] = display or ''
        elif kind == 'file':
            entry['url'] = f.get('url') or False
        return entry

    @api.model
    def _fs3_groups(self, contract, can_write):
        data = self._fs3_render(contract)
        out = []
        for sec in data.get('sections') or []:
            if sec.get('kind') != 'open' or not sec.get('fields'):
                continue
            out.append({
                'key': 'pbfs_%s' % sec.get('id'),
                'label': sec.get('title') or '',
                'icon': sec.get('icon') or 'sparkles',
                'pbfs': True,
                'fields': [self._fs3_entry(f, can_write) for f in sec['fields']],
            })
        return out

    @api.model
    def _cd_terms(self, contract, symbol, can_write, unmask):
        groups = super()._cd_terms(contract, symbol, can_write, unmask)
        return groups + self._fs3_groups(contract, can_write)

    # ======================================================== write: coerce
    @api.model
    def _cd_coerce_term(self, contract, entry, value):
        if not entry.get('pbfs'):
            return super()._cd_coerce_term(contract, entry, value)
        _ = self.env._
        field = contract._fields.get(entry['name'])
        if field is None:
            return None, _('That is not something this screen can change, so it was left alone.')
        if isinstance(value, dict):                     # a picker row
            value = value.get('id')
        stored, err = self.env['pb.form.studio']._pbfs_coerce(field, value)
        if err:
            return None, err
        empty = stored is False or stored is None or stored == ''
        if entry.get('required') and empty and field.type != 'boolean':
            return None, _('%s is required. Fill it in before saving.', entry['label'])
        return stored, None

    # ======================================================= write: picker
    @api.model
    def _fs3_link_comodels(self):
        """Comodels the reader's own custom "Link to a record" contract
        fields point at, limited to what the engine allows a link to name."""
        Studio = self.env['pb.form.studio']
        allowed = Studio._pbfs_link_targets()
        return {f['comodel'] for f in Studio.fields_for(MODEL, 'all')
                if f.get('type') == 'many2one' and f.get('comodel') in allowed}

    @api.model
    def lookup_contract_m2o(self, comodel, term='', limit=12):
        if comodel in _M2O_WHITELIST:
            return super().lookup_contract_m2o(comodel, term=term, limit=limit)
        self._cd_require_read()
        if comodel not in self._fs3_link_comodels() or comodel not in self.env:
            return []
        try:
            # The reader's OWN rights (never sudo): a custom link may point at
            # contacts or people, and the picker must not list what this
            # person could not open.
            records = self.env[comodel].search(
                [('display_name', 'ilike', term or '')], limit=min(int(limit or 12), 20))
        except Exception:                               # noqa: BLE001
            return []
        return [{'id': r.id, 'label': r.display_name or ''} for r in records]

    # ===================================================== write: approval
    @api.model
    def _cd_propose(self, contract, terms, components, note, term_vals, plan,
                    refusals=None):
        """R9 — a custom field follows the SAME approval as the other terms:
        where a contract route is published, the change waits for the
        approver (handover FS-3 test 2).

        The stock method only holds `MONEY_TERMS` (a module constant). When
        no custom field is in the press, this is `super()` untouched — every
        existing save behaves exactly as before. When one is, the same body
        runs with the held set widened to the custom fields that passed the
        judgement; the snapshot holds them in a comparable shape
        (`snap_value`), and the approver's rows name them in words
        (`pb.contract.proposal._proposal_rows`, contract_proposal.py).
        Merge-time task: a `_cd_held_terms()` hook in pb_contracts would let
        this be a three-line override (FS3_REPORT §Merge-time tasks).
        """
        custom = [k for k in (term_vals or {}) if is_custom(k)]
        if not custom or self.env.context.get(CONTRACT_WRITE) \
                or 'pb.contract.proposal' not in self.env:
            return super()._cd_propose(contract, terms, components, note, term_vals,
                                       plan, refusals)
        _ = self.env._
        money = [k for k in (term_vals or {}) if k in MONEY_TERMS]
        components_changed = (len(plan.get('edits') or []) + len(plan.get('adds') or [])
                              + len(plan.get('removes') or []))
        shown = [{'label': (edit['line'].advantage_template_id.name if edit.get('line') else ''),
                  'old': edit.get('old_amount'), 'new': edit.get('new_amount')}
                 for edit in (plan.get('edits') or [])[:20]]
        held_terms = {k: v for k, v in (terms or {}).items() if k in MONEY_TERMS}
        # Only the custom values the judgement accepted: a refused one is
        # already on its way back to the panel with its sentence.
        held_terms.update({k: (terms or {}).get(k) for k in custom})
        snapshot = {key: contract[key] for key in sorted(held_terms)
                    if key in contract._fields and not is_custom(key)}
        snapshot.update({key: snap_value(contract, key) for key in custom})
        answer = self.env['pb.contract.proposal'].propose(
            'terms',
            _("Contract change · %s", contract.employee_id.name or ''),
            payload={'contract_id': contract.id, 'terms': held_terms,
                     'components': components or [], 'note': note or '',
                     'shown': shown},
            snapshot=snapshot,
            facts={'wage': {'value': float(term_vals.get('wage') or contract.wage or 0.0),
                            'unit': (contract.company_id or self.env.company).currency_id.name
                            or ''},
                   'touches_pay': {'value': bool(money), 'unit': ''},
                   'components': {'value': components_changed, 'unit': ''}},
            target=contract,
            subject_uids=contract.employee_id.user_id.ids,
            note=note,
            amount=float(term_vals.get('wage') or contract.wage or 0.0),
        ).answer()
        plain = {k: v for k, v in (term_vals or {}).items()
                 if k not in MONEY_TERMS and not is_custom(k)}
        written = 0
        refusals = list(refusals or [])
        if plain:
            try:
                with self.env.cr.savepoint():
                    contract.write(plain)
                written = len(plain)
            except Exception as error:                  # noqa: BLE001
                _logger.exception("Contract panel: plain-term write refused on %s",
                                  contract.id)
                reason = self._cd_reason(error)
                refusals += [{'scope': 'term', 'key': name, 'why': reason} for name in plain]
        if answer.get('applied'):
            result = answer.get('result') or {}
            refusals += list(result.get('refusals') or [])
            saved = int(result.get('saved') or 0) + written
            contract.invalidate_recordset()
            return {'ok': True, 'saved': saved, 'refusals': refusals,
                    'msg': self._cd_msg(saved, len(refusals)),
                    'detail': self._cd_payload(contract)}
        return {'ok': True, 'saved': written, 'refusals': refusals, 'pending': True,
                'reference': answer.get('reference'), 'request_id': answer.get('request_id'),
                'msg': answer.get('message') or '', 'detail': self._cd_payload(contract)}

    # ========================================================= full page
    @api.model
    def get_contract_detail(self, contract_id):
        out = super().get_contract_detail(contract_id)
        if not isinstance(out, dict) or out.get('error'):
            return out
        contract = self.env['hr.contract'].browse(int(contract_id))
        data = self._fs3_render(contract)
        # A new key: nothing the page already reads is disturbed.
        out['pbfs'] = {'sections': [s for s in data.get('sections') or []
                                    if s.get('kind') == 'open' and s.get('fields')],
                       'version': data.get('version') or 0}
        return out

    # =========================================================== filters
    @api.model
    def _pbf_groups(self):
        groups = super()._pbf_groups()
        if not any(g.get('key') == GROUP_KEY for g in groups):
            groups = groups + [{'key': GROUP_KEY, 'label': self.env._('Company details')}]
        return groups

    @api.model
    def _fs3_filter_spec(self):
        _ = self.env._
        out = []
        # `fields_for` answers with the reader's own rights: a field they may
        # not see is never offered (and `_pbf_resolve` re-checks the path).
        for f in self.env['pb.form.studio'].fields_for(MODEL, 'all'):
            kind = f.get('kind')
            if kind not in FILTER_KINDS:
                continue
            base = {'key': f['name'], 'label': f['label'], 'group': GROUP_KEY,
                    'help': f.get('help') or False}
            if kind == 'select':
                out.append(dict(base, icon='list', type='selection', path=f['name'],
                                none_label=_('Not filled in')))
            elif kind == 'm2o':
                out.append(dict(base, icon='link', type='many2one', path=f['name'],
                                none_label=_('Not filled in')))
            elif kind == 'date':
                out.append(dict(base, icon='calendar', type='date', path=f['name'],
                                presets='past', none_label=_('Not filled in')))
            elif kind == 'bool':
                out.append(dict(base, icon='checkCircle', type='choice', requires=[f['name']],
                                options=[
                                    {'value': 'yes', 'label': _('Yes'), 'tone': 'green',
                                     'domain': [(f['name'], '=', True)]},
                                    {'value': 'no', 'label': _('No'), 'tone': 'slate',
                                     'domain': [(f['name'], '!=', True)]},
                                ]))
        return out

    def _pbf_spec(self):
        spec = super()._pbf_spec()
        try:
            return spec + self._fs3_filter_spec()
        except Exception:                               # noqa: BLE001
            _logger.info('Form builder: contract filters skipped', exc_info=True)
            return spec
