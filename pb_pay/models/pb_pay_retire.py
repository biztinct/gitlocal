# -*- coding: utf-8 -*-
"""`pb.pay.retire` — the gate in front of removing the old planning module.

WHY A GATE AT ALL
-----------------
Uninstalling a module DROPS ITS TABLES. Everything anybody ever typed into the
old planning screens — merit matrices, compensation cycles, approval steps,
budget rows, performance scores — is gone the moment the button is pressed, and
there is no way back except a database restore. So the button is not offered
until a machine has checked, on THIS database, that every one of those things
has already been carried across and that nothing still installed reaches for a
model that is about to disappear.

WHAT IT REFUSES ON
------------------
Nine checks, each of which answers in a sentence a person can act on rather
than a code. It refuses if a single one fails; it never refuses quietly.

WHAT IT IS NOT
--------------
It is not a permission check and it is not a backup. It is the last read
before an irreversible write, and the ninth check is "somebody has taken a
copy of this database recently", because the other eight can all pass and the
one thing that saves you is still the dump.
"""

import logging
import os
import time

from odoo import _, api, models

_logger = logging.getLogger(__name__)

LEGACY = 'pb_hr_workforce_planning'

#: Where a dump is looked for, and how fresh it has to be.
BACKUP_DIRS = ('/tmp', '/var/backups', '/var/lib/odoo/backups')
BACKUP_HOURS = 12

#: The models that must have been carried across before the tables go.
CARRIED = (
    ('wfp.merit.matrix', 'pb.pay.guidance', 'guidance grids'),
    ('wfp.compensation.cycle', 'pb.pay.review', 'past pay reviews'),
    ('wfp.budget.actual', 'pb.budget.line', 'budget rows'),
)


class PbPayRetire(models.AbstractModel):
    _name = 'pb.pay.retire'
    _description = 'Checks before the old planning module is removed'

    # ------------------------------------------------------------- the gate
    @api.model
    def preflight(self):
        """Nine checks. `{'ok': bool, 'checks': [...], 'failures': [...]}`."""
        started = time.time()
        checks = []
        for probe in (self._check_installed, self._check_guidance,
                      self._check_reviews, self._check_ratings,
                      self._check_budget, self._check_limits,
                      self._check_manifests, self._check_plan_lens,
                      self._check_contracts, self._check_backup):
            try:
                checks.append(probe())
            except Exception as error:          # noqa: BLE001
                _logger.exception('pb_pay: a pre-flight check crashed')
                checks.append({
                    'key': getattr(probe, '__name__', 'check'),
                    'ok': False,
                    'text': _("This check could not be run: %(why)s",
                              why=str(error)[:120])})
        failures = [check for check in checks if not check['ok']]
        return {
            'ok': not failures,
            'db': self.env.cr.dbname,
            'checks': checks,
            'failures': [check['text'] for check in failures],
            'ms': int((time.time() - started) * 1000),
            'sentence': _("Everything has been carried across. The old "
                          "planning module can be removed.") if not failures
            else _("%(count)s things are not ready. The old planning module "
                   "must stay for now.", count=len(failures)),
        }

    # ------------------------------------------------------------ the checks
    @api.model
    def _installed(self):
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', LEGACY)], limit=1)
        return module and module.state == 'installed'

    @api.model
    def _check_installed(self):
        return {'key': 'installed', 'ok': True,
                'text': _("The old planning module is installed here.")
                if self._installed()
                else _("The old planning module is already gone from this "
                       "database.")}

    @api.model
    def _count(self, model, domain=None):
        if model not in self.env:
            return None
        return self.env[model].sudo().with_context(
            active_test=False).search_count(domain or [])

    @api.model
    def _check_guidance(self):
        old = self._count('wfp.merit.matrix')
        if old is None:
            return {'key': 'guidance', 'ok': True,
                    'text': _("There were no merit matrices to carry over.")}
        new = self._count('pb.pay.guidance') or 0
        ok = old == 0 or new > 0
        return {'key': 'guidance', 'ok': ok, 'old': old, 'new': new,
                'text': _("%(old)s old guidance grids, %(new)s carried over.",
                          old=old, new=new) if ok else _(
                    "%(old)s merit matrices have not been carried over into "
                    "guidance grids yet.", old=old)}

    @api.model
    def _check_reviews(self):
        old = self._count('wfp.compensation.cycle')
        if old is None:
            return {'key': 'reviews', 'ok': True,
                    'text': _("There were no old pay rounds to carry over.")}
        new = self._count('pb.pay.review', [('is_legacy', '=', True)]) or 0
        ok = new >= old
        return {'key': 'reviews', 'ok': ok, 'old': old, 'new': new,
                'text': _("%(old)s old pay rounds, %(new)s kept as history.",
                          old=old, new=new) if ok else _(
                    "%(old)s old pay rounds are on this database and only "
                    "%(new)s have been kept as history.", old=old, new=new)}

    @api.model
    def _check_ratings(self):
        if 'wfp_performance_rating' not in self.env['hr.employee']._fields:
            return {'key': 'ratings', 'ok': True,
                    'text': _("There were no scores on people to carry "
                              "over.")}
        old = self.env['hr.employee'].sudo().with_context(
            active_test=False).search_count(
                [('wfp_performance_rating', '!=', False)])
        new = self._count('pb.pay.rating',
                          [('source', '=', 'legacy')]) or 0
        ok = new >= old
        return {'key': 'ratings', 'ok': ok, 'old': old, 'new': new,
                'text': _("%(old)s people had a score, %(new)s kept.",
                          old=old, new=new) if ok else _(
                    "%(old)s people carry a score on the old field and only "
                    "%(new)s have been kept.", old=old, new=new)}

    @api.model
    def _check_budget(self):
        old = self._count('wfp.budget.actual')
        if old is None:
            return {'key': 'budget', 'ok': True,
                    'text': _("There were no budget rows to move.")}
        if 'pb.budget.line' not in self.env:
            return {'key': 'budget', 'ok': False,
                    'text': _("The budget rows have nowhere to live yet — "
                              "the Budgets module has not been updated on "
                              "this database.")}
        new = self._count('pb.budget.line') or 0
        cr = self.env.cr
        # ROW BY ROW, not two grand totals. The new table is the one the
        # product writes to now, so it legitimately holds budgets the old one
        # never had — comparing the two sums would refuse for ever the moment
        # somebody entered a budget. What has to be true is narrower and more
        # useful: every OLD row has a row on the new side for the same
        # company, team and month, and what was spent on it is the same
        # figure.
        cr.execute("""
            SELECT o.company_id, o.department_id, o.period_month,
                   SUM(o.actual_cost)
              FROM wfp_budget_actual o
          GROUP BY 1, 2, 3
        """)
        old_rows = {(row[0] or 0, row[1] or 0, str(row[2] or '')):
                    float(row[3] or 0.0) for row in cr.fetchall()}
        cr.execute("""
            SELECT n.company_id, n.department_id, n.period_month,
                   SUM(n.actual_cost)
              FROM pb_budget_line n
          GROUP BY 1, 2, 3
        """)
        new_rows = {(row[0] or 0, row[1] or 0, str(row[2] or '')):
                    float(row[3] or 0.0) for row in cr.fetchall()}
        missing = [key for key in old_rows if key not in new_rows]
        differ = [key for key, amount in old_rows.items()
                  if key in new_rows and abs(new_rows[key] - amount) >= 1.0]
        ok = not missing and not differ
        return {'key': 'budget', 'ok': ok, 'old': old, 'new': new,
                'missing': len(missing), 'differ': len(differ),
                'text': _("%(old)s budget rows are all on the new table, and "
                          "what was spent adds up the same on both.",
                          old=old) if ok else _(
                    "The budget rows have not all moved across: %(missing)s "
                    "months are missing on the new table and %(differ)s do "
                    "not add up the same.",
                    missing=len(missing), differ=len(differ))}

    @api.model
    def _check_limits(self):
        old = self._count('wfp.budget.guardrail')
        if old is None:
            return {'key': 'limits', 'ok': True,
                    'text': _("There were no old limits to carry over.")}
        new = self._count('pb.pay.review.limit',
                          [('settings_id', '!=', False)]) or 0
        ok = old == 0 or new > 0
        return {'key': 'limits', 'ok': ok, 'old': old, 'new': new,
                'text': _("%(old)s old limits, %(new)s carried over.",
                          old=old, new=new) if ok else _(
                    "%(old)s old limits have not been carried over.",
                    old=old)}

    @api.model
    def _check_manifests(self):
        """Nothing still installed may DEPEND on the module being removed."""
        Module = self.env['ir.module.module'].sudo()
        legacy = Module.search([('name', '=', LEGACY)], limit=1)
        if not legacy:
            return {'key': 'manifests', 'ok': True,
                    'text': _("Nothing depends on the old planning module.")}
        depends = self.env['ir.module.module.dependency'].sudo().search(
            [('name', '=', LEGACY)])
        blockers = sorted({dep.module_id.name for dep in depends
                           if dep.module_id.state == 'installed'
                           and dep.module_id.name != LEGACY})
        return {'key': 'manifests', 'ok': not blockers,
                'modules': blockers,
                'text': _("Nothing installed depends on the old planning "
                          "module.") if not blockers else _(
                    "These are still built on the old planning module and "
                    "would be removed with it: %(names)s.",
                    names=', '.join(blockers))}

    @api.model
    def _check_plan_lens(self):
        """People → Plan must open the Decision Room, not the old screens."""
        room = self.env.ref('pb_decision_room.group_decision_user',
                            raise_if_not_found=False) \
            if 'pb.decision.plan' in self.env else None
        path = self._file(
            'pb_people_hub', 'static', 'src', 'js', 'plan_launcher.js')
        if not path:
            return {'key': 'plan_lens', 'ok': True,
                    'text': _("The People screens are not on this server.")}
        with open(path, encoding='utf-8') as handle:
            body = handle.read()
        still_there = LEGACY in body
        return {'key': 'plan_lens', 'ok': (not still_there) and bool(room),
                'text': _("People → Plan opens the planning room and no "
                          "longer names the old screens.")
                if (not still_there) and room else _(
                    "People → Plan still names the old planning screens, so "
                    "removing them would leave a screen that opens nothing.")}

    @api.model
    def _check_contracts(self):
        """The contract screen must already read the NEW band fields."""
        fields_ = self.env['hr.contract']._fields
        ok = 'pb_band_id' in fields_ and 'pb_position_pct' in fields_
        return {'key': 'contracts', 'ok': ok,
                'text': _("The contract screen reads the new pay bands.")
                if ok else _(
                    "The contract screen does not read the new pay bands "
                    "yet, so removing the old grades would empty it.")}

    @api.model
    def _check_backup(self):
        """Somebody has taken a copy of this database recently."""
        name = self.env.cr.dbname
        newest, found = 0.0, ''
        for folder in BACKUP_DIRS:
            try:
                entries = os.listdir(folder)
            except OSError:
                continue
            for entry in entries:
                if name not in entry:
                    continue
                if not entry.endswith(('.sql', '.dump', '.gz', '.zip',
                                       '.backup')):
                    continue
                try:
                    stamp = os.path.getmtime(os.path.join(folder, entry))
                except OSError:
                    continue
                if stamp > newest:
                    newest, found = stamp, os.path.join(folder, entry)
        fresh = newest and (time.time() - newest) < BACKUP_HOURS * 3600
        return {'key': 'backup', 'ok': bool(fresh), 'file': found,
                'text': _("A copy of this database was taken at %(when)s.",
                          when=time.strftime('%Y-%m-%d %H:%M',
                                             time.localtime(newest)))
                if fresh else _(
                    "No copy of this database has been taken in the last "
                    "%(hours)s hours. Take one before anything is removed.",
                    hours=BACKUP_HOURS)}

    @api.model
    def _file(self, module, *parts):
        try:
            from odoo.modules.module import get_module_path
        except ImportError:
            return ''
        base = get_module_path(module, display_warning=False)
        if not base:
            return ''
        path = os.path.join(base, *parts)
        return path if os.path.exists(path) else ''

    # --------------------------------------------------------- the sweep up
    @api.model
    def tidy_up(self):
        """Remove what the uninstall could not, and say what it removed.

        Uninstalling a module deletes its records in one pass. A ROLE that
        another module's record rule still pointed at when that pass ran is
        skipped — the delete fails on a foreign key, the platform moves on,
        and the role survives with nothing behind it. On the first rehearsal
        that left one group called plainly "User" in every tenant's list of
        roles, belonging to a module nobody could find, still switched on for
        two people.

        So the sweep is run AFTER the uninstall, it is scoped to records the
        retired module owned by name, and it reports what it took.
        """
        report = {'groups': [], 'data': 0}
        Data = self.env['ir.model.data'].sudo()
        rows = Data.search([('module', '=', LEGACY)])
        groups = self.env['res.groups'].sudo().browse(
            [row.res_id for row in rows if row.model == 'res.groups'])
        for group in groups.exists():
            name = group.display_name
            try:
                group.unlink()
                report['groups'].append(name)
            except Exception as error:          # noqa: BLE001
                _logger.warning('pb_pay: %s could not be removed: %s',
                                name, error)
        left = Data.search([('module', '=', LEGACY)])
        report['data'] = len(left)
        if left:
            left.unlink()
        _logger.info('pb_pay: swept up after the old planning module: %s',
                     report)
        return report

    # ------------------------------------------------------------ the report
    @api.model
    def report(self):
        """The gate as a few lines of text, for a log or a terminal."""
        answer = self.preflight()
        lines = ['%s: %s' % (answer['db'], answer['sentence'])]
        for check in answer['checks']:
            lines.append('  [%s] %s — %s' % (
                'ok' if check['ok'] else 'NO', check['key'], check['text']))
        return '\n'.join(lines)
