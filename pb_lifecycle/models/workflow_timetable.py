"""WF2 P5c (owner decision D31): the areas' own date timetables.

Contracts (end date), trial periods (end date) and employee documents (expiry)
already remind people on their own, on the lifecycle's daily job and the
document expiry job. Each area now declares that timetable in its contract
(`_workflow_effects(company)`, a `reminder` row with a `timing`: which date,
how many days before it, and whether it is switched on). Studio lists them
under "Already happens" (they are ordinary effect rows) and, here, warns before
a workflow that starts around the same date (the shipped "At a record date"
start, or a scheduled start for each record) tells, or gives a task to, the
same kind of person inside that window (`repeats_existing`, kept on purpose
with "Keep it, it is different"). Nothing about the reminders changes.

No local is called `user` or `uid` in a method that calls `_()` (ledger G12).
"""
from odoo import models, _

from . import workflow_definition as D

#: Days in one unit of the shipped date start's offset.
UNIT_DAYS = {'minutes': 1 / 1440.0, 'hour': 1 / 24.0, 'day': 1, 'month': 30}


def _lower_first(text):
    text = str(text or '').strip()
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


class WorkflowTimetable(models.AbstractModel):
    _inherit = 'pb.workflow.studio'

    def _timetables(self, model, company):
        """The area's date reminders for this record type (declared rows with
        a `timing`), static and configuration-dependent alike."""
        if not model or model not in self.env:
            return []
        rows = list(self._contract(model).get('effects') or [])
        obj = self.env[model]
        if hasattr(obj, '_workflow_effects'):
            rows += list(obj._workflow_effects(company) or [])
        return [dict(e) for e in rows if e.get('kind') == 'reminder' and isinstance(e.get('timing'), dict)
                and e['timing'].get('field')]

    def _starts_in_window(self, d, timing):
        """Whether this workflow starts inside the area's window before the
        date: a record-date start on the same date, no later than the date
        and no earlier than the area's first reminder; any scheduled start for
        each record (it lands on some day of the window)."""
        t = d.get('trigger') or {}
        if t.get('kind') == 'date':
            if t.get('date_field') != timing.get('field'):
                return False
            days = (t.get('delay') or 0) * UNIT_DAYS.get(t.get('unit', 'day'), 1)
            if t.get('mode', 'after') == 'after':
                return days < 1
            return days <= (timing.get('before_days') or 0)
        if t.get('kind') == 'schedule':
            return (t.get('schedule') or {}).get('starts', 'each_record') == 'each_record'
        return False

    def _step_audience(self, n):
        """Who a step tells or asks, in the timetables' words: manager,
        requester (the person it is about), hr (a named person, a
        responsibility or a team), or None when unknown (an email)."""
        if n['type'] == 'email':
            return n.get('audience') or None
        if n['type'] in D.PEOPLE or n['type'] == 'notify':
            owner = n.get('owner') or {}
            if owner.get('kind') in ('role', 'team', 'user'):
                return 'hr'
            return self._owner_audience(owner)
        return False

    def _repeat_warnings(self, w, d):
        out = super()._repeat_warnings(w, d)
        model = w.source_model
        if not model or (d.get('trigger') or {}).get('kind') not in ('date', 'schedule'):
            return out
        tables = [e for e in self._timetables(model, w.company_id)
                  if e['timing'].get('active', True) and self._starts_in_window(d, e['timing'])]
        if not tables:
            return out
        flagged = {i['id'] for i in out}
        for n in d['nodes']:
            if n['id'] in flagged:
                continue
            audience = self._step_audience(n)
            if audience is False:
                continue
            hit = next((e for e in tables if audience is None or e.get('audience') == audience), None)
            if not hit:
                continue
            out.append({'id': n['id'], 'code': 'repeats_existing', 'severity': 'warning',
                        'acknowledged': bool(n.get('ack_repeat')), 'existing': hit.get('text', ''),
                        'existing_source': 'area',
                        'text': _('%(owner)s already reminds people on its own timetable: %(text)s '
                                  'This step would remind them a second time.',
                                  owner=hit.get('owner') or _('This area'), text=_lower_first(hit.get('text')))})
        return out
