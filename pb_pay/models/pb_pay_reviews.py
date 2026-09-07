# -*- coding: utf-8 -*-
"""`pb.pay.reviews` — the one door the Review and Changes screens talk through.

Same shape as `pb.pay.bands`: an AbstractModel with no table, every public
method a whole answer, every read scoped to the companies the reader may see,
every refusal a sentence, and a reader with no role given an EXPLAINED empty
board rather than an access dialog they cannot act on.

WHY A FACADE AND NOT `search_read` FROM THE BROWSER
---------------------------------------------------
Because a worksheet of nine hundred rows with a budget meter, a fairness line
and a limit check on every row is not a list of records — it is one answer,
and it has to be worked out in one place or the number at the top and the
numbers in the rows will disagree with each other in front of a reader who is
about to change somebody's pay.
"""

import logging
import time
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pb_pay_guidance import POSITION_BANDS, scale_words
from .pb_pay_review import GROUP_CEO, GROUP_FINANCE, GROUP_MANAGER

_logger = logging.getLogger(__name__)

#: How many worksheet rows one payload carries. Beyond this the screen pages.
PAGE = 120

#: How many dots the calibration picture draws.
MAX_DOTS = 900

READ_GROUPS = (
    'pb_pay.group_pay_viewer', 'pb_pay.group_pay_manager',
    'pb_pay.group_pay_finance', 'pb_pay.group_pay_ceo',
    'pb_group.group_group_admin', 'hr.group_hr_manager', 'base.group_system',
)


class PbPayReviews(models.AbstractModel):
    _name = 'pb.pay.reviews'
    # GROUP P7 — every read on this screen goes through `who sees what`.
    # A reader with no visibility row is narrowed by nothing at all.
    _inherit = ['pb.group.scoped']
    _description = 'Pay review screen'

    # ---------------------------------------------------------------- rails
    @api.model
    def _safe(self, fn, default=None):
        """A card that cannot be worked out does not take the page with it."""
        try:
            return fn()
        except Exception:                       # noqa: BLE001
            _logger.exception('pb_pay: a review card could not be worked out')
            return default

    @api.model
    def _has(self, *groups):
        for name in groups:
            try:
                if self.env.user.has_group(name):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _can_read(self):
        return self._has(*READ_GROUPS)

    @api.model
    def _can_write(self):
        return self._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                         'base.group_system')

    @api.model
    def _can_apply(self):
        return self._has(GROUP_MANAGER, 'base.group_system')

    @api.model
    def _require_read(self):
        if not self._can_read():
            raise AccessError(_(
                "Pay reviews are read by the pay roles. Your account holds "
                "none of them."))

    @api.model
    def _require_write(self):
        self._require_read()
        if not self._can_write():
            raise AccessError(_(
                "Only somebody who runs pay reviews can change one."))

    @api.model
    def _companies(self):
        return self.env['pb.pay.bands']._companies()

    @api.model
    def _wide(self, companies=None):
        """This model, with every company the reader is ENTITLED to switched on.

        GR27, for the fourth time in this programme. Pay is read for every
        company somebody may see rather than for the ones they happen to have
        ticked in the menu — but the record rule on a review, and the read
        check on `res.company` itself, both consult `allowed_company_ids`,
        which is the MENU. So a review for a company the reader can see but is
        not standing in is refused with the platform's "top-secret records"
        dialog, on a screen whose whole job is to look across companies.

        Widening the context to the intersection of the scope and
        `res.users.company_ids` is not a privilege: that context may only ever
        be a subset of the user's own companies. It is needed on every read AND
        every write of a review.
        """
        allowed = companies if companies is not None else self._companies()
        mine = set(self.env.user.company_ids.ids)
        ids = [company_id for company_id in allowed.ids if company_id in mine]
        if not ids:
            return self
        return self.with_context(allowed_company_ids=ids)

    # =============================================================== the list
    @api.model
    def get_board(self):
        """Every review and pay change this reader may see, and what is next."""
        started = time.time()
        blank = {
            'allowed': False, 'can_write': False, 'can_apply': False,
            'reviews': [], 'changes': [], 'scopes': [], 'guidance': [],
            'settings': {}, 'awaiting': {'count': 0, 'rows': []},
            'empty_title': '', 'empty_note': '', 'ms': 0,
        }
        if not self._can_read():
            blank['empty_title'] = _("Pay reviews are not open to you.")
            blank['empty_note'] = _(
                "A pay review is read by the pay roles. Your account holds "
                "none of them, so there is nothing here to show you.")
            return blank
        companies = self._companies()
        wide = self._wide(companies).env
        Review = wide['pb.pay.review']
        reviews = Review.search(
            [('company_ids', 'in', companies.ids)], limit=60)
        Change = wide['pb.pay.change']
        changes = Change.search(
            [('company_id', 'in', companies.ids)], limit=60)
        board = dict(blank)
        board.update({
            'allowed': True,
            'can_write': self._can_write(),
            'can_apply': self._can_apply(),
            'reviews': [self._card(review) for review in reviews],
            'changes': [change.payload() for change in changes],
            'scopes': self._safe(lambda: Review.scopes(), default=[]) or [],
            'guidance': self._safe(lambda: self.guidance_list(),
                                   default=[]) or [],
            'settings': self._safe(
                lambda: self.env['pb.pay.settings'].for_company(
                    self.env.company).summary(), default={}) or {},
            'awaiting': self._safe(lambda: self.awaiting(),
                                   default={'count': 0, 'rows': []}) or {},
            'today': str(fields.Date.context_today(self)),
        })
        if not reviews:
            board['empty_title'] = _("No pay review yet.")
            board['empty_note'] = _(
                "A review opens with a suggested rise already filled in for "
                "everybody it covers, the budget already counting and the "
                "fairness check already run. Start one and look before you "
                "change anything.")
        board['ms'] = int((time.time() - started) * 1000)
        return board

    @api.model
    def _card(self, review):
        money = self.env['pb.pay.bands']
        currency = review.currency_id or self.env.company.currency_id
        budget = float(review.budget_amount or 0.0)
        used = float(review.allocated_amount or 0.0)
        return {
            'id': review.id,
            'name': review.name or '',
            'scope_label': review.scope_label or '',
            'scope_note': review.scope_note or '',
            'scope_kind': review.scope_kind,
            'year': review.year,
            'state': review.state,
            'state_label': dict(review._fields['state'].selection).get(
                review.state, review.state),
            'people': review.people,
            'budget': budget,
            'budget_label': money._short(budget, currency),
            'allocated': used,
            'allocated_label': money._short(used, currency),
            'meter': _('%(used)s of %(budget)s',
                       used=money._short(used, currency),
                       budget=money._short(budget, currency))
            if budget else money._short(used, currency),
            'pct': round(used / budget * 100.0, 1) if budget else 0.0,
            'over': bool(budget and used > budget),
            'blocked': review.lines_blocked,
            'effective_date': str(review.effective_date or ''),
            'is_legacy': bool(review.is_legacy),
            'next_step': self._next_step(review),
            'undo_until': str(review.undo_until or ''),
        }

    @api.model
    def _next_step(self, review):
        """Who the review is waiting on, in words, or what it is waiting for."""
        return {
            'draft': _('Waiting to be sent for approval'),
            'proposed': _('Waiting for HR'),
            'hr_review': _('Waiting for finance'),
            'finance': _('Waiting for the CEO'),
            'approved': _('Approved — ready to apply'),
            'applied': _('Applied'),
            'closed': _('Closed'),
            'refused': _('Sent back'),
        }.get(review.state, '')

    @api.model
    def guidance_list(self):
        return [{'id': grid.id, 'name': grid.name,
                 'scale': grid.rating_scale,
                 'country': grid.country_code or '',
                 'squares': grid.cell_count}
                for grid in self.env['pb.pay.guidance'].sudo().search([])]

    @api.model
    def awaiting(self):
        """What is waiting on THIS reader right now, for the Home strip."""
        if not self._can_read():
            return {'count': 0, 'rows': []}
        wanted = []
        if self._has(GROUP_MANAGER, 'base.group_system'):
            wanted.append('proposed')
        if self._has(GROUP_FINANCE, 'base.group_system'):
            wanted.append('hr_review')
        if self._has(GROUP_CEO, 'base.group_system'):
            wanted.append('finance')
        if not wanted:
            return {'count': 0, 'rows': []}
        companies = self._companies()
        wide = self._wide(companies).env
        rows = []
        for review in wide['pb.pay.review'].search(
                [('state', 'in', wanted),
                 ('company_ids', 'in', companies.ids)], limit=30):
            rows.append({'kind': 'review', 'id': review.id,
                         'name': review.name or '',
                         'people': review.people,
                         'state': review.state})
        for change in wide['pb.pay.change'].search(
                [('state', 'in', wanted),
                 ('company_id', 'in', companies.ids)], limit=30):
            rows.append({'kind': 'change', 'id': change.id,
                         'name': change.name or '', 'people': 1,
                         'state': change.state})
        return {'count': len(rows), 'rows': rows,
                'sentence': self._awaiting_sentence(len(rows))}

    @api.model
    def _awaiting_sentence(self, count):
        if not count:
            return ''
        if count == 1:
            return _("1 pay decision is waiting for you.")
        return _("%(count)s pay decisions are waiting for you.", count=count)

    # ============================================================ one review
    @api.model
    def open_review(self, review_id, page=0, filters=None):
        """The whole review: header, meters, fairness, limits, rows, trail."""
        started = time.time()
        self._require_read()
        review = self._review(review_id)
        can_names = self._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                              'hr.group_hr_manager', 'base.group_system')
        lines = self._filtered_lines(review, filters or {})
        page = max(0, int(page or 0))
        window = lines[page * PAGE:(page + 1) * PAGE]
        fairness = self._safe(lambda: review.fairness(), default={}) or {}
        return {
            'allowed': True,
            'can_write': self._can_write() and not review.is_legacy,
            'can_apply': self._can_apply(),
            'card': self._card(review),
            'guidance': review.guidance_id.grid()
            if review.guidance_id else None,
            'limits': [limit.summary() for limit in review.limit_ids],
            'rows': [line.payload(can_names) for line in window],
            'total_rows': len(lines),
            'page': page,
            'pages': max(1, (len(lines) + PAGE - 1) // PAGE),
            'fairness': fairness,
            'fairness_line': fairness.get('sentence', ''),
            'blockers': self._blockers(review),
            'trail': review.get_approval_trail(),
            'steps': review._approval_steps(),
            'actions': self._actions(review),
            'columns': [{'key': key, 'label': label}
                        for key, label in POSITION_BANDS],
            'words': scale_words(review.rating_scale),
            'unrated': len(review.line_ids.filtered(lambda l: not l.rating)),
            'ms': int((time.time() - started) * 1000),
        }

    @api.model
    def _review(self, review_id):
        """One review, read with every company the reader is entitled to."""
        review = self._wide().env['pb.pay.review'].browse(
            int(review_id or 0)).exists()
        if not review:
            raise UserError(_("That review is not there any more."))
        return review

    @api.model
    def _filtered_lines(self, review, filters):
        lines = review.line_ids
        which = (filters or {}).get('which') or 'all'
        if which == 'mine':
            me = self.env.user.employee_id
            if me:
                lines = lines.filtered(lambda l: l.manager_id.id == me.id)
        elif which == 'unrated':
            lines = lines.filtered(lambda l: not l.rating)
        elif which == 'blocked':
            lines = lines.filtered(
                lambda l: any(c.get('blocks') for c in (l.chips or [])))
        elif which == 'below_band':
            lines = lines.filtered(
                lambda l: l.has_band and l.position_pct < 0)
        elif which == 'no_rise':
            lines = lines.filtered(lambda l: not l.proposal_pct)
        text = ((filters or {}).get('text') or '').strip().lower()
        if text:
            lines = lines.filtered(
                lambda l: text in (l.employee_id.name or '').lower()
                or text in (l.job_id.display_name or '').lower()
                or text in (l.department_id.display_name or '').lower())
        return lines.sorted(
            key=lambda l: (l.department_id.display_name or '',
                           l.employee_id.name or ''))

    @api.model
    def _blockers(self, review):
        """"What stops approval", as a short list of real sentences."""
        out = []
        counted = defaultdict(int)
        example = {}
        for line in review.line_ids:
            for chip in (line.chips or []):
                if not chip.get('blocks'):
                    continue
                counted[chip['key']] += 1
                example.setdefault(chip['key'], chip.get('text', ''))
        for key, count in counted.items():
            out.append({'key': key, 'count': count,
                        'text': example.get(key, ''),
                        'label': _('%(count)s rows', count=count)})
        budget = float(review.budget_amount or 0.0)
        if budget and review.allocated_amount > budget:
            money = self.env['pb.pay.bands']
            currency = review.currency_id or self.env.company.currency_id
            out.append({
                'key': 'budget', 'count': 0,
                'label': _('Over budget'),
                'text': _("This review proposes %(over)s more than its "
                          "budget.",
                          over=money._money(
                              review.allocated_amount - budget, currency))})
        return out

    @api.model
    def _actions(self, review):
        """Which buttons this reader may press, decided on the server."""
        state = review.state
        can = review._approval_can
        return {
            'submit': state == 'draft' and can('draft', 'proposed'),
            'hr': state == 'proposed' and can('proposed', 'hr_review'),
            'finance': state == 'hr_review' and can('hr_review', 'finance'),
            'ceo': state == 'finance' and can('finance', 'approved'),
            'apply': state == 'approved' and self._can_apply(),
            'undo': state == 'applied' and bool(review.undo_until)
            and fields.Datetime.now() <= review.undo_until,
            'undo_gone': state == 'applied' and bool(review.undo_until)
            and fields.Datetime.now() > review.undo_until,
            'send_back': state in ('proposed', 'hr_review', 'finance',
                                   'approved')
            and review._approval_can(state, 'draft'),
            'drop': state in ('draft', 'proposed', 'hr_review', 'finance',
                              'approved')
            and review._approval_can_refuse(state),
            'close': state == 'applied' and can('applied', 'closed'),
            'undo_note': _(
                "The time to take this back ran out at %(when)s. To move the "
                "pay again, make a pay change — that leaves a record of both "
                "moves.", when=fields.Datetime.to_string(review.undo_until))
            if review.undo_until
            and fields.Datetime.now() > review.undo_until else '',
        }

    # ============================================================== creation
    @api.model
    def create_review(self, values):
        """Start a review and fill its worksheet in one call."""
        self._require_write()
        values = values or {}
        scope_kind = values.get('scope_kind') or 'company'
        scope_ref = int(values.get('scope_ref') or 0)
        scope = self.env['pb.pay.review']._scope_companies(
            scope_kind, scope_ref)
        companies = scope['companies']
        if not companies:
            raise UserError(_(
                "There is nobody in that group of people to review."))
        Review = self._wide(companies).env['pb.pay.review']
        company = companies[:1]
        settings = self.env['pb.pay.settings'].for_company(company)
        guidance_id = int(values.get('guidance_id') or 0) \
            or (settings.guidance_id.id if settings.guidance_id else 0)
        if not guidance_id:
            grid = self.env['pb.pay.guidance'].for_company(company)
            guidance_id = grid.id if grid else 0
        year = int(values.get('year')
                   or fields.Date.context_today(self).year)
        review = Review.create({
            'name': values.get('name')
            or _('%(scope)s · %(year)s', scope=scope['label'], year=year),
            'scope_kind': scope_kind, 'scope_ref': scope_ref,
            'scope_label': scope['label'],
            'company_id': company.id,
            'company_ids': [(6, 0, companies.ids)],
            'currency_id': company.currency_id.id,
            'year': year,
            'effective_date': values.get('effective_date')
            or fields.Date.context_today(self),
            'budget_amount': float(values.get('budget_amount') or 0.0),
            'guidance_id': guidance_id or False,
            'note': values.get('note') or '',
            'limit_ids': settings.default_limits(),
        })
        review.build_lines()
        return {'id': review.id, 'people': review.people,
                'sentence': _(
                    "“%(name)s” is ready: %(people)s people, each with a "
                    "suggested rise already filled in.",
                    name=review.name, people=review.people)}

    @api.model
    def make_default_guidance(self):
        self._require_write()
        grid = self.env['pb.pay.guidance'].make_default(self.env.company)
        settings = self.env['pb.pay.settings'].for_company(self.env.company)
        if not settings.guidance_id:
            settings.sudo().guidance_id = grid.id
        return {'id': grid.id, 'name': grid.name, 'grid': grid.grid()}

    @api.model
    def save_guidance_cell(self, cell_id, pct):
        self._require_write()
        cell = self.env['pb.pay.guidance.cell'].sudo().browse(
            int(cell_id or 0)).exists()
        if not cell:
            raise UserError(_("That square is not there any more."))
        cell.write({'pct': float(pct or 0.0)})
        return cell.guidance_id.grid()

    # ============================================================ the writes
    @api.model
    def set_proposals(self, review_id, rows):
        """Write many proposals and recompute everything ONCE."""
        self._require_write()
        review = self._editable(review_id)
        by_id = {line.id: line for line in review.line_ids}
        touched = self.env['pb.pay.review.line']
        for row in rows or []:
            line = by_id.get(int(row.get('line_id') or 0))
            if not line:
                continue
            if row.get('amount') is not None:
                line._recalc(amount=float(row.get('amount') or 0.0))
            else:
                line._recalc(pct=float(row.get('pct') or 0.0))
            if row.get('note') is not None:
                line.manager_note = row.get('note') or ''
            touched |= line
        review.recompute_chips()
        review.mark_fairness_dirty()
        return self._after_write(review, len(touched))

    @api.model
    def nudge(self, review_id, line_ids, by_pct):
        """"Select a block and type +1" — the gesture the whole screen is for."""
        self._require_write()
        review = self._editable(review_id)
        step = float(by_pct or 0.0)
        lines = review.line_ids.filtered(lambda l: l.id in set(line_ids or []))
        for line in lines:
            line._recalc(pct=float(line.proposal_pct or 0.0) + step)
        review.recompute_chips()
        review.mark_fairness_dirty()
        return self._after_write(review, len(lines))

    @api.model
    def apply_guidance(self, review_id, line_ids=None):
        self._require_write()
        review = self._editable(review_id)
        lines = review.line_ids
        if line_ids:
            lines = lines.filtered(lambda l: l.id in set(line_ids))
        review.apply_guidance_to(lines)
        return self._after_write(review, len(lines))

    @api.model
    def spread_remaining(self, review_id, line_ids=None, by='rating'):
        """Share what is left of the budget out, in one of two honest ways.

        By score: the people who did better get more of it. Evenly: everybody
        gets the same percentage. Nothing is spread if there is nothing left,
        and the sentence says so rather than silently doing nothing.
        """
        self._require_write()
        review = self._editable(review_id)
        left = float(review.remaining_amount or 0.0)
        lines = review.line_ids
        if line_ids:
            lines = lines.filtered(lambda l: l.id in set(line_ids))
        if left <= 0:
            return dict(self._after_write(review, 0), sentence=_(
                "There is nothing left of the budget to share out."))
        if not lines:
            return dict(self._after_write(review, 0), sentence=_(
                "There is nobody selected to share it between."))
        weights = {}
        for line in lines:
            if by == 'rating':
                weights[line.id] = float(max(1, line.rating or 1))
            else:
                weights[line.id] = 1.0
        total = sum(weights.values()) or 1.0
        for line in lines:
            share = left * weights[line.id] / total / 12.0
            line._recalc(amount=float(line.proposal_amount or 0.0) + share)
        review.recompute_chips()
        review.mark_fairness_dirty()
        answer = self._after_write(review, len(lines))
        money = self.env['pb.pay.bands']
        answer['sentence'] = _(
            "%(amount)s shared between %(count)s people.",
            amount=money._short(left, review.currency_id),
            count=len(lines))
        return answer

    @api.model
    def _editable(self, review_id):
        review = self._review(review_id)
        if review.is_legacy:
            raise UserError(_(
                "This review was carried over from the old screens and is "
                "kept as history. It cannot be changed."))
        if review.state not in ('draft', 'proposed', 'hr_review', 'finance'):
            raise UserError(_(
                "This review has already been decided, so its numbers cannot "
                "be changed."))
        return review

    @api.model
    def _after_write(self, review, touched):
        """The header, the blockers and the changed rows — never the whole page."""
        return {
            'card': self._card(review),
            'blockers': self._blockers(review),
            'fairness_line': (review.fairness() or {}).get('sentence', ''),
            'touched': touched,
            'actions': self._actions(review),
        }

    @api.model
    def rows(self, review_id, line_ids):
        """Re-read a handful of rows after a write, rather than the page."""
        self._require_read()
        try:
            review = self._review(review_id)
        except UserError:
            return []
        can_names = self._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                              'hr.group_hr_manager', 'base.group_system')
        wanted = set(line_ids or [])
        return [line.payload(can_names) for line in review.line_ids
                if line.id in wanted]

    # ============================================================ ratings
    @api.model
    def paste_ratings(self, review_id, text, dry_run=True):
        self._require_write()
        self._editable(review_id)
        return self.env['pb.pay.rating'].paste(review_id, text, dry_run)

    @api.model
    def set_rating(self, review_id, employee_id, rating):
        self._require_write()
        self._editable(review_id)
        return self.env['pb.pay.rating'].set_one(
            review_id, employee_id, rating)

    @api.model
    def sync_ratings(self, review_id):
        self._require_write()
        self._editable(review_id)
        return self.env['pb.pay.rating'].sync_from_connected_system(review_id)

    # ========================================================== calibration
    @api.model
    def calibration(self, review_id):
        """Every person as a dot: how well they did across, the rise up.

        The outliers are not a matter of taste. A dot is ringed when its rise
        is more than two standard deviations above the average rise of the
        people who scored the SAME — which is the question a calibration
        meeting is actually asking — or when it already breaks a limit.
        """
        self._require_read()
        review = self._review(review_id)
        can_names = self._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                              'hr.group_hr_manager', 'base.group_system')
        by_rating = defaultdict(list)
        for line in review.line_ids:
            by_rating[line.rating or 0].append(float(line.proposal_pct or 0.0))
        stats = {}
        for rating, values in by_rating.items():
            mean = sum(values) / len(values) if values else 0.0
            variance = sum((v - mean) ** 2 for v in values) / len(values) \
                if values else 0.0
            stats[rating] = (mean, variance ** 0.5,
                             self.env['pb.pay.bands']._median(values))

        dots, outliers = [], []
        for line in review.line_ids[:MAX_DOTS]:
            mean, deviation, middle = stats.get(line.rating or 0,
                                                (0.0, 0.0, 0.0))
            pct = float(line.proposal_pct or 0.0)
            # TWO tests, because one of them is useless on a small team. Two
            # standard deviations is the right question over a few hundred
            # people; over four, the one big number IS most of the deviation
            # and nothing is ever ringed. So a rise of more than twice the
            # middle of its own group, and at least two points above it, is
            # an outlier as well — which is what a person means when they say
            # "that one is much bigger than the others".
            far = (deviation > 0 and pct > mean + 2 * deviation) \
                or (middle > 0 and pct > 2 * middle and pct - middle >= 2.0)
            blocked = any(c.get('blocks') for c in (line.chips or []))
            # A rating the grid does not have — an old score of 5 on a
            # four-level scale — is drawn at the top rather than off the
            # right-hand edge, and a person nobody has scored is drawn in the
            # middle with the chip on their row saying so. A dot outside the
            # picture is a person the meeting cannot see.
            levels = int(review.rating_scale or '4')
            column = int(line.rating or 0)
            if column < 1:
                column = max(1, (levels + 1) // 2)
            column = min(column, levels)
            dot = {
                'line_id': line.id,
                'name': line.employee_id.name if can_names
                else _('Person %(number)s', number=line.id),
                'rating': int(line.rating or 0),
                'column': column,
                # A deterministic spread inside the column. Nine hundred
                # people on four ratings land on four points and the picture
                # reads as four dots; nudging each one sideways by a number
                # derived from its own id turns a stack back into a cloud, and
                # the same person lands in the same place every time.
                'jitter': ((line.id * 37) % 100) / 100.0,
                'pct': round(float(line.proposal_pct or 0.0), 2),
                'position_pct': round(float(line.position_pct or 0.0), 1),
                'cost': float(line.annual_cost_delta or 0.0),
                'team': line.department_id.display_name or '',
                'outlier': bool(far or blocked),
            }
            dots.append(dot)
            if far or blocked:
                outliers.append(dict(dot, why=_(
                    "This rise breaks a limit.") if blocked else _(
                    "Much bigger than the others who scored the same.")))
        highest = max([d['pct'] for d in dots] or [0.0])
        # A picture of a review nobody has touched is five straight lines,
        # because every row still holds exactly what the guidance suggested.
        # That is TRUE and it looks broken, so the screen says which it is.
        spread = {round(dot['pct'], 2) for dot in dots}
        flat = len(spread) <= max(1, len(by_rating))
        return {
            'dots': dots,
            'flat': bool(flat),
            'flat_note': _(
                "Everybody is still on the guidance, so each score sits on "
                "one line. Move a dot, or change a row in the worksheet, and "
                "the picture spreads out.") if flat else '',
            'outliers': outliers[:60],
            'levels': int(review.rating_scale or '4'),
            'words': scale_words(review.rating_scale),
            'max_pct': max(highest, 1.0),
            'card': self._card(review),
            'capped': len(review.line_ids) > MAX_DOTS,
            'capped_note': _(
                "The picture draws the first %(count)s people. The budget and "
                "the limits are worked out over all of them.", count=MAX_DOTS)
            if len(review.line_ids) > MAX_DOTS else '',
        }

    # ============================================================= the chain
    @api.model
    def act(self, review_id, what, note=False):
        """Send on, send back or close — one door for the whole ladder."""
        self._require_read()
        review = self._review(review_id)
        if what == 'drop':
            # The only way OUT of a review nobody is going to run. It is the
            # mixin's own refusal, so it is logged in the trail with whoever
            # pressed it, and it is not a delete: what was proposed stays
            # readable.
            review.action_refuse_chain(note=note or False)
            return {'card': self._card(review),
                    'actions': self._actions(review),
                    'trail': review.get_approval_trail(),
                    'sentence': _("Dropped. Nothing was changed.")}
        target = {
            'submit': 'proposed', 'hr': 'hr_review', 'finance': 'finance',
            'ceo': 'approved', 'close': 'closed', 'send_back': 'draft',
        }.get(what)
        if not target:
            raise UserError(_("That is not something a review can do."))
        review._advance_state(target, note=note or False)
        return {'card': self._card(review),
                'actions': self._actions(review),
                'trail': review.get_approval_trail(),
                'sentence': self._step_sentence(what, review)}

    @api.model
    def _step_sentence(self, what, review):
        return {
            'submit': _("Sent to HR."),
            'hr': _("Sent to finance."),
            'finance': _("Sent to the CEO."),
            'ceo': _("Approved. It can be applied now."),
            'send_back': _("Sent back to be worked on again."),
            'close': _("Closed."),
        }.get(what, _("Done."))

    @api.model
    def return_line(self, review_id, line_id, note):
        """Send ONE row back to its manager with a reason."""
        self._require_write()
        review = self._review(review_id)
        line = review.line_ids.filtered(lambda l: l.id == int(line_id or 0))
        if not line:
            raise UserError(_("That row is not in this review."))
        if not (note or '').strip():
            raise UserError(_(
                "Say why it is going back. A row that comes back with no "
                "reason cannot be acted on."))
        line.write({'state': 'returned', 'returned_note': note})
        review.message_post(body=_(
            "%(who)s was sent back: %(why)s",
            who=line.employee_id.name or '', why=note))
        return self.rows(review.id, [line.id])

    # ======================================================= apply and undo
    @api.model
    def preview_apply(self, review_id):
        self._require_read()
        return self._wide().env['pb.pay.apply'].preview_review(review_id)

    @api.model
    def apply(self, review_id):
        self._require_write()
        if not self._can_apply():
            raise AccessError(_(
                "Only somebody who runs pay can write a new figure onto a "
                "contract."))
        answer = self._wide().env['pb.pay.apply'].apply_review(review_id)
        review = self._review(review_id)
        answer['card'] = self._card(review)
        answer['actions'] = self._actions(review)
        return answer

    @api.model
    def undo(self, review_id):
        self._require_write()
        answer = self._wide().env['pb.pay.apply'].undo_review(review_id)
        review = self._review(review_id)
        answer['card'] = self._card(review)
        answer['actions'] = self._actions(review)
        return answer

    # =========================================================== pay changes
    @api.model
    def people_for_change(self, text=''):
        """The people this reader may make a pay change for."""
        self._require_read()
        companies = self._companies()
        domain = [('company_id', 'in', companies.ids)]
        text = (text or '').strip()
        if text:
            domain.append(('name', 'ilike', text))
        people = self.env['hr.employee'].sudo().search(domain, limit=30)
        return [{'id': person.id, 'name': person.name or '',
                 'job': person.job_title or '',
                 'company': person.company_id.display_name or ''}
                for person in people]

    @api.model
    def prepare_change(self, employee_id):
        """What a pay change for this person would start from."""
        self._require_write()
        Change = self._wide().env['pb.pay.change']
        draft = Change.new({'employee_id': int(employee_id or 0)})
        draft._fill_from_employee()
        draft._recalc()
        money = self.env['pb.pay.bands']
        currency = draft.currency_id or self.env.company.currency_id
        blocked = self.env['pb.pay.review.line'].sudo().search([
            ('employee_id', '=', int(employee_id or 0)),
            ('review_id.state', 'in',
             ('draft', 'proposed', 'hr_review', 'finance', 'approved')),
        ], limit=1)
        return {
            'employee_id': int(employee_id or 0),
            'employee': draft.employee_id.name or '',
            'current_wage': float(draft.current_wage or 0.0),
            'current_label': money._money(draft.current_wage, currency),
            'currency': currency.name or '',
            'band': draft.band_id.name or '',
            'position_before': round(float(draft.position_before or 0.0), 1),
            'guidance_pct': round(float(draft.guidance_pct or 0.0), 2),
            'has_contract': bool(draft.contract_id),
            'blocked_by_review': blocked.review_id.name or '',
            'blocked_note': _(
                "%(who)s is in the pay review “%(review)s”, which has not "
                "finished. Change their pay there instead.",
                who=draft.employee_id.name or '',
                review=blocked.review_id.name or '') if blocked else '',
        }

    @api.model
    def create_change(self, values):
        self._require_write()
        values = values or {}
        change = self._wide().env['pb.pay.change'].create({
            'employee_id': int(values.get('employee_id') or 0),
            'kind': values.get('kind') or 'promotion',
            'new_wage': float(values.get('new_wage') or 0.0),
            'new_job_id': int(values.get('new_job_id') or 0) or False,
            'effective_date': values.get('effective_date')
            or fields.Date.context_today(self),
            'reason': values.get('reason') or '',
        })
        return change.payload()

    @api.model
    def change_act(self, change_id, what, note=False):
        self._require_read()
        change = self._wide().env['pb.pay.change'].browse(
            int(change_id or 0)).exists()
        if not change:
            raise UserError(_("That pay change is not there any more."))
        if what == 'apply':
            if not self._can_apply():
                raise AccessError(_(
                    "Only somebody who runs pay can write a new figure onto a "
                    "contract."))
            answer = change.action_apply()
            return dict(change.payload(), **answer)
        if what == 'undo':
            answer = change.action_undo()
            return dict(change.payload(), **answer)
        target = {'submit': 'proposed', 'hr': 'hr_review',
                  'send_back': 'draft', 'close': 'closed'}.get(what)
        if what == 'next':
            target = 'finance' if change.needs_finance() else 'approved'
        if what == 'ceo':
            target = 'approved'
        if not target:
            raise UserError(_("That is not something a pay change can do."))
        change._advance_state(target, note=note or False)
        return change.payload()

    @api.model
    def update_change(self, change_id, values):
        self._require_write()
        change = self._wide().env['pb.pay.change'].browse(
            int(change_id or 0)).exists()
        if not change:
            raise UserError(_("That pay change is not there any more."))
        if change.state not in ('draft',):
            raise UserError(_(
                "This pay change has been sent for approval, so its numbers "
                "cannot be changed. Send it back first."))
        allowed = {'new_wage', 'kind', 'effective_date', 'reason',
                   'new_job_id'}
        change.write({key: value for key, value in (values or {}).items()
                      if key in allowed})
        return change.payload()
