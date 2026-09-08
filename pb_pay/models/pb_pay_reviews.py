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
import math
import time
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pb_pay_guidance import POSITION_BANDS, scale_words
from .pb_pay_review import GROUP_CEO, GROUP_FINANCE, GROUP_MANAGER

_logger = logging.getLogger(__name__)

#: How many worksheet rows one payload carries. Beyond this the screen pages.
#: A worksheet is a LIST somebody pages through, which is a different thing
#: from a picture: a picture may never leave anybody out (LOOK rule 16).
PAGE = 120

#: How many people the "who is standing here" panel names at once. A LIST cap,
#: exactly like `pb.pay.bands.people_between`'s, and it says so on the panel.
PEOPLE_IN_BIN = 40

#: How many rows the "worth a second look" list carries. Also a LIST cap: the
#: picture draws every one of them, and the list says how many it did not name.
OUTLIER_ROWS = 60

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
    def _pct_pair(self, low, high):
        """Two ends of a range of PER CENT, told apart from each other.

        A bin on this picture is a few pixels of a percentage axis, so on a
        review whose rises run from 0 to 30% one bin is about a tenth of a
        point wide — and one decimal prints "7.0% to 7.0%" for two figures
        that are not the same figure (LOOK L4, the ruler's rule applied to the
        marks). The number of decimals comes from the range's OWN width.
        """
        low, high = float(low or 0.0), float(high or 0.0)
        spread = abs(high - low)
        if spread <= 0:
            decimals = 1
        else:
            decimals = max(0, min(3, int(math.ceil(-math.log10(spread))) + 1))
        return ('%.*f' % (decimals, low), '%.*f' % (decimals, high))

    @api.model
    def _stats_by_rating(self, rows):
        """Mean, standard deviation and median of the rise, per score."""
        by_rating = defaultdict(list)
        for row in rows:
            by_rating[int(row['rating'] or 0)].append(
                float(row['proposal_pct'] or 0.0))
        stats = {}
        for rating, values in by_rating.items():
            mean = sum(values) / len(values) if values else 0.0
            variance = sum((v - mean) ** 2 for v in values) / len(values) \
                if values else 0.0
            stats[rating] = (mean, variance ** 0.5,
                             self.env['pb.pay.bands']._median(values))
        return by_rating, stats

    @api.model
    def _calib_state(self, row, stats):
        """`normal`, `outlier` or `blocked` — the three words on this picture.

        The outliers are not a matter of taste. A rise stands out when it is
        more than two standard deviations above the average rise of the people
        who scored the SAME — which is the question a calibration meeting is
        actually asking — or when it is more than twice the middle of its own
        group and at least two points above it. The second test exists because
        the first is useless on a small team: over four people the one big
        number IS most of the deviation and nothing is ever ringed.

        A rise that breaks a limit is `blocked` whether or not it stands out:
        a limit saying no is the more urgent fact about that row.
        """
        chips = row.get('chips') or []
        if any(chip.get('blocks') for chip in chips
               if isinstance(chip, dict)):
            return 'blocked'
        mean, deviation, middle = stats.get(int(row['rating'] or 0),
                                            (0.0, 0.0, 0.0))
        pct = float(row['proposal_pct'] or 0.0)
        far = (deviation > 0 and pct > mean + 2 * deviation) \
            or (middle > 0 and pct > 2 * middle and pct - middle >= 2.0)
        return 'outlier' if far else 'normal'

    @api.model
    def _calib_column(self, rating, levels):
        """Which column a person is drawn in.

        A score the grid does not have — an old five on a four-level scale —
        is drawn at the top rather than off the right-hand edge, and a person
        nobody has scored is drawn in the MIDDLE with the chip on their row
        saying so. A mark outside the picture is a person the meeting cannot
        see.
        """
        column = int(rating or 0)
        if column < 1:
            column = max(1, (levels + 1) // 2)
        return min(max(column, 1), levels)

    @api.model
    def calibration(self, review_id):
        """The whole review as a shape: the score across, the rise up.

        EVERYBODY IS ON IT, AT ANY SIZE. This used to slice the first nine
        hundred people and say so on the screen, which is the one sentence
        LOOK rule 16 forbids on the one screen where it matters most — a
        calibration meeting is a meeting about the people at the edges, and a
        cap silently removes an arbitrary set of them. The picture now changes
        SHAPE instead, exactly as the band picture does: along each score's
        column the rise axis is cut into bins a few pixels tall, a bin holding
        a handful of people draws each of them, and a busier one draws a bar
        that says how many.

        WHAT COMES BACK IS WHAT THE PICTURE DRAWS WITH, AND NOTHING ELSE.
        `people` carries four things per row and no name: names and details
        are read back for ONE bin on demand (`calibration_people`) and for the
        handful of rises worth arguing about (`outliers`). That is both a
        payload and a permission decision — at four and a half thousand
        people, sending everybody's name to draw a shape is neither.
        """
        started = time.time()
        self._require_read()
        review = self._review(review_id)
        can_names = self._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                              'hr.group_hr_manager', 'base.group_system')
        levels = int(review.rating_scale or '4')
        words = scale_words(review.rating_scale)
        money = self.env['pb.pay.bands']

        # ONE search_read of the four columns the shape is drawn from. Reading
        # `review.line_ids` and touching `employee_id.name` on every row is
        # what made somebody reach for a cap in the first place; there is no
        # many2one in this field list on purpose, because the platform
        # resolves one into `(id, display_name)` and that is a name lookup per
        # person. `chips` is a stored Json column and costs nothing.
        rows = self._wide().env['pb.pay.review.line'].search_read(
            [('review_id', '=', review.id)],
            ['rating', 'proposal_pct', 'chips'], order='id')

        by_rating, stats = self._stats_by_rating(rows)
        people, standouts = [], []
        drawn_in_column = defaultdict(int)
        for row in rows:
            pct = round(float(row['proposal_pct'] or 0.0), 2)
            column = self._calib_column(row['rating'], levels)
            state = self._calib_state(row, stats)
            drawn_in_column[column] += 1
            people.append({'line_id': row['id'], 'column': column,
                           'pct': pct, 'state': state})
            if state != 'normal':
                standouts.append((pct, row['id'], state))

        # ------------------------------------------------ one row per score
        columns = []
        for index in range(1, levels + 1):
            values = by_rating.get(index) or []
            middle = money._median(values) if values else 0.0
            columns.append({
                'column': index,
                'rating': index,
                'word': words[index - 1] if index - 1 < len(words)
                else str(index),
                # HOW MANY HOLD THIS SCORE, and how many marks the column
                # draws. They differ by exactly the people nobody has scored,
                # who are drawn in the middle column — so both figures are
                # here rather than one of them silently standing for the
                # other.
                'scored': len(values),
                'drawn': drawn_in_column.get(index, 0),
                'unscored': max(0, drawn_in_column.get(index, 0)
                                - len(values)),
                'has_median': bool(values),
                'median': round(middle, 2),
                'median_label': _("middle of this score %(pct)s%%",
                                  pct=('%g' % round(middle, 2)))
                if values else '',
            })

        # ----------------------------------------- the limits that can be drawn
        limits = []
        for limit in review.limit_ids:
            if limit.kind != 'max_raise_pct':
                continue
            summary = limit.summary()
            summary['value'] = float(summary.get('value') or 0.0)
            summary['label'] = '%g%%' % summary['value']
            limits.append(summary)
        limits.sort(key=lambda one: one['value'])

        # A limit drawn off the top of the picture explains nothing, so the
        # axis reaches past the highest one with room for its own line.
        highest = max([person['pct'] for person in people] or [0.0])
        ceiling = max([one['value'] for one in limits] or [0.0])
        top = max(highest, 1.0)
        if ceiling >= top:
            top = ceiling * 1.08

        # ------------------------------------------ worth a second look (LIST)
        standouts.sort(key=lambda one: (-one[0], one[1]))
        listed = standouts[:OUTLIER_ROWS]
        found = {line.id: line for line in
                 self._wide().env['pb.pay.review.line'].browse(
                     [one[1] for one in listed])}
        outliers = []
        for pct, line_id, state in listed:
            line = found.get(line_id)
            if not line:
                continue
            outliers.append({
                'line_id': line_id,
                'name': self._safe(
                    lambda one=line: one.employee_id.name or '', default='')
                if can_names else _('Person %(number)s', number=line_id),
                # Reading one field of a person reads forty on this build, a
                # good many of them behind payroll roles (RIZE R56), so every
                # extra on this row answers for itself: a row that loses its
                # team is still a row a meeting can act on.
                'team': self._safe(
                    lambda one=line: one.department_id.display_name or '',
                    default='') or '',
                'rating': int(line.rating or 0),
                'column': self._calib_column(line.rating, levels),
                'pct': pct,
                'state': state,
                'state_word': self._state_word(state),
                'cost_label': self._safe(
                    lambda one=line: money._short(
                        one.annual_cost_delta,
                        one.currency_id or review.currency_id),
                    default='') or '',
                # The row's OWN sentence about the limit it breaks
                # ("14.7% is above the 12% this review allows"), not a second
                # sentence repeating the chip printed beside it.
                'why': self._blocked_why(line) if state == 'blocked'
                else _("Much bigger than the others who scored the same."),
            })
        more = max(0, len(standouts) - len(listed))

        # A picture of a review nobody has touched is one line per score,
        # because every row still holds exactly what the guidance suggested.
        # That is TRUE and it looks broken, so the screen says which it is.
        spread = {person['pct'] for person in people}
        flat = bool(people) and len(spread) <= max(1, len(by_rating))
        return {
            'people': people,
            'total': len(people),
            'columns': columns,
            'limits': limits,
            'outliers': outliers,
            'outliers_total': len(standouts),
            'outliers_more': more,
            'outliers_note': _(
                "%(count)s more rises stand out. Every one of them is on the "
                "picture; the biggest %(shown)s are named here.",
                count=more, shown=len(listed)) if more else '',
            'flat': flat,
            'flat_note': _(
                "Everybody is still on the guidance, so each score sits on "
                "one line. Move a mark, or change a row in the worksheet, and "
                "the picture spreads out.") if flat else '',
            'levels': levels,
            'words': words,
            'max_pct': top,
            'can_names': can_names,
            'card': self._card(review),
            'empty_title': _("Nobody is in this review yet.")
            if not people else '',
            'empty_note': _(
                "A review draws the people it covers as soon as it has any. "
                "Go back to the worksheet and check who this one is for.")
            if not people else '',
            'ms': int((time.time() - started) * 1000),
        }

    @api.model
    def _blocked_why(self, line):
        for chip in (line.chips or []):
            if isinstance(chip, dict) and chip.get('blocks') \
                    and chip.get('text'):
                return chip['text']
        return _("This rise breaks a limit.")

    @api.model
    def _state_word(self, state):
        """The WORD beside the colour, always. A picture whose whole meaning
        is a hue is unreadable to a good number of readers."""
        if state == 'blocked':
            return _("breaks a limit")
        if state == 'outlier':
            return _("stands out")
        return _("in line with the others")

    @api.model
    def calibration_people(self, review_id, rating, low, high,
                           limit=PEOPLE_IN_BIN):
        """The named people standing in ONE bin of one score's column.

        The half of the picture a shape cannot draw. A bar says HOW MANY and
        never WHO, so a bar is a button and pressing it asks this — the same
        gesture, the same shape of answer and the same list cap as the band
        picture's `pb.pay.bands.people_between`.

        `rating` is the COLUMN that was pressed, which is a score on the
        scale; a person nobody has scored is drawn in the middle column and is
        found there, exactly as the picture draws them.
        """
        blank = {'allowed': False, 'total': 0, 'rows': [], 'more': 0,
                 'more_label': '', 'title': '', 'can_names': False}
        self._require_read()
        review = self._review(review_id)
        can_names = self._has(GROUP_MANAGER, GROUP_FINANCE, GROUP_CEO,
                              'hr.group_hr_manager', 'base.group_system')
        levels = int(review.rating_scale or '4')
        column = min(max(int(rating or 0), 1), levels)
        low, high = float(low or 0.0), float(high or 0.0)
        if high < low:
            low, high = high, low

        rows = self._wide().env['pb.pay.review.line'].search_read(
            [('review_id', '=', review.id)],
            ['rating', 'proposal_pct', 'chips'], order='id')
        _by_rating, stats = self._stats_by_rating(rows)
        top = max([round(float(row['proposal_pct'] or 0.0), 2)
                   for row in rows] or [0.0])
        for one in review.limit_ids:
            if one.kind == 'max_raise_pct':
                top = max(top, float(one.value or 0.0) * 1.08)
        top = max(top, 1.0)
        # A bin is HALF-OPEN, exactly as the picture's own binning is, or a
        # person standing on a boundary is listed under two bars. The two ends
        # of the axis are the exception: somebody paid beyond either end is
        # drawn ON that end, so the first and last bins are closed.
        lowest = low <= 1e-9
        highest = high >= top - 1e-9

        wanted = []
        for row in rows:
            if self._calib_column(row['rating'], levels) != column:
                continue
            pct = round(float(row['proposal_pct'] or 0.0), 2)
            if not lowest and pct < low:
                continue
            if not highest and pct >= high:
                continue
            wanted.append((pct, row))
        if not wanted:
            return dict(blank, allowed=True, title=_("Nobody is standing here"))

        wanted.sort(key=lambda one: (-one[0], one[1]['id']))
        limit = max(1, min(int(limit or PEOPLE_IN_BIN), PEOPLE_IN_BIN))
        listed = wanted[:limit]
        found = {line.id: line for line in
                 self._wide().env['pb.pay.review.line'].browse(
                     [row['id'] for _pct, row in listed])}
        money = self.env['pb.pay.bands']
        out = []
        for pct, row in listed:
            line = found.get(row['id'])
            if not line:
                continue
            state = self._calib_state(row, stats)
            out.append({
                'id': line.id,
                'name': self._safe(
                    lambda one=line: one.employee_id.name or '', default='')
                if can_names else _('Person %(number)s', number=line.id),
                'job': self._safe(
                    lambda one=line: one.job_id.display_name or '',
                    default='') or '',
                'team': self._safe(
                    lambda one=line: one.department_id.display_name or '',
                    default='') or '',
                'pct': pct,
                'pct_label': '%g%%' % pct,
                'state': state,
                'state_word': self._state_word(state),
                'new_label': self._safe(
                    lambda one=line: money._money(
                        one.new_wage,
                        one.currency_id or review.currency_id),
                    default='') or '',
            })
        more = max(0, len(wanted) - len(listed))
        edges = self._pct_pair(low, high)
        word = scale_words(review.rating_scale)
        return {
            'allowed': True,
            'can_names': can_names,
            'column': column,
            'low': low, 'high': high,
            'total': len(wanted),
            'rows': out,
            'more': more,
            'more_label': _("and %(count)s more standing here.", count=more)
            if more else '',
            'title': _("%(people)s scored %(word)s, rising %(low)s%% to "
                       "%(high)s%%",
                       people=money._people_phrase(len(wanted)),
                       word=word[column - 1] if column - 1 < len(word)
                       else str(column),
                       low=edges[0], high=edges[1]),
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
