# -*- coding: utf-8 -*-
"""Learning › Courses › OUTSIDE, Claims › REQUESTS, the course drawer's
version / ratings / skills, and the Overview and Numbers additions
(LEARNING L5).

One read per screen, behind the board's gate (`{'allowed': False}` without a
training group, never an AccessError):

  * `outside_board(filters)`  the outside catalogue as cards;
  * `outside_page(id)`        one outside course: who asked, who took it,
                              ratings, claims against it, skills it gives;
  * `requests_board(filters)` every course request, problem first;
  * `course_extras(id)`       version, ratings, follow-up answers, skills it
                              gives, "people may ask to take it".

Writes go through `act`. WHO MAY DO WHAT: a trainer keeps the outside list,
decides requests where a route seat is theirs (the ENGINE checks the seat —
the press runs as the caller, never as the system), puts people on courses
and edits the skills a course gives; only a training manager publishes a new
version of a course.
"""

import logging

from odoo import _, api, fields, models
from odoo.tools.misc import format_date
from odoo.exceptions import AccessError, UserError

from .course_version import require_manager
from .feedback import rating_words, rollup
from .outside_course import check_outside_values
from .pb_training_sessions import PbTrainingSessions
from .training_common import (
    FOLLOWUP_STATE_LABEL, GROUP_ADMIN, GROUP_MANAGER, OUTSIDE_KIND_LABEL,
    OUTSIDE_KINDS, REQUEST_KIND_LABEL, REQUEST_KINDS, REQUEST_STATE_LABEL,
    as_id, fold, money_words, tr,
)

_logger = logging.getLogger(__name__)

#: The four steps a request moves through on the Requests tab (a request is
#: at exactly one): waiting · agreed · taken or claimed · closed.
REQUEST_STEPS = {
    'waiting': ('draft', 'submitted'),
    'agreed': ('approved',),
    'done': ('taken', 'claimed'),
    'closed': ('refused', 'cancelled'),
}
REQUEST_RANK = {'submitted': 0, 'draft': 1, 'approved': 2, 'taken': 3,
                'claimed': 4, 'refused': 5, 'cancelled': 6}
REQUEST_CAP = 300


class PbTrainingCatalogue(models.AbstractModel):
    _inherit = 'pb.training'

    _VERBS = PbTrainingSessions._VERBS + (
        'create_test', 'set_pool',
        'save_outside', 'archive_outside', 'put_on_outside', 'put_on_course',
        'approve_request', 'refuse_request', 'mark_taken', 'open_request',
        'publish_version', 'save_grant', 'drop_grant', 'set_requestable',
        'close_gap',
    )

    # =====================================================================
    #  helpers
    # =====================================================================
    @api.model
    def _can_manage(self):
        user = self.env.user
        return user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)

    @api.model
    def _outside(self, course_id):
        rec = self.env['pb.training.outside.course'].sudo().with_context(
            active_test=False).browse(as_id(course_id)).exists()
        if not rec or rec.company_id.id not in self.env.companies.ids:
            raise UserError(_("That outside course is not here any more."))
        return rec

    @api.model
    def _request(self, request_id):
        rec = self.env['pb.training.request'].sudo().browse(
            as_id(request_id)).exists()
        if not rec or rec.company_id.id not in self.env.companies.ids:
            raise UserError(_("That request is not here any more."))
        return rec

    @api.model
    def _outside_card(self, rec):
        data = rollup(self.env, [('outside_course_id', '=', rec.id)])
        reqs = rec.request_ids.sudo()
        months = rec.validity_months
        cert = ''
        if rec.issues_certificate:
            cert = (_("Certificate, valid %s months", months) if months
                    else _("Certificate that does not run out"))
        return {
            'id': rec.id,
            'name': rec.name or '',
            'provider': rec.provider or '',
            'url': rec.url or '',
            'kind': rec.kind,
            'kind_word': tr(self.env, OUTSIDE_KIND_LABEL.get(rec.kind, '')),
            'cost': rec.cost or 0.0,
            'cost_words': rec.cost_words(),
            'currency': rec.currency_id.name or '',
            'hours': rec.hours or 0.0,
            'hours_words': rec.hours_words(),
            'blurb': rec.blurb or '',
            'jobs': rec.job_ids.mapped('name'),
            'job_ids': rec.job_ids.ids,
            'country': rec.country_id.name or '',
            'country_id': rec.country_id.id,
            'issues_certificate': bool(rec.issues_certificate),
            'validity_months': months or 0,
            'certificate_words': cert,
            'rating_words': rating_words(self.env, data),
            'avg_rating': data.get('avg_rating'),
            'ratings_count': data.get('ratings_count') or 0,
            'waiting': len(reqs.filtered(lambda r: r.state == 'submitted')),
            'requests_count': len(reqs.filtered(
                lambda r: r.state != 'cancelled')),
            'taken_count': len(reqs.filtered(
                lambda r: r.state in ('taken', 'claimed'))),
            'skills': [g._words() for g in rec.skill_grant_ids.sudo()],
            'active': bool(rec.active),
        }

    # =====================================================================
    #  OUTSIDE — the catalogue
    # =====================================================================
    @api.model
    def outside_lists(self):
        if not self._can_read():
            return {'allowed': False}
        jobs = self.env['hr.job'].sudo().search(
            [('company_id', 'in', self.env.companies.ids + [False])],
            order='name')
        countries = self.env.companies.mapped('partner_id.country_id')
        return {
            'allowed': True,
            'kinds': [{'key': k, 'label': tr(self.env, v)}
                      for k, v in OUTSIDE_KINDS],
            'jobs': [{'id': j.id, 'name': j.name} for j in jobs],
            'countries': [{'id': c.id, 'name': c.name} for c in countries],
            'currency': self.env.company.currency_id.name or '',
        }

    @api.model
    def outside_board(self, filters=None):
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'kpis': {}}
        filters = filters or {}
        Course = self.env['pb.training.outside.course'].sudo().with_context(
            active_test=False)
        domain = [('company_id', 'in', self.env.companies.ids)]
        all_rows = Course.search(domain)
        live = all_rows.filtered('active')
        rows = live if not filters.get('archived') else \
            all_rows.filtered(lambda r: not r.active)
        if filters.get('kind') in dict(OUTSIDE_KINDS):
            rows = rows.filtered(lambda r: r.kind == filters['kind'])
        job = as_id(filters.get('job_id'))
        if job:
            rows = rows.filtered(lambda r: job in r.job_ids.ids)
        needle = fold(filters.get('q') or '')
        if needle:
            rows = rows.filtered(lambda r: needle in fold(
                '%s %s %s' % (r.name, r.provider or '', r.blurb or '')))
        cards = [self._outside_card(r) for r in rows]
        # PROBLEM FIRST: somebody waiting for a decision, then the most asked.
        cards.sort(key=lambda c: (-c['waiting'], -c['requests_count'],
                                  fold(c['name'])))
        Request = self.env['pb.training.request'].sudo()
        year = fields.Date.today().year
        outside_reqs = Request.search([
            ('company_id', 'in', self.env.companies.ids),
            ('kind', 'in', ('outside', 'other'))])
        waiting = len(outside_reqs.filtered(lambda r: r.state == 'submitted'))
        taken = len(outside_reqs.filtered(
            lambda r: r.state in ('taken', 'claimed') and r.year == year))
        kpis = {
            'courses': len(live),
            'waiting': waiting,
            'taken': taken,
            'archived': len(all_rows) - len(live),
            'spend': self._money_by_currency(outside_reqs.filtered(
                lambda r: r.state in ('approved', 'taken', 'claimed')
                and r.year == year)),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'rows': cards,
            'kpis': kpis,
            'headline': self._outside_headline(kpis),
            'filtered': bool(filters.get('kind') or job or needle
                             or filters.get('archived')),
        }

    @api.model
    def _money_by_currency(self, requests):
        """Never one total over two currencies: one phrase per currency."""
        sums = {}
        for req in requests:
            sums.setdefault(req.currency_id, 0.0)
            sums[req.currency_id] += req.amount or 0.0
        return ' + '.join(money_words(self.env, v, c)
                          for c, v in sums.items() if v)

    @api.model
    def _outside_headline(self, k):
        if not k['courses']:
            return _("No outside courses yet.")
        bits = [_("1 outside course") if k['courses'] == 1
                else _("%s outside courses", k['courses'])]
        if k['waiting']:
            bits.append(_("1 request waiting") if k['waiting'] == 1
                        else _("%s requests waiting", k['waiting']))
        if k['taken']:
            bits.append(_("1 taken this year") if k['taken'] == 1
                        else _("%s taken this year", k['taken']))
        return ' · '.join(str(b) for b in bits)

    @api.model
    def outside_page(self, course_id):
        self._require_read()
        rec = self._outside(course_id)
        card = self._outside_card(rec)
        data = rollup(self.env, [('outside_course_id', '=', rec.id)])
        reqs = rec.request_ids.sudo().sorted(
            lambda r: (REQUEST_RANK.get(r.state, 9), -r.id))
        claims = self.env['pb.training.claim'].sudo().search(
            [('outside_course_id', '=', rec.id)], order='id desc', limit=40)
        card.update({
            'people': [r._payload() for r in reqs[:80]],
            'claims': [{
                'id': c.id, 'who': c.employee_id.sudo().name or '',
                'amount_words': money_words(self.env, c.amount,
                                            c.currency_id),
                'state_word': tr(self.env, dict(
                    c._fields['state'].selection).get(c.state, '')),
                'state': c.state,
            } for c in claims],
            'ratings': data,
            'grants': [{'id': g.id, 'words': g._words()}
                       for g in rec.skill_grant_ids.sudo()],
            'can_write': self._can_write(),
        })
        return card

    @api.model
    def save_outside(self, payload=None):
        self._require_write()
        payload = payload or {}
        vals = check_outside_values(self.env, payload)
        Course = self.env['pb.training.outside.course']
        if as_id(payload.get('id')):
            rec = self._outside(payload['id'])
            rec.write(vals)
            return {'id': rec.id, 'message': _("%s is saved.", rec.name)}
        vals['company_id'] = self.env.company.id
        vals['currency_id'] = self.env.company.currency_id.id
        rec = Course.sudo().create(vals)
        return {'id': rec.id, 'message': _(
            "%s is on the outside list. People can ask to take it from My "
            "learning.", rec.name)}

    @api.model
    def archive_outside(self, course_id, active=False):
        self._require_write()
        rec = self._outside(course_id)
        rec.write({'active': bool(active)})
        if active:
            return {'message': _("%s is back on the list.", rec.name)}
        return {'message': _(
            "%s is archived. Nobody new can ask for it; requests already "
            "agreed carry on.", rec.name)}

    # =====================================================================
    #  putting somebody on a course (the training team agrees it)
    # =====================================================================
    @api.model
    def _put_on(self, emp, vals):
        """One request, created already agreed on the person's behalf. The
        money rule still applies (the allowance is the only gate)."""
        Request = self.env['pb.training.request'].sudo()
        vals = dict(vals, employee_id=emp.id,
                    company_id=(emp.company_id or self.env.company).id)
        with self.env.cr.savepoint():
            rec = Request.create(vals)
            problem = rec._request_problem()
            if problem:
                raise UserError(problem)
            rec._chain_state_write('approved')
            rec.write({'put_on_by_id': self.env.uid})
            rec._after_approval_transition('approved')
            rec.message_post(body=_("Agreed by the training team (%s) on the "
                                    "person's behalf.", self.env.user.name))
        return rec

    @api.model
    def put_on_outside(self, payload=None):
        self._require_write()
        payload = payload or {}
        course = self._outside(payload.get('outside_course_id'))
        if not course.active:
            raise UserError(_("That outside course is archived."))
        return self.put_on_course(dict(payload, kind='outside',
                                       outside_course_id=course.id))

    @api.model
    def put_on_course(self, payload=None):
        """"Put someone on a course": people + what + why → agreed requests,
        one per person. Says what really happened, person by person."""
        self._require_write()
        payload = payload or {}
        ids = [as_id(e) for e in (payload.get('employee_ids') or [])
               if as_id(e)]
        if as_id(payload.get('employee_id')):
            ids.append(as_id(payload['employee_id']))
        if not ids:
            raise UserError(_("Pick at least one person."))
        why = (payload.get('why') or '').strip()[:2000] or \
            _("Put on by the training team.")
        emps = self.env['hr.employee'].sudo().search([
            ('id', 'in', ids), ('company_id', 'in', self.env.companies.ids)])
        Request = self.env['pb.training.request']
        made, failed = [], []
        for emp in emps:
            try:
                vals = Request._values_from_form(
                    emp, dict(payload, why=why))
                self._put_on(emp, vals)
                made.append(emp.name or '')
            except (UserError, AccessError) as err:
                failed.append('%s: %s' % (emp.name or '', err))
            except Exception:           # noqa: BLE001 — one person, one grave
                _logger.warning('pb_training: %s could not be put on a '
                                'course', emp.id, exc_info=True)
                failed.append(emp.name or '')
        if not made and failed:
            raise UserError(' '.join(failed[:3]))
        bits = [_("1 person is on it.") if len(made) == 1
                else _("%s people are on it.", len(made))]
        if failed:
            bits.append(_("Not done for: %s", '; '.join(failed[:3])))
        return {'made': len(made), 'failed': failed,
                'message': ' '.join(str(b) for b in bits)}

    # =====================================================================
    #  REQUESTS — the Claims lens's second tab
    # =====================================================================
    @api.model
    def requests_board(self, filters=None):
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'steps': {}}
        filters = filters or {}
        Request = self.env['pb.training.request'].sudo()
        base = [('company_id', 'in', self.env.companies.ids)]
        every = Request.search(base)
        steps = {k: len(every.filtered(lambda r, s=v: r.state in s))
                 for k, v in REQUEST_STEPS.items()}
        rows = every
        step = filters.get('step')
        if step in REQUEST_STEPS:
            rows = rows.filtered(lambda r: r.state in REQUEST_STEPS[step])
        if filters.get('kind') in dict(REQUEST_KINDS):
            rows = rows.filtered(lambda r: r.kind == filters['kind'])
        needle = fold(filters.get('q') or '')
        if needle:
            rows = rows.filtered(lambda r: needle in fold('%s %s' % (
                r.employee_id.name or '', r.course_name or '')))
        rows = rows.sorted(lambda r: (REQUEST_RANK.get(r.state, 9), -r.id))
        shown = rows[:REQUEST_CAP]
        out = []
        for rec in shown:
            data = rec._payload()
            data['waiting_on'] = self._waiting_on(rec)
            data['can_decide'] = rec.state == 'submitted'
            data['can_mark_taken'] = rec.state == 'approved' \
                and rec.kind != 'ours'
            out.append(data)
        year = fields.Date.today().year
        committed = every.filtered(
            lambda r: r.state in ('approved', 'taken') and r.amount > 0)
        claimed = every.filtered(
            lambda r: r.state == 'claimed' and r.year == year)
        kpis = {
            'waiting': steps['waiting'],
            'agreed': steps['agreed'],
            'done': steps['done'],
            'closed': steps['closed'],
            'total': len(every),
            'committed_words': self._money_by_currency(committed),
            'claimed_words': self._money_by_currency(claimed),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'rows': out,
            'steps': steps,
            'kpis': kpis,
            'shown': len(out),
            'matching': len(rows),
            'headline': self._requests_headline(kpis),
            'kinds': [{'key': k, 'label': tr(self.env, v)}
                      for k, v in REQUEST_KINDS],
        }

    @api.model
    def _waiting_on(self, rec):
        """"Waiting on Ngô Bảo Lâm" — who holds the live seat, if anybody."""
        if rec.state != 'submitted':
            return ''
        try:
            step = rec._chain_active_step()
            seats = step.sudo().seat_ids.filtered(lambda s: s.status == 'open')
            names = seats.mapped('acting_user_id.name')
            if names:
                return _("Waiting on %s", ', '.join(names[:2]))
            if step:
                return _("Waiting on %s", step.title or '')
        except Exception:               # noqa: BLE001 — a word is not fatal
            _logger.debug('pb_training: seat not readable', exc_info=True)
        return ''

    @api.model
    def _requests_headline(self, k):
        if not k['total']:
            return _("Nobody has asked to take a course yet.")
        bits = []
        if k['waiting']:
            bits.append(_("1 request is waiting for a decision")
                        if k['waiting'] == 1
                        else _("%s requests are waiting for a decision",
                               k['waiting']))
        if k['agreed']:
            bits.append(_("1 agreed and not taken yet") if k['agreed'] == 1
                        else _("%s agreed and not taken yet", k['agreed']))
        if k['committed_words']:
            bits.append(_("%s set aside", k['committed_words']))
        if not bits:
            bits.append(_("Nothing is waiting on anybody"))
        return ' · '.join(str(b) for b in bits)

    @api.model
    def approve_request(self, request_id):
        """Agree it — AS THE CALLER (AM84): the engine checks the seat."""
        self._require_write()
        rec = self._request(request_id)
        rec.with_user(self.env.user).action_approve()
        rec.invalidate_recordset()
        if rec.state == 'approved':
            if rec.kind == 'ours':
                return {'message': _("Agreed. %s is on their training page "
                                     "now.", rec.course_name)}
            return {'message': _("Agreed. They have the link and how to "
                                 "claim it back.")}
        return {'message': _("Your decision is recorded. It now waits on the "
                             "next person.")}

    @api.model
    def refuse_request(self, request_id, note=''):
        self._require_write()
        rec = self._request(request_id)
        note = (note or '').strip()[:2000]
        if not note:
            raise UserError(_(
                "Say why. They get it in an email, and a refusal with no "
                "reason is one they will ask about instead."))
        rec.sudo().write({'refuse_note': note})
        rec.with_user(self.env.user).action_refuse_chain(note)
        return {'message': _("Turned down, and they have been told why.")}

    @api.model
    def mark_taken(self, request_id):
        self._require_write()
        rec = self._request(request_id)
        if rec.state != 'approved':
            raise UserError(_("Only an agreed request can be marked as "
                              "taken."))
        rec._mark_taken()
        return {'message': _("%s is marked as taken.", rec.course_name)}

    @api.model
    def open_request(self, request_id):
        self._require_read()
        rec = self._request(request_id)
        return {
            'type': 'ir.actions.act_window', 'name': _("Course request"),
            'res_model': 'pb.training.request', 'res_id': rec.id,
            'view_mode': 'form', 'views': [[False, 'form']],
            'target': 'current',
        }

    # =====================================================================
    #  the course drawer — version, ratings, skills, requests
    # =====================================================================
    @api.model
    def course_extras(self, channel_id):
        self._require_read()
        channel = self.env['slide.channel'].sudo().browse(
            as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        data = rollup(self.env, [('channel_id', '=', channel.id)])
        Followup = self.env['pb.training.followup'].sudo()
        waiting = Followup.search_count([('channel_id', '=', channel.id),
                                         ('state', '=', 'sent')])
        planned = Followup.search_count([('channel_id', '=', channel.id),
                                         ('state', '=', 'planned')])
        reqs = self.env['pb.training.request'].sudo().search_count([
            ('channel_id', '=', channel.id), ('state', '=', 'submitted')])
        return {
            'id': channel.id,
            'version': channel.pb_version or 1,
            'version_since': format_date(
                self.env, channel.pb_version_published_on)
            if channel.pb_version_published_on else '',
            'version_note': channel.pb_version_note or '',
            'version_words': (_("Version %(n)s, since %(when)s. What changed: "
                                "%(note)s", n=channel.pb_version,
                                when=format_date(
                                    self.env,
                                    channel.pb_version_published_on),
                                note=channel.pb_version_note or '')
                              if channel.pb_version_published_on
                              else _("The first version.")),
            'version_log': str(channel.pb_version_log or ''),
            'pending': len(channel._pb_queue()),
            'reread_days': channel.pb_reread_days or 14,
            'can_manage': self._can_manage(),
            'can_write': self._can_write(),
            'requestable': bool(channel.pb_requestable),
            'requests_waiting': reqs,
            'ratings': data,
            'rating_words': rating_words(self.env, data),
            'followups_waiting': waiting,
            'followups_planned': planned,
            'grants': [{'id': g.id, 'words': g._words(),
                        'skill': g.skill_id.name or '',
                        'level': g.skill_level_id.name or ''}
                       for g in channel.pb_skill_grant_ids.sudo()],
            'finishers': len(channel._pb_finishers()),
        }

    @api.model
    def publish_version(self, channel_id, note, reread_days=None):
        self._require_read()
        require_manager(self.env)
        channel = self.env['slide.channel'].browse(as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        res = channel._pb_publish_version(note, reread_days)
        if not res['people']:
            msg = _("Version %s is published. Nobody had finished the last "
                    "one, so nobody is asked to read it again.",
                    res['version'])
        elif res['left']:
            msg = _("Version %(v)s is published. %(done)s of %(n)s people are "
                    "on the re-read now; the morning job puts on the other "
                    "%(left)s.", v=res['version'], done=res['done'],
                    n=res['people'], left=res['left'])
        else:
            msg = _("Version %(v)s is published. %(n)s people who finished "
                    "the last one have a re-read and an email saying what "
                    "changed.", v=res['version'], n=res['done'])
        return dict(res, message=msg)

    @api.model
    def skill_lists(self):
        self._require_read()
        types = self.env['hr.skill.type'].sudo().search([])
        return {'types': [{
            'id': t.id, 'name': t.name,
            'skills': [{'id': s.id, 'name': s.name} for s in t.skill_ids],
            'levels': [{'id': lv.id, 'name': lv.name,
                        'progress': lv.level_progress or 0}
                       for lv in t.skill_level_ids.sorted('level_progress')],
        } for t in types]}

    @api.model
    def save_grant(self, payload=None):
        self._require_write()
        payload = payload or {}
        skill = self.env['hr.skill'].sudo().browse(
            as_id(payload.get('skill_id'))).exists()
        level = self.env['hr.skill.level'].sudo().browse(
            as_id(payload.get('skill_level_id'))).exists()
        if not skill or not level:
            raise UserError(_("Pick the skill and the level it gives."))
        vals = {'skill_id': skill.id, 'skill_level_id': level.id,
                'company_id': self.env.company.id}
        if as_id(payload.get('channel_id')):
            vals['channel_id'] = as_id(payload['channel_id'])
            key = ('channel_id', vals['channel_id'])
        elif as_id(payload.get('outside_course_id')):
            vals['outside_course_id'] = self._outside(
                payload['outside_course_id']).id
            key = ('outside_course_id', vals['outside_course_id'])
        else:
            raise UserError(_("Pick the course."))
        Grant = self.env['pb.training.skill.grant'].sudo()
        old = Grant.search([key, ('skill_id', '=', skill.id)])
        old.unlink()
        Grant.create(vals)
        return {'message': _("Finishing it now gives %(skill)s at %(level)s.",
                             skill=skill.name, level=level.name)}

    @api.model
    def drop_grant(self, grant_id):
        self._require_write()
        grant = self.env['pb.training.skill.grant'].sudo().browse(
            as_id(grant_id)).exists()
        if not grant:
            raise UserError(_("That is not here any more."))
        words = grant._words()
        grant.unlink()
        return {'message': _("%s is no longer given by this course. Nobody "
                             "who already has it loses it.", words)}

    @api.model
    def set_requestable(self, channel_id, on):
        self._require_write()
        channel = self.env['slide.channel'].sudo().browse(
            as_id(channel_id)).exists()
        if not channel:
            raise UserError(_("That course is not here any more."))
        channel.write({'pb_requestable': bool(on)})
        return {'message': _("People can ask to take it.") if on
                else _("It is no longer offered when people ask for a "
                       "course.")}

    # =====================================================================
    #  the Courses tab's cards
    # =====================================================================
    def _course_row(self, channel):
        row = super()._course_row(channel)
        try:
            sudo = channel.sudo()
            row['version'] = sudo.pb_version or 1
            data = rollup(self.env, [('channel_id', '=', channel.id)])
            row['rating_words'] = rating_words(self.env, data)
            row['requestable'] = bool(sudo.pb_requestable)
        except Exception:               # noqa: BLE001 — a chip is not fatal
            _logger.warning('pb_training: course chips could not be read',
                            exc_info=True)
        return row

    # =====================================================================
    #  the Overview
    # =====================================================================
    @api.model
    def overview(self):
        data = super().overview()
        if not data.get('allowed'):
            return data
        companies = self.env.companies.ids
        waiting = self._safe(lambda: self.env['pb.training.request'].sudo()
                             .search_count([('company_id', 'in', companies),
                                            ('state', '=', 'submitted')]))
        followups = self._safe(lambda: self.env['pb.training.followup'].sudo()
                               .search_count([('company_id', 'in', companies),
                                              ('state', '=', 'sent')]))
        if waiting:
            data['calm'] = False
        data['queue'] = data.get('queue', []) + [
            {'key': 'course_requests', 'label': _("Course requests waiting"),
             'count': waiting, 'lens': 'claims', 'tab': 'course_requests'},
            {'key': 'followups',
             'label': _("Follow-ups waiting on managers"),
             'count': followups, 'lens': 'numbers', 'tab': ''},
        ]
        return data

    # =====================================================================
    #  the dispatcher
    # =====================================================================
    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'save_outside':
            return self.save_outside(payload)
        if verb == 'archive_outside':
            return self.archive_outside(payload.get('outside_course_id'),
                                        payload.get('active'))
        if verb == 'put_on_outside':
            return self.put_on_outside(payload)
        if verb == 'put_on_course':
            return self.put_on_course(payload)
        if verb == 'approve_request':
            return self.approve_request(payload.get('request_id'))
        if verb == 'refuse_request':
            return self.refuse_request(payload.get('request_id'),
                                       payload.get('note'))
        if verb == 'mark_taken':
            return self.mark_taken(payload.get('request_id'))
        if verb == 'open_request':
            return self.open_request(payload.get('request_id'))
        if verb == 'publish_version':
            return self.publish_version(payload.get('channel_id'),
                                        payload.get('note'),
                                        payload.get('reread_days'))
        if verb == 'save_grant':
            return self.save_grant(payload)
        if verb == 'drop_grant':
            return self.drop_grant(payload.get('grant_id'))
        if verb == 'set_requestable':
            return self.set_requestable(payload.get('channel_id'),
                                        payload.get('on'))
        return super().act(verb, payload)


# =========================================================================
#  the Numbers
# =========================================================================
class PbTrainingAnalyticsL5(models.AbstractModel):
    _inherit = 'pb.training.analytics'

    @api.model
    def _l5_numbers(self, start, end, filters=None):
        from datetime import datetime
        filters = filters or {}
        companies = self.env.companies.ids
        lo = datetime.combine(start, datetime.min.time())
        hi = datetime.combine(end, datetime.max.time())
        span = [('company_id', 'in', companies), ('submitted_at', '>=', lo),
                ('submitted_at', '<=', hi)]
        channel = as_id(filters.get('channel_id'))
        if channel:
            span.append(('channel_id', '=', channel))
        overall = rollup(self.env, span)
        Feedback = self.env['pb.feedback.request'].sudo()
        by_course = {}
        for req in Feedback.search(span + [('state', '=', 'submitted'),
                                           ('kind', 'in', (
                                               'training',
                                               'training_followup'))]):
            key = ('c', req.channel_id.id) if req.channel_id else \
                ('o', req.outside_course_id.id)
            by_course.setdefault(key, req)
        ratings = []
        for (kind, rid), req in by_course.items():
            dom = span + ([('channel_id', '=', rid)] if kind == 'c'
                          else [('outside_course_id', '=', rid)])
            data = rollup(self.env, dom)
            ratings.append({
                'name': req._pb_course_name(),
                'outside': kind == 'o',
                'avg': data['avg_rating'],
                'count': data['ratings_count'],
                'recommend': data['recommend_pct'],
                'effect': data['effect_avg'],
                'used': data['used_pct'],
                'answered': data['followups_answered'],
            })
        ratings.sort(key=lambda r: (-(r['count'] or 0), fold(r['name'])))
        Followup = self.env['pb.training.followup'].sudo()
        waiting = Followup.search_count([('company_id', 'in', companies),
                                         ('state', '=', 'sent')])
        Request = self.env['pb.training.request'].sudo()
        reqs = Request.search([('company_id', 'in', companies),
                               ('create_date', '>=', lo),
                               ('create_date', '<=', hi)])
        by_state = []
        for key, label in REQUEST_STATE_LABEL.items():
            n = len(reqs.filtered(lambda r, k=key: r.state == k))
            if n:
                by_state.append({'key': key, 'label': tr(self.env, label),
                                 'n': n})
        by_kind = []
        for key, label in REQUEST_KIND_LABEL.items():
            n = len(reqs.filtered(lambda r, k=key: r.kind == k))
            if n:
                by_kind.append({'key': key, 'label': tr(self.env, label),
                                'n': n})
        facade = self.env['pb.training']
        return {
            'ratings': {
                'avg': overall['avg_rating'],
                'count': overall['ratings_count'],
                'recommend': overall['recommend_pct'],
                'rows': ratings[:20],
            },
            'did_it_work': {
                'answered': overall['followups_answered'],
                'waiting': waiting,
                'effect': overall['effect_avg'],
                'used': overall['used_pct'],
                'state_words': {k: tr(self.env, v)
                                for k, v in FOLLOWUP_STATE_LABEL.items()},
            },
            'requests': {
                'total': len(reqs),
                'by_state': by_state,
                'by_kind': by_kind,
                'committed_words': facade._money_by_currency(reqs.filtered(
                    lambda r: r.state in ('approved', 'taken')
                    and r.amount > 0)),
                'claimed_words': facade._money_by_currency(reqs.filtered(
                    lambda r: r.state == 'claimed')),
            },
        }

    @api.model
    def get_numbers(self, date_from=None, date_to=None, filters=None):
        payload = super().get_numbers(date_from, date_to, filters)
        if not payload.get('allowed'):
            return payload
        start, end = self._range(date_from, date_to)
        extra = self._safe(lambda: self._l5_numbers(start, end, filters),
                           default={})
        payload['ratings'] = extra.get('ratings') or {'rows': []}
        payload['did_it_work'] = extra.get('did_it_work') or {}
        payload['course_requests'] = extra.get('requests') or {
            'by_state': [], 'by_kind': []}
        payload['skills'] = self._safe(
            lambda: self.env['pb.training']._skills_summary(),
            default={'rows': []})
        return payload

