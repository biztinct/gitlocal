# -*- coding: utf-8 -*-

import difflib
import re

from odoo import api, fields, models


class HrPayrollCycleComponentMappingWizard(models.TransientModel):
    _name = 'hr.payroll.cycle.component.mapping.wizard'
    _description = 'Mid-Cycle to End-Cycle Mapping Wizard'

    mid_cycle_config_id = fields.Many2one(
        'hr.formula.config',
        string='Mid-Cycle Configuration',
        required=True,
        domain="[('cycle_type', '=', 'mid_cycle')]"
    )
    end_cycle_config_id = fields.Many2one(
        'hr.formula.config',
        string='End-Cycle Configuration',
        required=True,
        domain="[('cycle_type', '=', 'end_cycle')]"
    )
    # Computed (not stored) — suggestions are persistent and keyed by the config
    # pair, so we surface the ones matching this wizard's selected pair.
    suggestion_ids = fields.One2many(
        'hr.payroll.cycle.mapping.suggestion', compute='_compute_suggestion_ids', string='Suggestions')

    @api.depends('mid_cycle_config_id', 'end_cycle_config_id')
    def _compute_suggestion_ids(self):
        Sug = self.env['hr.payroll.cycle.mapping.suggestion']
        for w in self:
            if w.mid_cycle_config_id and w.end_cycle_config_id:
                w.suggestion_ids = Sug.search([
                    ('mid_cycle_config_id', '=', w.mid_cycle_config_id.id),
                    ('end_cycle_config_id', '=', w.end_cycle_config_id.id)])
            else:
                w.suggestion_ids = False

    # ---- Mid→End auto-suggest (T4.1) --------------------------------------
    @staticmethod
    def _norm_code(code):
        """Normalise a component code for fuzzy matching: strip a MID_/END_
        prefix, drop underscores/spaces, lowercase."""
        if not code:
            return ''
        c = code.strip()
        for pre in ('MID_', 'END_'):
            if c.upper().startswith(pre):
                c = c[len(pre):]
                break
        return re.sub(r'[_\s]', '', c).lower()

    def _best_end_match(self, mid, end_rules, used_end_ids):
        """Best end component for one mid component. Returns (end, confidence,
        reason) or None. Ladder: exact code (1.0) → normalized code (0.9) →
        difflib name ratio ≥ 0.75."""
        mcode = (mid.code or '').strip()
        mnorm = self._norm_code(mcode)
        mname = (mid.name or '').strip().lower()
        best = None
        for end in end_rules:
            if end.id in used_end_ids:
                continue                      # an end maps from at most one mid
            ecode = (end.code or '').strip()
            if mcode and ecode and mcode.upper() == ecode.upper():
                cand = (end, 1.0, 'Exact code match')
            elif mnorm and mnorm == self._norm_code(ecode):
                cand = (end, 0.9, 'Normalized code match')
            else:
                ename = (end.name or '').strip().lower()
                ratio = difflib.SequenceMatcher(None, mname, ename).ratio() if (mname and ename) else 0.0
                cand = (end, round(ratio, 3), 'Name similarity %d%%' % round(ratio * 100)) if ratio >= 0.75 else None
            if cand and (best is None or cand[1] > best[1]):
                best = cand
        return best

    def action_suggest_mappings(self):
        self.ensure_one()
        Sug = self.env['hr.payroll.cycle.mapping.suggestion']
        Mapping = self.env['hr.payroll.cycle.component.mapping']
        mid_cfg, end_cfg = self.mid_cycle_config_id, self.end_cycle_config_id

        # already-mapped components (both sides) are off the table
        existing = Mapping.search([('mid_cycle_config_id', '=', mid_cfg.id),
                                   ('end_cycle_config_id', '=', end_cfg.id)])
        mapped_mid_ids = set(existing.mapped('mid_component_id').ids)
        used_end_ids = set(existing.mapped('end_component_id').ids)

        # prior suggestions: keep accepted/rejected (persist decisions), refresh proposed
        prior = Sug.search([('mid_cycle_config_id', '=', mid_cfg.id),
                            ('end_cycle_config_id', '=', end_cfg.id)])
        kept = prior.filtered(lambda s: s.state in ('accepted', 'rejected'))
        (prior - kept).unlink()
        rejected_pairs = {(s.mid_component_id.id, s.end_component_id.id)
                          for s in kept if s.state == 'rejected'}
        mapped_mid_ids |= set(kept.filtered(lambda s: s.state == 'accepted').mapped('mid_component_id').ids)
        used_end_ids |= set(kept.filtered(lambda s: s.state == 'accepted').mapped('end_component_id').ids)

        end_rules = end_cfg.rule_ids
        vals_list = []
        for mid in mid_cfg.rule_ids:
            if mid.id in mapped_mid_ids:
                continue                          # already mapped → skip
            best = self._best_end_match(mid, end_rules, used_end_ids)
            if not best:
                continue
            end, conf, reason = best
            if (mid.id, end.id) in rejected_pairs:
                continue                          # user already rejected this pair
            used_end_ids.add(end.id)              # one suggestion per mid, one mid per end
            vals_list.append({
                'mid_cycle_config_id': mid_cfg.id, 'end_cycle_config_id': end_cfg.id,
                'mid_component_id': mid.id, 'end_component_id': end.id,
                'confidence': conf, 'match_reason': reason, 'state': 'proposed',
            })
        if vals_list:
            Sug.create(vals_list)
        return self._reopen()

    def action_accept_all(self, min_confidence=0.9):
        """Accept every proposed suggestion at or above the confidence floor —
        creates the real mappings (rejected/lower-confidence ones untouched)."""
        self.ensure_one()
        to_accept = self.suggestion_ids.filtered(
            lambda s: s.state == 'proposed' and s.confidence >= min_confidence)
        if to_accept:
            to_accept.action_accept()
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_open_mappings(self):
        self.ensure_one()
        action = self.env['ir.actions.actions'].sudo()._for_xml_id(
            'pb_hr_payroll_formula.action_payroll_cycle_component_mapping'
        )
        context = dict(self.env.context or {})
        context['default_mid_cycle_config_id'] = self.mid_cycle_config_id.id
        context['default_end_cycle_config_id'] = self.end_cycle_config_id.id
        context['search_default_mid_cycle_config_id'] = self.mid_cycle_config_id.id
        context['search_default_end_cycle_config_id'] = self.end_cycle_config_id.id
        action['context'] = context
        return action
