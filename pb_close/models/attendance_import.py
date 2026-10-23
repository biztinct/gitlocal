# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Bulk import vs a locked day — rows are SKIPPED WITH A REASON, never written.

The hook is ``_prepare()``, the wizard's shared row resolver
(``pb_attendance_flow/wizards/attendance_import.py``:227), and it is the right
one for a reason worth writing down: ``validate()`` and ``commit()`` both call
it, so a lock error appended here appears in the DRY-RUN verdict table AND stops
the write, from one place. Hooking ``commit()`` instead would have let an
officer map, preview a clean-looking file, press Import and only then discover
that half of it was refused — the verdict table would have been lying.

The wizard's own contract does the rest for free: `commit()` skips every row
whose `errors` list is non-empty and reports it under `skipped` with the reason
string. So a locked day produces exactly what §3.2 asks for — flagged as
skipped, not written — with no change to the commit loop at all.

Note the import's day is already the file's LOCAL calendar date (`rec['date']`,
before `_to_utc` is applied), which is the same day the lock chips show.
"""

from odoo import _, api, models


class PbAttendanceImportWizard(models.TransientModel):
    _inherit = 'pb.attendance.import.wizard'

    @api.model
    def _prepare(self, file_b64, filename, mapping):
        prepared, truncated = super()._prepare(file_b64, filename, mapping)
        Lock = self.env['pb.wf.lock']
        if Lock._bypass():
            return prepared, truncated

        pairs = {(r['employee'].company_id.id, r['date'])
                 for r in prepared if r.get('employee') and r.get('date')}
        if not pairs:
            return prepared, truncated
        locked = Lock._locked_pairs([c for c, _d in pairs],
                                    [d for _c, d in pairs])
        if not locked:
            return prepared, truncated

        for r in prepared:
            emp, day = r.get('employee'), r.get('date')
            if emp and day and (emp.company_id.id, day) in locked:
                r['errors'].append(_(
                    "That day is closed for payroll (%s) — reopen it first",
                    day.strftime('%d %b %Y')))
        return prepared, truncated
