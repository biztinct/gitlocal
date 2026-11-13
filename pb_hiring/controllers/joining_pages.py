# -*- coding: utf-8 -*-
"""RECRUIT P6 — the three pages "Before they join" sends people to.

  * `/hiring/b/<token>` — the hiring manager names one or more buddies
    (English, R11).
  * `/hiring/l/<token>` — the new joiner says how they want their laptop, in
    the language they applied in (`pb_lang`; words from `.po`, vi_VN/id_ID).
  * `/hiring/w/<token>` — the week-before page: still on, the date changed,
    or they will not join (English).

THE LINK IS THE CREDENTIAL (the `/hiring/f/` doctrine): 24 random bytes per
item or per person asked; a GET only looks (an email scanner that follows a
link changes nothing) and a POST answers; one page per status, so a wrong key
and a spent one read the same to a stranger; a spent link says who answered
and gives the recruiter's address.
"""

import logging
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.pb_hiring.models.hiring_common import DROP_REASONS

_logger = logging.getLogger(__name__)

_MAX = 2000


def laptop_words(env):
    """Every sentence of the laptop page, in the page's language (`.po`)."""
    _t = env._
    return {
        'eyebrow': _t('Before you join'),
        'title': _t('Your laptop'),
        'lede': _t('We are getting your first day ready. Tell us how you like to work and we will set your laptop up that way.'),
        'joining': _t('You join on {date}'),
        'q_kind': _t('Which kind of laptop?'),
        'mac': _t('Mac'),
        'windows': _t('Windows'),
        'any': _t('No preference'),
        'q_keyboard': _t('Keyboard layout'),
        'kb_us': _t('English (US)'),
        'kb_uk': _t('English (UK)'),
        'kb_vi': _t('Vietnamese'),
        'kb_id': _t('Indonesian'),
        'kb_other': _t('Something else'),
        'q_screen': _t('Screen size'),
        'small': _t('13 to 14 inch, easy to carry'),
        'large': _t('15 to 16 inch, more room'),
        'q_extras': _t('Anything else you would like?'),
        'mouse': _t('A mouse'),
        'headset': _t('A headset'),
        'monitor': _t('A second screen'),
        'stand': _t('A laptop stand'),
        'q_note': _t('Anything we should know?'),
        'note_ph': _t('For example: I am left-handed, or I use a screen reader.'),
        'optional': _t('Optional'),
        'send': _t('Send my answers'),
        'fine': _t('Only the people preparing your first day see this.'),
        'need_kind': _t('Choose Mac, Windows or no preference.'),
        'thanks': _t('Thank you'),
        'thanks_sub': _t('Your answers are with the team getting your first day ready. See you soon.'),
        'used_title': _t('Already answered'),
        'used_sub': _t('You have already told us. If something has changed, write to {who}.'),
        'closed_title': _t('This link has closed'),
        'closed_sub': _t('There is nothing to answer here any more. If you think that is wrong, reply to the email that brought you here.'),
        'failed': _t('That did not save. Try once more; if it happens again, reply to the email that brought you here.'),
    }


class PbHiringJoiningPages(http.Controller):

    # ================================================================ buddy
    def _buddy_people(self, item):
        """The company's people, the manager's team first. Names, jobs and
        teams only — the manager is the reader."""
        offer = item.offer_id.sudo()
        manager = offer._manager()
        Emp = request.env['hr.employee'].sudo()
        rows = Emp.search([('company_id', '=', offer.company_id.id), ('active', '=', True)],
                          order='name', limit=800)
        team = set()
        if manager:
            team |= set(Emp.search([('parent_id', '=', manager.id)]).ids)
            if manager.department_id:
                team |= set(Emp.search([('department_id', '=', manager.department_id.id)]).ids)
        req = offer.requisition_id
        if req.department_id:
            team |= set(Emp.search([('department_id', '=', req.department_id.id)]).ids)
        out = [{'id': e.id, 'name': e.name or '', 'job': e.job_title or '',
                'dept': e.department_id.name or '', 'team': e.id in team}
               for e in rows if not manager or e.id != manager.id]
        out.sort(key=lambda r: (not r['team'], r['name'].lower()))
        return out

    @http.route('/hiring/b/<string:token>', type='http', auth='public', website=True,
                sitemap=False)
    def hiring_buddy_view(self, token, **kw):
        Item = request.env['pb.hiring.prejoin'].sudo()
        row, status = Item._request_for_token(token, 'buddy')
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        facts = row.page_facts() if row else {}
        if facts.get('join_date'):
            from odoo.tools.misc import format_date
            facts['join_words'] = format_date(request.env, facts['join_date'],
                                              date_format='EEEE d MMMM y')
        problem = {'none': _("Choose at least one person."),
                   'failed': _("That did not save. Try once more; if it happens again, "
                               "reply to the email that brought you here.")}.get(kw.get('problem'), '')
        return request.render('pb_hiring.hiring_buddy_page', {
            'status': status, 'token': token, 'facts': facts, 'problem': problem,
            'people': self._buddy_people(row) if status == 'ok' else [],
        })

    @http.route('/hiring/b/<string:token>/answer', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def hiring_buddy_answer(self, token, **post):
        """`csrf=False` like every token page here: the visitor has no session.
        The write touches one item and can only move it forward."""
        Item = request.env['pb.hiring.prejoin'].sudo()
        row, status = Item._request_for_token(token, 'buddy')
        if status != 'ok':
            return request.redirect('/hiring/b/%s' % token)
        ordered = [x for x in (post.get('order') or '').split(',') if x.strip().isdigit()]
        ticked = request.httprequest.form.getlist('emp')
        ids = [int(x) for x in ordered if x in ticked] + \
            [int(x) for x in ticked if x.isdigit() and x not in ordered]
        if not ids:
            return request.redirect('/hiring/b/%s?problem=none' % token)
        try:
            row.submit_buddy(ids, why=(post.get('why') or '')[:_MAX])
        except UserError:
            return request.redirect('/hiring/b/%s?problem=none' % token)
        except Exception:               # noqa: BLE001 — never a traceback
            _logger.exception('pb_hiring: a buddy answer failed')
            return request.redirect('/hiring/b/%s?problem=failed' % token)
        return request.redirect('/hiring/b/%s?done=1' % token)

    # =============================================================== laptop
    def _laptop_env(self, row):
        """The page's language: the one they applied in, when it is here."""
        lang = 'en_US'
        if row:
            want = row.offer_id.sudo().applicant_id.pb_lang or 'en_US'
            if request.env['res.lang'].sudo().search_count([('code', '=', want),
                                                             ('active', '=', True)]):
                lang = want
        return request.env(context=dict(request.env.context, lang=lang)), lang

    @http.route('/hiring/l/<string:token>', type='http', auth='public', website=True,
                sitemap=False)
    def hiring_laptop_view(self, token, **kw):
        Item = request.env['pb.hiring.prejoin'].sudo()
        row, status = Item._request_for_token(token, 'laptop')
        if kw.get('done') == '1' and status in ('used', 'ok'):
            status = 'thanks'
        env, lang = self._laptop_env(row)
        tx = laptop_words(env)
        facts = row.with_env(env).page_facts() if row else {}
        join = facts.get('join_date')
        if join:
            from odoo.tools.misc import format_date
            tx['joining'] = tx['joining'].replace(
                '{date}', format_date(env, join, lang_code=lang, date_format='EEEE d MMMM'))
        tx['used_sub'] = tx['used_sub'].replace(
            '{who}', facts.get('recruiter_email') or facts.get('recruiter') or '')
        problem = {'kind': tx['need_kind'], 'failed': tx['failed']}.get(kw.get('problem'), '')
        return request.render('pb_hiring.hiring_laptop_page', {
            'status': status, 'token': token, 'facts': facts, 'tx': tx,
            'problem': problem, 'page_lang': lang.split('_')[0],
        })

    @http.route('/hiring/l/<string:token>/answer', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def hiring_laptop_answer(self, token, **post):
        Item = request.env['pb.hiring.prejoin'].sudo()
        row, status = Item._request_for_token(token, 'laptop')
        if status != 'ok':
            return request.redirect('/hiring/l/%s' % token)
        values = {'kind': post.get('kind'), 'keyboard': post.get('keyboard'),
                  'screen': post.get('screen'),
                  'extras': request.httprequest.form.getlist('extras'),
                  'note': (post.get('note') or '')[:_MAX]}
        try:
            row.submit_laptop(values)
        except UserError:
            return request.redirect('/hiring/l/%s?problem=kind' % token)
        except Exception:               # noqa: BLE001 — never a traceback
            _logger.exception('pb_hiring: a laptop answer failed')
            return request.redirect('/hiring/l/%s?problem=failed' % token)
        return request.redirect('/hiring/l/%s?done=1' % token)

    # ========================================================== week before
    @http.route('/hiring/w/<string:token>', type='http', auth='public', website=True,
                sitemap=False)
    def hiring_week_view(self, token, **kw):
        Ask = request.env['pb.hiring.join.ask'].sudo()
        row, status = Ask._request_for_token(token)
        if kw.get('done') == '1' and status in ('used', 'ok', 'closed'):
            status = 'thanks'
        offer = row.offer_id.sudo() if row else None
        facts = {}
        if offer:
            from odoo.tools.misc import format_date
            req = offer.requisition_id
            join = offer.expected_join_date or offer.start_date
            facts = {
                'candidate': offer.candidate_name or '', 'role': offer.job_title or '',
                'join_words': format_date(request.env, join, date_format='EEEE d MMMM y')
                if join else '',
                'join_iso': str(join or ''),
                'min_iso': str(fields.Date.context_today(offer) + timedelta(days=1)),
                'who': row.name or '', 'recruiter': req.recruiter_id.name or '',
                'recruiter_email': req.recruiter_id.email or '',
                'answer': dict(offer._fields['week_answer'].selection).get(offer.week_answer, ''),
                'answered_by': offer.week_answered_by or '',
                'state': offer.state,
                'state_words': {'joined': _('They have started.'),
                                'dropped': _('They will not join.')}.get(offer.state, ''),
            }
        problem = {'date': _("Pick the new date — a day after today."),
                   'pick': _("Choose one of the three answers."),
                   'failed': _("That did not save. Try once more; if it happens again, "
                               "write to the recruiter.")}.get(kw.get('problem'), '')
        pick = kw.get('a') if kw.get('a') in ('still_on', 'changed', 'dropped') else ''
        return request.render('pb_hiring.hiring_week_page', {
            'status': status, 'token': token, 'facts': facts, 'problem': problem,
            'pick': pick, 'reasons': DROP_REASONS,
        })

    @http.route('/hiring/w/<string:token>/answer', type='http', auth='public',
                website=True, methods=['POST'], csrf=False, sitemap=False)
    def hiring_week_answer(self, token, **post):
        Ask = request.env['pb.hiring.join.ask'].sudo()
        row, status = Ask._request_for_token(token)
        if status != 'ok':
            return request.redirect('/hiring/w/%s' % token)
        answer = post.get('answer')
        if answer not in ('still_on', 'changed', 'dropped'):
            return request.redirect('/hiring/w/%s?problem=pick' % token)
        offer = row.offer_id.sudo()
        try:
            if answer == 'changed':
                new = fields.Date.to_date(post.get('new_date') or False)
                if not new or new <= fields.Date.context_today(offer):
                    return request.redirect('/hiring/w/%s?a=changed&problem=date' % token)
                offer.answer_week(row, 'changed', new_date=new,
                                  reason=(post.get('reason') or '')[:_MAX])
            elif answer == 'dropped':
                offer.answer_week(row, 'dropped', reason=(post.get('note') or '')[:_MAX],
                                  drop_reason=post.get('drop_reason'))
            else:
                offer.answer_week(row, 'still_on')
        except UserError:
            return request.redirect('/hiring/w/%s?a=%s&problem=date' % (token, answer))
        except Exception:               # noqa: BLE001 — never a traceback
            _logger.exception('pb_hiring: a week-before answer failed')
            return request.redirect('/hiring/w/%s?problem=failed' % token)
        return request.redirect('/hiring/w/%s?done=1&a=%s' % (token, answer))
