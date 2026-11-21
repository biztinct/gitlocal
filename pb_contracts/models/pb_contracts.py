# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from odoo import _, api, models
from odoo.fields import Domain
from odoo.tools.translate import LazyTranslate

_logger = logging.getLogger(__name__)
# Lazy module-level words, read through `env._()` (LEARN REFRESH step 6).
_lt = LazyTranslate(__name__)

STATE_LABEL = {'draft': _lt('Draft'), 'open': _lt('Running'), 'close': _lt('Expired'),
               'cancel': _lt('Cancelled')}
#: One page of the roster (the filter panel pages it; "Show N more" appends).
PAGE_SIZE = 60
#: "Ending soon" = a running contract whose end date is within this many days.
ENDING_DAYS = 30
# state -> contextual next actions (label, icon, kind)
NEXT = {
    'draft': [('set_running', 'Set running', 'play', 'primary'),
              ('cancel', 'Cancel', 'x', 'danger')],
    'open':  [('renew', 'Renew', 'rotate', 'primary'),
              ('terminate', 'Terminate', 'x', 'danger')],
    'close': [('renew', 'Renew', 'rotate', 'primary')],
    'cancel': [('set_running', 'Re-activate', 'play', 'ghost')],
}
LIFECYCLE = {'set_running', 'terminate', 'cancel'}


def next_label(env, label):
    """A NEXT button's words in the reader's language: one `env._()` literal per
    label (a label inside a tuple is data and is never extracted)."""
    return {
        'Set running': env._("Set running"),
        'Cancel': env._("Cancel"),
        'Renew': env._("Renew"),
        'Terminate': env._("Terminate"),
        'Re-activate': env._("Re-activate"),
    }.get(label, label)


def _initials(name):
    parts = [p for p in (name or '').replace('-', ' ').split() if p]
    return ((parts[0][0] if parts else '?') + (parts[-1][0] if len(parts) > 1 else '')).upper()


class PbContracts(models.AbstractModel):
    _name = 'pb.contracts'
    _inherit = ['pb.filter.mixin']
    _description = 'Payobook contracts cockpit data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Contracts cockpit metric failed: %s", e)
            return default

    @api.model
    def _company_domain(self):
        company = self.env.company
        co_ids = self.env.companies.ids or [company.id]
        return [('company_id', 'in', co_ids)]

    @api.model
    def _step_domains(self):
        """Where a contract is, as domains (the strip, the figures and the
        filter panel's "Where it is" section all read these). Every running
        contract is at exactly one of `running` / `ending`, so the four steps
        add up; a cancelled contract is at no step."""
        today = date.today()
        soon = today + timedelta(days=ENDING_DAYS)
        return {
            'draft': [('state', '=', 'draft')],
            # running, and not ending within 30 days (open-ended, ends later,
            # or an end date already behind it while still marked running)
            'running': [('state', '=', 'open'), '|', '|', ('date_end', '=', False),
                        ('date_end', '<', str(today)), ('date_end', '>', str(soon))],
            'ending': [('state', '=', 'open'), ('date_end', '>=', str(today)),
                       ('date_end', '<=', str(soon))],
            'ended': [('state', '=', 'close')],
        }

    @api.model
    def get_board(self, step=None):
        """The numbers line, counted over every contract whatever is filtered.

        The roster itself is no longer here: the filter panel pages it through
        `get_contracts_page` (FILTER W1). `step` is accepted for old callers
        and ignored; `step_counts` stays for them (Learn's `get_board` refs).
        """
        C = self.env['hr.contract']
        company = self.env.company
        cur = company.currency_id
        DOM = self._company_domain()
        steps = self._step_domains()

        running = self._safe(lambda: C.search_count(DOM + [('state', '=', 'open')]))
        expired = self._safe(lambda: C.search_count(DOM + steps['ended']))
        draft = self._safe(lambda: C.search_count(DOM + steps['draft']))
        expiring = self._safe(lambda: C.search_count(DOM + steps['ending']))
        total_wage = 0.0
        try:
            g = C.read_group(DOM + [('state', '=', 'open')], ['wage:sum'], [])
            total_wage = (g and g[0].get('wage')) or 0.0
        except Exception:
            total_wage = 0.0
        avg_wage = round(total_wage / running) if running else 0
        # One total (and average) per currency: a group paying in several
        # never sees ₫ + Rp + ₹ added into one number. Soft: pb_people owns
        # the per-person currency and is not a dependency of this board.
        wage_totals = []
        People = self.env.get('pb.people')
        if People is not None and hasattr(People, '_wage_totals'):
            wage_totals = self._safe(
                lambda: People._wage_totals(DOM + [('state', '=', 'open')]), [])
        step_counts = {'draft': draft, 'ending': expiring, 'ended': expired,
                       'running': max(running - expiring, 0), 'open': running}

        return {
            'currency': cur.symbol or '',
            'kpis': {'running': running, 'expiring': expiring, 'expired': expired,
                     'draft': draft, 'total_wage': total_wage, 'avg_wage': avg_wage,
                     'wage_totals': wage_totals},
            'total': self._safe(lambda: C.search_count(DOM)),
            'step_counts': step_counts,
            # CD-1: the contract drawer's bundled read exists on this build, so
            # the list can offer it without probing for the method first.
            'has_360': True,
        }

    # ============================================================ filter panel
    # FILTER W1 (2026-10-31): the roster used to load the newest 240 contracts
    # and filter those in the browser, so a structure chip could say 1,900
    # while the list behind it held 40. Everything is now counted and paged on
    # the server for the panel's state (pb_filter_kit).

    def _pbf_model(self):
        return 'hr.contract'

    def _pbf_screen(self):
        return 'contracts'

    def _pbf_base_domain(self):
        return self._company_domain()

    def _pbf_search_fields(self):
        return ['name', 'employee_id.name', 'struct_id.name', 'job_id.name']

    def _pbf_layout_extra(self):
        return {'currency': self.env.company.currency_id.symbol or ''}

    def _pbf_sorts(self):
        return [
            {'key': 'newest', 'label': _('Newest start first'), 'order': 'date_start desc, id desc'},
            {'key': 'ending', 'label': _('Earliest end date first'),
             'order': 'date_end asc nulls last, id desc'},
            {'key': 'oldest', 'label': _('Oldest start first'), 'order': 'date_start asc, id asc'},
            {'key': 'person', 'label': _('Person, A to Z'), 'order': 'employee_id, id desc'},
            {'key': 'wage', 'label': _('Highest wage first'), 'order': 'wage desc, id desc'},
        ]

    def _pbf_spec(self):
        steps = self._step_domains()
        return [
            # ---- pinned: what is asked of a contract list first
            # A choice rather than the raw `state` selection: the stock label of
            # a draft contract is "New", while this board's tab, step and
            # figure all say "Draft" — the chip must use the board's words.
            {'key': 'status', 'label': _('Contract status'), 'icon': 'fileText',
             'group': 'contract', 'type': 'choice', 'pinned': True, 'requires': ['state'],
             'options': [
                 {'value': 'draft', 'label': _('Draft'), 'tone': 'blue',
                  'domain': [('state', '=', 'draft')]},
                 {'value': 'open', 'label': _('Running'), 'tone': 'green',
                  'domain': [('state', '=', 'open')]},
                 {'value': 'close', 'label': _('Expired'), 'tone': 'slate',
                  'domain': [('state', '=', 'close')]},
                 {'value': 'cancel', 'label': _('Cancelled'), 'tone': 'rose',
                  'domain': [('state', '=', 'cancel')]},
             ]},
            {'key': 'structure', 'label': _('Pay structure'), 'icon': 'sigma',
             'group': 'pay', 'type': 'many2one', 'path': 'struct_id', 'pinned': True,
             'none_label': _('No pay structure')},
            {'key': 'ends', 'label': _('Contract ends'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'date_end', 'pinned': True,
             'presets': 'future', 'none_label': _('No end date')},
            # ---- more filters
            {'key': 'step', 'label': _('Where it is'), 'icon': 'route',
             'group': 'contract', 'type': 'choice', 'requires': ['state', 'date_end'],
             'help': _('The steps above the list: running contracts ending within '
                       '30 days are "Ending soon", the rest are "Running".'),
             'options': [
                 {'value': 'draft', 'label': _('Draft'), 'tone': 'blue', 'domain': steps['draft']},
                 {'value': 'running', 'label': _('Running'), 'tone': 'green',
                  'domain': steps['running']},
                 {'value': 'ending', 'label': _('Ending within 30 days'), 'tone': 'amber',
                  'domain': steps['ending']},
                 {'value': 'ended', 'label': _('Ended'), 'tone': 'slate', 'domain': steps['ended']},
             ]},
            {'key': 'starts', 'label': _('Started'), 'icon': 'calendar',
             'group': 'dates', 'type': 'date', 'path': 'date_start', 'presets': 'past',
             'none_label': _('No start date')},
            {'key': 'department', 'label': _('Department'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'employee_id.department_id',
             'none_label': _('No department')},
            {'key': 'job', 'label': _('Job position'), 'icon': 'briefcase',
             'group': 'work', 'type': 'many2one', 'path': 'job_id',
             'none_label': _('No job position')},
            {'key': 'category', 'label': _('Contract category'), 'icon': 'tag',
             'group': 'contract', 'type': 'many2one', 'path': 'type_id',
             'none_label': _('No category')},
            {'key': 'wage', 'label': _('Monthly wage'), 'icon': 'banknote',
             'group': 'pay', 'type': 'number', 'path': 'wage', 'unit': 'money'},
            {'key': 'trial', 'label': _('Trial period ends'), 'icon': 'hourglass',
             'group': 'dates', 'type': 'date', 'path': 'trial_date_end', 'presets': 'future',
             'none_label': _('No trial period')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id'},
        ] + self._fillin_spec()

    # ================================================== FILLIN P2 — To check
    @api.model
    def _fillin_ready(self):
        """Does this database mark the answers Payobook fills in (FILLIN P1,
        `pb_hr_payroll_formula`)? Probed, never assumed: this module does not
        depend on the rules module."""
        Line = self.env.get('hr.contract.advantage')
        return Line is not None and 'pb_fill' in Line._fields \
            and 'pb_checked_at' in Line._fields

    @api.model
    def _fillin_domain(self):
        return [('advantages_ids', 'any', [('pb_fill', '=', 'auto'),
                                           ('pb_checked_at', '=', False)])]

    def _fillin_spec(self):
        """A hidden choice: never listed in the panel, switched on by the
        "To check" tab (and by the pay run's door), named by its chip."""
        if not self._fillin_ready():
            return []
        return [{'key': 'fillin', 'label': _('Answers to check'),
                 'icon': 'listChecks', 'group': 'contract', 'type': 'choice',
                 'hidden': True,
                 'options': [{'value': 'unchecked',
                              'label': _('Filled in by Payobook, not checked'),
                              'tone': 'amber',
                              'domain': self._fillin_domain()}]}]

    @api.model
    def _fillin_rows(self, contracts):
        """`{contract_id: {'n', 'answers': [{label, value_text}]}}` for the
        unchecked filled-in lines of a page of contracts — ONE search."""
        if not contracts or not self._fillin_ready():
            return {}
        lines = self.env['hr.contract.advantage'].sudo().search([
            ('contract_id', 'in', contracts.ids), ('pb_fill', '=', 'auto'),
            ('pb_checked_at', '=', False)])
        if not lines:
            return {}
        codes = list({l.advantage_template_id.code for l in lines} - {False})
        rules = self._safe(lambda: self._cd_rule_by_code(
            codes, company=self.env.company), default={})
        out = {}
        for line in lines.sorted(lambda l: ((l.advantage_template_id.code or ''),
                                             l.id)):
            rule = rules.get(line.advantage_template_id.code)
            word = ''
            if rule is not None and hasattr(rule, 'value_label_for'):
                word = self._safe(lambda: rule.value_label_for(line.amount),
                                  default='')
            entry = out.setdefault(line.contract_id.id, {'n': 0, 'answers': []})
            entry['n'] += 1
            entry['answers'].append({
                'label': (line.advantage_template_id.name
                          or (rule.name if rule else '')
                          or line.advantage_template_id.code or '—'),
                'value_text': word or self._cd_num(line.amount or 0.0),
            })
        return out

    @api.model
    def fillin_check_contract(self, contract_id):
        """"Looks right" on one card: confirm that contract's unchecked
        filled-in answers. The right is `pb_fillin_check`'s own."""
        contract = self._cd_contract(contract_id) if self._cd_may_read() \
            else None
        if contract is None:
            return {'ok': False, 'n': 0,
                    'msg': _("That contract is no longer here.")}
        if not self._cd_may_check():
            return {'ok': False, 'n': 0,
                    'msg': _("You cannot confirm the answers on a contract. "
                             "Ask an administrator for the right to change "
                             "contracts.")}
        try:
            n = contract.pb_fillin_check()
        except Exception as error:   # noqa: BLE001 — AccessError included
            return {'ok': False, 'n': 0, 'msg': self._cd_reason(error)}
        return {'ok': True, 'n': n,
                'msg': _("%(who)s: answers confirmed.") % {
                    'who': contract.employee_id.name or contract.name or ''}}

    @api.model
    def fillin_preview_all(self, filters=None, search=None):
        """What "All N look right" would confirm, for the confirm dialog: the
        count and the first five people, under the SAME filters as the list."""
        if not self._fillin_ready() or not self._cd_may_read():
            return {'n': 0, 'people': [], 'more': 0, 'can_check': False}
        filters = filters if isinstance(filters, dict) else {}
        domain = Domain.AND([Domain(self.pbf_domain(filters, search)),
                             Domain(self._fillin_domain())])
        C = self.env['hr.contract']
        n = C.search_count(domain)
        first = C.search(domain, order='employee_id, id', limit=5)
        return {'n': n,
                'people': [c.employee_id.name or c.name or '—' for c in first],
                'more': max(n - len(first), 0),
                'can_check': bool(n and self._cd_may_check())}

    @api.model
    def fillin_check_all(self, filters=None, search=None):
        """"All N look right": confirm every unchecked filled-in answer of the
        contracts the list shows right now (its filters AND search), in the
        caller's rights. Returns how many contracts."""
        if not self._fillin_ready():
            return {'ok': False, 'n': 0, 'lines': 0, 'msg': ''}
        self._cd_require_read()
        if not self._cd_may_check():
            return {'ok': False, 'n': 0, 'lines': 0,
                    'msg': _("You cannot confirm the answers on a contract. "
                             "Ask an administrator for the right to change "
                             "contracts.")}
        filters = filters if isinstance(filters, dict) else {}
        # The list's own domain, read with the caller's rights: nobody checks
        # a contract they cannot see.
        domain = Domain.AND([Domain(self.pbf_domain(filters, search)),
                             Domain(self._fillin_domain())])
        contracts = self.env['hr.contract'].search(domain)
        if not contracts:
            return {'ok': True, 'n': 0, 'lines': 0,
                    'msg': _("Nothing was left to check.")}
        try:
            lines = contracts.pb_fillin_check()
        except Exception as error:   # noqa: BLE001 — AccessError included
            return {'ok': False, 'n': 0, 'lines': 0,
                    'msg': self._cd_reason(error)}
        n = len(contracts)
        return {'ok': True, 'n': n, 'lines': lines,
                'msg': _("Checked 1 contract.") if n == 1 else
                _("Checked %s contracts.") % n}

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All contracts'), 'icon': 'fileText', 'filters': {}},
            {'key': 'running', 'label': _('Running'), 'filters': {'status': ['open']}},
            # FILLIN P2 B1 — the review list. Offered only where the marks
            # exist (a view naming a section the database lacks is dropped).
            {'key': 'fillin', 'label': _('To check'), 'icon': 'listChecks',
             'filters': {'fillin': ['unchecked']}},
            {'key': 'ending', 'label': _('Ending within 30 days'), 'filters': {'step': ['ending']}},
            {'key': 'draft', 'label': _('Draft'), 'filters': {'status': ['draft']}},
            {'key': 'started', 'label': _('Started this month'),
             'filters': {'starts': {'preset': 'this_month'}}},
        ]

    @api.model
    def _contract_row(self, c, today, pay_signs=None):
        dte = (c.date_end - today).days if c.date_end else None
        # the card's money sign is the person's pay-scheme currency (pb_people
        # owns it; soft, absent -> the board's company sign)
        People = self.env.get('pb.people')
        currency = (self._safe(lambda: People._pay_symbol(c.employee_id, pay_signs), '')
                    if People is not None and hasattr(People, '_pay_symbol')
                    and c.employee_id else '')
        return {
            'id': c.id, 'name': c.name or '—',
            'currency': currency,
            'employee': c.employee_id.name if c.employee_id else '—',
            'employee_id': c.employee_id.id if c.employee_id else False,
            'avatar': ('/web/image/hr.employee/%s/avatar_128' % c.employee_id.id) if c.employee_id else '',
            'state': c.state,
            'state_label': self.env._(STATE_LABEL[c.state]) if c.state in STATE_LABEL else c.state,
            'kanban_state': c.kanban_state,
            'wage': c.wage or 0.0,
            'date_start': str(c.date_start) if c.date_start else '',
            'date_end': str(c.date_end) if c.date_end else '',
            'days_to_expiry': dte,
            'structure': (c.struct_id.name if getattr(c, 'struct_id', False) else
                          (c.structure_type_id.name if c.structure_type_id else '')),
        }

    @api.model
    def _pbf_step_counts(self, filters, search):
        """The strip's counts for the panel's state: each step counted against
        every OTHER filter (the kit's rule), so the strip and the panel's
        "Where it is" section always say the same numbers."""
        spec = self._pbf_clean_spec()
        s = next((x for x in spec if x['key'] == 'step'), None)
        if not s:
            return {}
        res = self._pbf_count_section(s, filters or {}, search, spec)
        return {r['v']: r['n'] for r in res.get('values') or []}

    @api.model
    def get_contracts_page(self, filters=None, search=None, sort=None, offset=0, limit=PAGE_SIZE):
        """One page of the roster for the filter panel's current state, with
        the step strip's counts for the same state."""
        C = self.env['hr.contract']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'date_start desc, id desc'
        today = date.today()
        rows = []
        pay_signs = {}
        page = C.search(domain, order=order, offset=offset, limit=limit)
        # FILLIN P2 B2 — the answers to check, one search for the page
        fillin = self._safe(lambda: self._fillin_rows(page), default={})
        for c in page:
            try:
                row = self._contract_row(c, today, pay_signs)
                row['fillin'] = fillin.get(c.id) or {'n': 0, 'answers': []}
                rows.append(row)
            except Exception as ex:  # noqa: BLE001 — one bad card never blanks the list
                _logger.debug("Contract row failed: %s", ex)
        out = {'rows': rows, 'total': C.search_count(domain), 'offset': offset,
               'can_check': bool(fillin) and self._safe(self._cd_may_check,
                                                        default=False)}
        if not offset:
            out['steps'] = self._safe(lambda: self._pbf_step_counts(filters, search), default={})
        return out

    # ------------------------------------------------------------------ detail
    @api.model
    def get_contract_detail(self, contract_id):
        c = self.env['hr.contract'].browse(int(contract_id))
        if not c.exists():
            return {'error': _('Contract not found')}
        # SCHEMECTX: the same sign the drawer writes — the scheme that pays
        # the person, not whatever the company is filed under. This screen and
        # the drawer show one contract each, so they must agree to the letter.
        symbol = self._cd_symbol(c)
        today = date.today()
        e = c.employee_id
        dte = (c.date_end - today).days if c.date_end else None

        # tenure since start
        tenure_label = '—'
        if c.date_start:
            months = (today.year - c.date_start.year) * 12 + (today.month - c.date_start.month)
            if today.day < c.date_start.day:
                months -= 1
            months = max(months, 0)
            y, m = divmod(months, 12)
            tenure_label = (('%dy ' % y) if y else '') + ('%dm' % m) if (y or m) else '<1m'

        rail_state = {'draft': 'draft', 'open': 'running', 'close': 'expired',
                      'cancel': 'expired'}.get(c.state, 'draft')
        order = ['draft', 'running', 'expired']
        ci = order.index(rail_state)
        rail_lbl = {'draft': _('Draft'), 'running': _('Running'), 'expired': _('Expired')}
        pipeline = [{'key': s, 'label': rail_lbl[s], 'done': i < ci, 'current': i == ci}
                    for i, s in enumerate(order)]

        acts = [{'method': m, 'label': next_label(self.env, l), 'icon': i, 'kind': k} for (m, l, i, k) in NEXT.get(c.state, [])]

        return {
            'id': c.id, 'name': c.name or '—',
            'employee': e.name if e else '—', 'employee_id': e.id if e else False,
            'initials': _initials(e.name if e else ''),
            'avatar': ('/web/image/hr.employee/%s/avatar_256' % e.id) if e else '',
            'job': (e.job_id.name if (e and e.job_id) else ''),
            'dept': (c.department_id.name if c.department_id else ''),
            'structure': (c.struct_id.name if getattr(c, 'struct_id', False) else
                          (c.structure_type_id.name if c.structure_type_id else '')),
            'currency': symbol,
            'state': c.state, 'state_label': self.env._(STATE_LABEL[c.state]) if c.state in STATE_LABEL else c.state,
            'kanban_state': c.kanban_state,
            'wage': c.wage or 0.0,
            'date_start': str(c.date_start) if c.date_start else '',
            'date_end': str(c.date_end) if c.date_end else '',
            'trial_end': str(c.trial_date_end) if c.trial_date_end else '',
            'days_to_expiry': dte,
            'tenure_label': tenure_label,
            'pipeline': pipeline,
            'next_actions': acts,
            'error': None,
        }

    @api.model
    def run_contract_action(self, contract_id, method, value=None):
        c = self.env['hr.contract'].browse(int(contract_id))
        err = None
        if method not in LIFECYCLE:
            d = self.get_contract_detail(contract_id)
            d['error'] = 'Action not permitted'
            return d
        try:
            if method == 'set_running':
                c.write({'state': 'open'})
            elif method == 'terminate':
                vals = {'state': 'close'}
                if not c.date_end:
                    vals['date_end'] = value or str(date.today())
                elif value:
                    vals['date_end'] = value
                c.write(vals)
            elif method == 'cancel':
                c.write({'state': 'cancel'})
        except Exception as e:
            err = str(getattr(e, 'name', None) or e) or 'Action failed.'
            _logger.warning("Contract action %s failed: %s", method, e)
        detail = self.get_contract_detail(contract_id)
        detail['error'] = err
        return detail
