# -*- coding: utf-8 -*-
"""`/my/goals` — the employee's own goals page.

THE ROUTE IS THE GATE. The employee is re-resolved from the SESSION user on
every request and no route accepts an employee id, so a crafted URL can never
open somebody else's goals. The only ids a route takes are a goal, a key result
and a template, and every one of them is checked against the caller's own sheet
inside `pb.my.goals` before anything is read or written.

THIS FILE HOLDS NO RULES. It proves who is asking, it posts the form, and it
renders; every fact and every refusal comes from `pb.my.goals`, so the journey a
person walks in a browser is the journey the test suite walks in Python.

EVERY PRIVATE HELPER HERE CARRIES `_gl_`, AND THAT IS NOT A STYLE CHOICE (R186).
ALL `CustomerPortal` SUBCLASSES MERGE INTO ONE CLASS: a helper called `_notice`
here and `_notice` in `pb_rnr` are the same attribute on the same class, and
whichever module loads last silently wins. It has bitten this programme three
times — a confirmation sentence that never once appeared on a live page, and a
`_problem` clash that turned an error page into a different error page — and
nothing about any of it is visible at runtime.

A REFUSAL IS A CODE AND THIS FILE HOLDS THE WORDS. Putting the sentence in the
redirect writes whatever is in the query string onto the page, and a page that
prints back what somebody put in the address bar is a page somebody else can
write. The exceptions are the refusals that carry ARITHMETIC — "the weights add
up to 90" — which come back from the model as whole sentences and are shown
through a flash the model itself wrote.
"""

import logging

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

class PbGoalsPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _gl_facade(self):
        return request.env['pb.my.goals']

    #: SAID ONCE, IN WORDS, so the same refusal reads the same way on every
    #: path — and BUILT INSIDE THE METHOD rather than in a module-level dict.
    #: A `_()` evaluated at import time has no language to translate into: the
    #: module load logs "no translation language detected" once per sentence
    #: and the string is frozen in English for every reader, for ever. The
    #: sentences have to be built while a request is in flight.
    def _gl_notice(self, key):
        return {
            'added': _("Added."),
            'saved': _("Saved."),
            'deleted': _("Deleted."),
            'template': _("Added from the template — every word of it is "
                          "yours to change."),
            'sent': _("Sent to your manager. You will get an email either "
                      "way."),
            'moved': _("Progress saved."),
        }.get(key or '', '')

    def _gl_problem(self, key):
        return {
            'mine': _("That one is not yours. If you think it should be, tell "
                      "your HR team."),
            'none': _("You have no goal sheet open. When the goal year opens "
                      "you will get an email."),
            'locked': _("Your goals have been agreed, so they cannot be "
                        "changed. Ask your manager to send them back if "
                        "something has to move."),
            'no_employee': _("You do not have an employee record yet, so "
                             "there is nowhere to write your goals. Tell your "
                             "HR team."),
            'saved': _("That did not save. Try again, and tell your HR team "
                       "if it keeps happening."),
        }.get(key or '', '')

    def _gl_back(self, problem=None, ok=None, flash=None):
        """Back to the page, with one sentence."""
        url = '/my/goals'
        bits = []
        if problem:
            bits.append('problem=%s' % problem)
        if ok:
            bits.append('ok=%s' % ok)
        if flash:
            # The model's own sentence, kept in the session rather than in the
            # query string: a page must never print back what somebody typed
            # into the address bar.
            request.session['pb_goals_flash'] = flash[:400]
        if bits:
            url += '?' + '&'.join(bits)
        return request.redirect(url)

    def _gl_run(self, fn, ok=None):
        """Do one thing, and turn any refusal into a sentence on the page."""
        try:
            fn()
        except (UserError, AccessError) as err:
            message = err.args[0] if err.args else ''
            return self._gl_back(flash=str(message))
        except Exception:               # noqa: BLE001 — never a 500 on a form
            _logger.exception('pb_goals: a goals page action failed')
            return self._gl_back(problem='saved')
        return self._gl_back(ok=ok)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'goals_count' in counters:
            values['goals_count'] = self._gl_facade().home_count()
        return values

    def _prepare_portal_layout_values(self):
        """The eager key the home card is drawn on (R62).

        `portal.portal_my_home` fetches its counters lazily, AFTER the page
        renders, so at render time `goals_count` is not a number and a
        `t-if="goals_count"` is simply false — no error, and a card that is
        never drawn. A card whose PRESENCE is conditional needs its own eagerly
        computed key, and QWeb raises on a name it has never heard of, so a
        missing key turns a hidden card into a 500 for the whole of `/my`.
        """
        values = super()._prepare_portal_layout_values()
        try:
            values['pb_goals_has'] = bool(self._gl_facade()._current())
        except Exception:               # noqa: BLE001 — /my never 500s over us
            values['pb_goals_has'] = False
        return values

    # =================================================================
    #  The page
    # =================================================================
    @http.route(['/my/goals'], type='http', auth='user', website=True)
    def portal_my_goals(self, **kw):
        data = self._gl_facade().home()
        flash = request.session.pop('pb_goals_flash', '')
        return request.render('pb_goals.portal_my_goals', {
            'page_name': 'goals',
            'me': data,
            'notice': self._gl_notice(kw.get('ok')),
            'problem': self._gl_problem(kw.get('problem')) or flash,
        })

    # =================================================================
    #  Writing
    # =================================================================
    @http.route(['/my/goals/goal/new'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_goal_new(self, **post):
        return self._gl_run(lambda: self._gl_facade().add_goal({
            'title': post.get('title'),
            'description': post.get('description'),
            'date_start': post.get('date_start') or False,
            'date_end': post.get('date_end') or False,
            'self_rating': post.get('self_rating') or False,
        }), ok='added')

    @http.route(['/my/goals/goal/<int:goal_id>/edit'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_goal_edit(self, goal_id, **post):
        return self._gl_run(lambda: self._gl_facade().edit_goal(goal_id, {
            'title': post.get('title'),
            'description': post.get('description'),
            'date_start': post.get('date_start') or False,
            'date_end': post.get('date_end') or False,
            'self_rating': post.get('self_rating') or False,
        }), ok='saved')

    @http.route(['/my/goals/goal/<int:goal_id>/delete'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_goal_delete(self, goal_id, **post):
        return self._gl_run(
            lambda: self._gl_facade().delete_goal(goal_id), ok='deleted')

    @http.route(['/my/goals/template/<int:template_id>'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_goal_template(self, template_id, **post):
        return self._gl_run(
            lambda: self._gl_facade().use_template(template_id), ok='template')

    @http.route(['/my/goals/goal/<int:goal_id>/kr/new'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_kr_new(self, goal_id, **post):
        return self._gl_run(lambda: self._gl_facade().add_kr(goal_id, {
            'title': post.get('title'),
            'measure': post.get('measure'),
            'target': post.get('target') or 0,
            'current': post.get('current') or 0,
            'due_date': post.get('due_date') or False,
        }), ok='added')

    @http.route(['/my/goals/kr/<int:kr_id>/edit'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_kr_edit(self, kr_id, **post):
        return self._gl_run(lambda: self._gl_facade().edit_kr(kr_id, {
            'title': post.get('title'),
            'measure': post.get('measure'),
            'target': post.get('target') or 0,
            'due_date': post.get('due_date') or False,
        }), ok='saved')

    @http.route(['/my/goals/kr/<int:kr_id>/delete'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_kr_delete(self, kr_id, **post):
        return self._gl_run(
            lambda: self._gl_facade().delete_kr(kr_id), ok='deleted')

    @http.route(['/my/goals/kr/<int:kr_id>/move'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_kr_move(self, kr_id, **post):
        """Move a key result along — the one thing that works after the lock."""
        return self._gl_run(lambda: self._gl_facade().move_kr(
            kr_id, post.get('progress') or 0, post.get('current'),
            post.get('note') or ''), ok='moved')

    @http.route(['/my/goals/submit'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_goals_submit(self, **post):
        return self._gl_run(lambda: self._gl_facade().submit(), ok='sent')
