# -*- coding: utf-8 -*-
"""LEARNREV P4 — a walkthrough's Try, checked against what the person did.

`learn.scenario.check(key, step_key, args)` answers ONE question about the demo
world: has the person on the other end of this walkthrough step actually done
what it asked — on the real screen, in their own records? It generalises the
live capstone's predicates (`learn_live.py`), and it keeps every promise they
make:

  * READ-ONLY. Every check is a search or a read. Nothing here writes, and
    `contract.json::live-surfaces-are-read-only` style review covers it: the
    person presses the product's own buttons, and this looks.
  * AS THE PERSON. No elevation anywhere in this file — a check can never see
    further than the screen in front of the person.
  * GATED ON THE SERVER. Only a demo-world session (the demo group, working in
    the demo company — `learn_live._live_gate`) is ever checked; anyone else
    gets the refusal as a sentence, never a silent False.
  * THEIR OWN WORK ONLY. A check counts a change only when THIS user made it
    (`write_uid` / `create_uid`), so a prospect is never congratulated for a
    record somebody else touched.

WHERE CHECKS ARE DECLARED
-------------------------
A screen manifest may declare `checks: {"<scenario>.<step>": "<model>.<method>"}`
(the treatment manifest does, for its own board). Checks over the demo
world's pay run and Records Desk reuse pb_learn's own predicates and are
declared here (`BUILTIN_CHECKS`). The method is called as
`method(scenario_key, step_key, args)` and returns `{ok, note: {en, vi}}`.
A key that maps to nothing is said as such ("not verified"), never a pass.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .learn_live import _live_gate, _note

_logger = logging.getLogger(__name__)

#: Checks over pb_learn's own demo-world predicates. Manifests may add more.
BUILTIN_CHECKS = {
    'sc_payrun.compute': 'learn.scenario._check_run_computed',
    'sc_payrun.next': 'learn.scenario._check_run_submitted',
    'sc_records.review': 'learn.scenario._check_records_bank',
}


def _pair(en, vi):
    return {'en': en, 'vi': vi}


class LearnScenario(models.AbstractModel):
    """`learn.scenario` — read-only checks for a walkthrough's Try."""
    _name = 'learn.scenario'
    _description = 'Learn walkthrough checks'

    # ------------------------------------------------------------ the table
    @api.model
    def _checks(self):
        """{"<scenario>.<step>": "<model>.<method>"}: the manifests' own,
        then pb_learn's built-ins (a manifest cannot shadow one)."""
        out = {}
        for man in self.env['learn.guide']._manifests().values():
            for k, v in (man.get('checks') or {}).items():
                if isinstance(k, str) and isinstance(v, str):
                    out[k] = v
        out.update(BUILTIN_CHECKS)
        return out

    @api.model
    def checked_steps(self):
        """{scenario key: [step keys]} that Try checks on the real screen —
        EMPTY outside a demo-world session, so the client simply plays Try
        on the practice copy as before."""
        if _live_gate(self.env) is not None:
            return {}
        out = {}
        for ref in sorted(self._checks()):
            key, _dot, step = ref.partition('.')
            if key and step:
                out.setdefault(key, []).append(step)
        return out

    # ------------------------------------------------------------ the call
    @api.model
    def check(self, key, step_key, args=None):
        """Has the person done what this step asked? `{ok, note{en,vi}}`."""
        refused = _live_gate(self.env)
        if refused:
            return refused
        ref = self._checks().get('%s.%s' % (key or '', step_key or ''))
        if not ref:
            return {'ok': False, 'note': _note(self.env, 'notVerified', step=step_key or '')}
        model, _dot, method = ref.rpartition('.')
        if model not in self.env or not hasattr(self.env[model], method):
            return {'ok': False, 'note': _note(self.env, 'noSuchCheck', key=ref)}
        try:
            # A savepoint: a check that fails half-way must not poison the
            # request (the right-now providers' rule, learn_guide.py).
            with self.env.cr.savepoint():
                res = getattr(self.env[model], method)(key, step_key, dict(args or {}))
        except AccessError:
            return {'ok': False, 'note': _note(self.env, 'checkNoAccess')}
        except Exception:                                     # noqa: BLE001
            _logger.exception("pb_learn: walkthrough check %s failed", ref)
            return {'ok': False, 'note': _note(self.env, 'checkFailed')}
        res = res or {}
        note = res.get('note') or {}
        if isinstance(note, str):
            note = {'en': note, 'vi': note}
        return {'ok': bool(res.get('ok')), 'note': {'en': note.get('en') or '',
                                                    'vi': note.get('vi') or note.get('en') or ''}}

    # ------------------------------------------------------------ built-ins
    @api.model
    def _check_run_computed(self, key, step_key, args):
        """sc_payrun · Compute: the person's own June run has payslips."""
        return self.env['learn.live'].check('june_run_computed')

    @api.model
    def _check_run_submitted(self, key, step_key, args):
        """sc_payrun · Submit: the person's own June run left Draft."""
        return self.env['learn.live'].check('june_run_submitted')

    @api.model
    def _check_records_bank(self, key, step_key, args):
        """sc_records · Review → Apply: a bank detail of one DEMO employee,
        changed through the Records Desk by THIS user (since `args.since`,
        when the client sends the moment the step began)."""
        if 'pb.records.change' not in self.env or 'is_demo' not in self.env['hr.employee']._fields:
            return {'ok': False, 'note': _note(self.env, 'checkUnavailable')}
        domain = [('create_uid', '=', self.env.uid),
                  ('field_key', '=like', 'b:%'),
                  ('apply_id.undone', '=', False),
                  ('employee_id.is_demo', '=', True)]
        since = args.get('since')
        if since:
            try:
                domain.append(('create_date', '>=', fields.Datetime.to_datetime(since)))
            except (TypeError, ValueError):
                pass
        change = self.env['pb.records.change'].search(domain, order='id desc', limit=1)
        if not change:
            return {'ok': False, 'note': _note(self.env, 'recordsWaiting')}
        return {'ok': True, 'note': _note(
            self.env, 'recordsDone', person=change.employee_name or change.employee_id.name or '',
            field=change.field_label or '')}
