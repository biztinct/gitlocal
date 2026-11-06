# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""MEHOME M2 — the Pay, Leave and This week cards, the grid, motion and font.

Numbered after the handover (docs/handovers/mehome/M2_HANDOVER.md §Numbered
tests). The card tests render the templates with a payload built here, so they
assert on the words and numbers the template draws, not on what the bench
clone happens to hold; the server test seeds its own attendance.
"""
import ast
import os
import re
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCSS = os.path.join(_HERE, 'static', 'src', 'scss', 'me_portal.scss')
_TEMPLATES = os.path.join(_HERE, 'views', 'portal_templates.xml')
_MANIFEST = os.path.join(_HERE, '__manifest__.py')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _scss_code():
    """The stylesheet without its comments (words in a comment are not CSS)."""
    src = re.sub(r'/\*.*?\*/', '', _read(_SCSS), flags=re.S)
    return re.sub(r'(?m)//.*$', '', src)


def _block(src, head):
    """The `{ … }` body that follows the first occurrence of `head`."""
    start = src.index(head)
    i = src.index('{', start)
    depth, j = 0, i
    while True:
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
        j += 1


def _make_user(env, login, name, password=None):
    vals = {'name': name, 'login': login,
            'group_ids': [(6, 0, [env.ref('base.group_user').id])]}
    if password:
        vals['password'] = password
    return env['res.users'].with_context(no_reset_password=True).create(vals)


def _doc(markup):
    return lxml_html.fromstring('<div>%s</div>' % markup)


def _text(node):
    return re.sub(r'\s+', ' ', node.text_content()).strip()


@tagged('post_install', '-at_install')
class TestMeHomeCards(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.QWeb = cls.env['ir.qweb'].with_context(lang='en_US')

    def _render(self, xmlid, home):
        return str(self.QWeb._render('pb_me_portal.%s' % xmlid, {'pbme_home': home}))

    # ------------------------------------------------------------ builders
    def _pay(self, nets=(27250000.0, 28450000.0, 26100000.0), *, explain=True,
             next_pay=None, paid_on=None):
        trend = [{'month_date': date(2026, 4 + i, 28), 'net': n}
                 for i, n in enumerate(nets)]
        last = trend[-1]
        return {
            'count': len(nets),
            'next_pay_date': next_pay,
            'next_pay_days': None,
            'explain_url': '/my/pay' if explain else None,
            'list_url': '/my/payslips',
            'last': {'id': 1, 'period_date': last['month_date'], 'net': last['net'],
                     'currency_id': self.vnd.id, 'currency': self.vnd,
                     'pdf_url': '/my/payslips/1?report_type=pdf&download=true',
                     'view_url': '/my/payslips/1', 'paid_on': paid_on},
            'previous_net': trend[-2]['net'] if len(trend) > 1 else None,
            'trend': trend,
        }

    def _leave(self, left, allocated, *, low=False, pending=0):
        return {'left': left, 'allocated': allocated, 'booked_pending': pending,
                'low': low, 'types': 1, 'url': '/my/work/leave'}

    def _week(self, *, pending=3, worked=16.0, all_off=False):
        monday = date(2026, 10, 12)
        plan = [('acked', '9–18', 1), ('pending', '9–18', 1), ('pending', '13–21', 2),
                ('pending', '9–13', 1), ('leave', None, 0), ('off', None, 0),
                ('off', None, 0)]
        days = []
        for i, (state, short, n) in enumerate(plan):
            if all_off:
                state, short, n = 'off', None, 0
            d = monday + timedelta(days=i)
            days.append({'date': d, 'is_today': i == 1, 'label': d.strftime('%a'),
                         'day_num': d.day, 'shift': short and short.replace('–', ':00–') + ':00',
                         'shift_short': short, 'shifts': n, 'state': state})
        return {'days': days, 'pending': 0 if all_off else pending,
                'hours_label': '38 h scheduled', 'scheduled_h': 0.0 if all_off else 38.0,
                'worked_h': worked, 'url': '/my/work/schedule'}

    # ------------------------------------------------------------ test 1
    def test_01_pay_card(self):
        out = self._render('pbme_card_pay', {'pay': self._pay()})
        doc = _doc(out)
        big = doc.xpath('//div[contains(@class, "pbme-pay-big")]')
        self.assertEqual(len(big), 1)
        self.assertIn(self.vnd.symbol, _text(big[0]), "the monetary widget drew the figure")
        self.assertTrue(big[0].xpath('.//span[contains(@class, "oe_currency_value")]'))
        # last 26.1 M after 28.45 M → "less than"
        delta = doc.xpath('//p[contains(@class, "pbme-pay-delta")]')
        self.assertEqual(len(delta), 1)
        self.assertIn('less than', _text(delta[0]))
        self.assertIn('May', _text(delta[0]), "the previous slip's month")
        self.assertIn(self.vnd.symbol, _text(delta[0]))
        more = _doc(self._render('pbme_card_pay', {'pay': self._pay((26100000.0, 28450000.0))}))
        self.assertIn('more than', _text(more.xpath('//p[contains(@class, "pbme-pay-delta")]')[0]))
        same = _doc(self._render('pbme_card_pay', {'pay': self._pay((28450000.0, 28450000.0))}))
        self.assertIn('Same as', _text(same.xpath('//p[contains(@class, "pbme-pay-delta")]')[0]))
        one = _doc(self._render('pbme_card_pay', {'pay': self._pay((28450000.0,))}))
        self.assertFalse(one.xpath('//p[contains(@class, "pbme-pay-delta")]'),
                         "no delta line without a previous slip")
        self.assertEqual(len(one.xpath('//i[contains(@class, "pbme-bar")]')), 1,
                         "one bar still draws with one paid month")
        # six bars, heights proportional to the highest net (= 100 %)
        nets = (24.0, 25.0, 23.5, 26.0, 28.45, 26.1)
        six = _doc(self._render('pbme_card_pay', {'pay': self._pay(tuple(n * 1e6 for n in nets))}))
        bars = six.xpath('//i[contains(@class, "pbme-bar")]')
        self.assertEqual(len(bars), 6)
        heights = [float(re.search(r'--pbme-h:\s*([\d.]+)%', b.get('style')).group(1)) for b in bars]
        top = max(nets)
        self.assertEqual(heights, [round(n * 100.0 / top, 1) for n in nets])
        self.assertEqual(max(heights), 100.0)
        self.assertEqual(['is-cur' in b.get('class') for b in bars], [False] * 5 + [True])
        self.assertEqual(len(six.xpath('//div[contains(@class, "pbme-bars-x")]/span')), 6)
        # the doors
        self.assertIn('Explain my pay', out)
        pdf = doc.xpath('//a[contains(@class, "pbme-btn--pri")]')
        self.assertEqual(len(pdf), 1)
        self.assertEqual(pdf[0].get('href'), '/my/payslips/1?report_type=pdf&download=true')
        self.assertIn('Payslip PDF', _text(pdf[0]))
        self.assertEqual(doc.xpath('//a[contains(@class, "pbme-lab-link")]/@href'), ['/my/payslips'])
        self.assertNotIn('Explain my pay',
                         self._render('pbme_card_pay', {'pay': self._pay(explain=False)}))
        # footer: next pay, else paid on, else nothing
        nxt = self._render('pbme_card_pay', {'pay': self._pay(next_pay=date(2026, 10, 30))})
        self.assertIn('Next pay', nxt)
        self.assertIn('Friday 30 October', nxt)
        paid = self._render('pbme_card_pay', {'pay': self._pay(paid_on=date(2026, 9, 30))})
        self.assertIn('Paid on', paid)
        self.assertIn('Wednesday 30 September', paid)
        self.assertNotIn('Next pay', out)
        self.assertNotIn('Paid on', out)
        # the label names the month of the last slip
        self.assertIn('Last pay', out)
        self.assertEqual(_text(doc.xpath('//h2[@id="pbme-pay-h"]')[0]), 'Last pay · June')

    # ------------------------------------------------------------ test 2
    def test_02_pay_empty_state(self):
        empty = {'count': 0, 'next_pay_date': date(2026, 10, 30), 'next_pay_days': 16,
                 'explain_url': '/my/pay', 'list_url': '/my/payslips'}
        out = self._render('pbme_card_pay', {'pay': empty})
        self.assertIn('No payslips yet', out)
        self.assertIn('Your first payslip appears here once payroll runs', out)
        self.assertNotIn('pbme-bar', out)
        self.assertNotIn('Payslip PDF', out)
        self.assertIn('Next pay', out)
        self.assertIn('All payslips', out)
        empty['next_pay_date'] = None
        self.assertNotIn('Next pay', self._render('pbme_card_pay', {'pay': empty}))
        # guard: no pay section at all still draws the card, empty
        self.assertIn('No payslips yet', self._render('pbme_card_pay', {'pay': None}))

    # ------------------------------------------------------------ test 3
    def test_03_leave_card(self):
        out = self._render('pbme_card_leave', {'leave': self._leave(9.5, 20.0, pending=1)})
        ring = _doc(out).xpath('//div[contains(@class, "pbme-ring")]')
        self.assertEqual(len(ring), 1)
        self.assertRegex(ring[0].get('style'), r'--pbme-pct:\s*47\.5%')
        self.assertNotIn('is-low', ring[0].get('class'))
        self.assertIn('9.5', _text(ring[0]))
        self.assertIn('days left', _text(ring[0]))
        self.assertEqual(_text(_doc(out).xpath('//p[@class="pbme-leave-cap"]')[0]),
                         'of 20 allocated · 1 request waiting')
        self.assertIn('Request time off', out)
        # nothing taken yet: never a full ring
        full = self._render('pbme_card_leave', {'leave': self._leave(20.0, 20.0)})
        self.assertRegex(full, r'--pbme-pct:\s*0%')
        self.assertIn('None taken yet', full)
        self.assertIn('>20<', full.replace(' ', ''))
        # amber when low
        low = self._render('pbme_card_leave', {'leave': self._leave(1.0, 12.0, low=True)})
        self.assertIn('pbme-ring is-low', low)
        self.assertIn('day left', low)
        # empty state
        none = self._render('pbme_card_leave', {'leave': self._leave(0.0, 0.0)})
        self.assertIn('No leave allocated yet', none)
        self.assertIn('Open My Leave', none)
        self.assertNotIn('pbme-ring', none)
        # absent source: no card at all
        self.assertNotIn('pbme-b-leave', self._render('pbme_card_leave', {'leave': None}))

    def test_03b_bento_without_leave_and_week(self):
        home = {'pay': self._pay(), 'leave': None, 'week': None, 'needs_you': []}
        out = self._render('pbme_bento', home)
        doc = _doc(out)
        self.assertNotIn('pbme-b-leave', out)
        self.assertNotIn('pbme-b-week', out)
        bento = doc.xpath('//div[contains(@class, "pbme-bento")]')[0]
        self.assertIn('pbme-bento--no-leave', bento.get('class'))
        self.assertIn('pbme-bento--no-week', bento.get('class'))
        # ... and the stylesheet puts Needs you at cols 6–12, row 1 for it
        desk = _block(_scss_code(), '@container (min-width: 1000px)')
        self.assertRegex(desk, r'\.pbme-bento--no-leave\.pbme-bento--no-week \.pbme-b-needs\s*\{\s*'
                               r'grid-column:\s*6 / 13;\s*grid-row:\s*1 / 2;')
        # only Leave absent: This week widens to cols 6–12 rows 1–2
        out = self._render('pbme_bento', dict(home, week=self._week()))
        bento = _doc(out).xpath('//div[contains(@class, "pbme-bento")]')[0]
        self.assertIn('pbme-bento--no-leave', bento.get('class'))
        self.assertNotIn('pbme-bento--no-week', bento.get('class'))
        self.assertRegex(desk, r'\.pbme-bento--no-leave \.pbme-b-week,\s*'
                               r'\.pbme-home \.pbme-bento--no-week \.pbme-b-leave\s*\{\s*'
                               r'grid-column:\s*6 / 13;\s*grid-row:\s*1 / 3;')

    # ------------------------------------------------------------ test 4
    def test_04_week_card(self):
        out = self._render('pbme_card_week', {'week': self._week()})
        doc = _doc(out)
        cells = doc.xpath('//li[contains(@class, "pbme-day")]')
        self.assertEqual(len(cells), 7)
        states = [re.search(r'is-(acked|pending|leave|off)', c.get('class')).group(1) for c in cells]
        self.assertEqual(states, ['acked', 'pending', 'pending', 'pending', 'leave', 'off', 'off'])
        self.assertEqual(len(doc.xpath('//li[contains(@class, "is-today")]')), 1)
        self.assertIn('is-today', cells[1].get('class'))
        self.assertIn('13–21 +1', _text(cells[2]), "two shifts: the first's hours + 1")
        self.assertIn('9–18', _text(cells[0]))
        self.assertEqual(_text(cells[4]).split()[-2:], ['On', 'leave'])
        self.assertIn('off', _text(cells[6]))
        self.assertEqual(cells[0].get('title'), '9:00–18:00')
        # the day name comes from the date, in the reader's language
        self.assertIn('Mon', _text(cells[0]))
        pill = doc.xpath('//span[contains(@class, "pbme-pill--amber")]')
        self.assertEqual(len(pill), 1)
        self.assertEqual(_text(pill[0]), '3 to confirm')
        btn = doc.xpath('//a[contains(@class, "pbme-btn")]')
        self.assertEqual(len(btn), 1)
        self.assertIn('pbme-btn--pri', btn[0].get('class'))
        self.assertEqual(_text(btn[0]), 'Confirm shifts')
        self.assertEqual(btn[0].get('href'), '/my/work/schedule')
        foot = _text(doc.xpath('//span[contains(@class, "pbme-week-h")]')[0])
        # the " · " is drawn by CSS (.pbme-week-worked::before) and said to a
        # screen reader by a visually hidden twin — never a translation term
        self.assertEqual(foot, '38 h scheduled · 16 h worked so far')
        self.assertTrue(doc.xpath('//span[@class="pbme-week-worked"]'))
        self.assertIn('.pbme-week-worked::before', _scss_code())
        # nothing waiting: no pill, outline "Open schedule"
        calm = _doc(self._render('pbme_card_week', {'week': self._week(pending=0, worked=None)}))
        self.assertFalse(calm.xpath('//span[contains(@class, "pbme-pill")]'))
        btn = calm.xpath('//a[contains(@class, "pbme-btn")]')[0]
        self.assertIn('pbme-btn--out', btn.get('class'))
        self.assertEqual(_text(btn), 'Open schedule')
        self.assertEqual(_text(calm.xpath('//span[contains(@class, "pbme-week-h")]')[0]),
                         '38 h scheduled')
        # an empty week still draws its seven cells
        off = _doc(self._render('pbme_card_week', {'week': self._week(all_off=True)}))
        self.assertEqual(len(off.xpath('//li[contains(@class, "is-off")]')), 7)
        self.assertEqual(_text(off.xpath('//span[contains(@class, "pbme-week-h")]')[0]),
                         'No shifts scheduled this week')
        self.assertIn('Open schedule', _text(off))
        self.assertNotIn('pbme-b-week', self._render('pbme_card_week', {'week': None}))

    def test_04b_week_worked_hours_from_the_timesheet(self):
        if 'pb.ess.workforce' not in self.env:
            self.skipTest('pb_ess_workforce is not installed on this database')
        user = _make_user(self.env, 'test_pbme_week', 'Week Person')
        emp = self.env['hr.employee'].create({
            'name': 'Week Person', 'user_id': user.id, 'company_id': self.env.company.id})
        Home = self.env['pb.me.home'].with_user(user)
        today = fields.Date.context_today(Home)
        monday = today - timedelta(days=today.weekday())
        start = datetime.combine(monday, time(0, 30))
        self.env['hr.attendance'].sudo().create({
            'employee_id': emp.id, 'check_in': start,
            'check_out': start + timedelta(hours=2)})
        self.env.flush_all()
        week = Home.get_home_data(emp)['week']
        self.assertIn('worked_h', week)
        totals = self.env['pb.ess.workforce'].with_user(user).get_my_week(
            monday.isoformat())['totals']
        self.assertEqual(week['worked_h'], round(totals['actual'], 1))
        self.assertGreater(week['worked_h'], 0)
        # the facade gives nothing → None, and the week card still draws
        Ess = type(self.env['pb.ess.workforce'])
        with patch.object(Ess, 'get_my_week', return_value={}):
            week = Home.get_home_data(emp)['week']
        self.assertIsNone(week['worked_h'])
        self.assertEqual(len(week['days']), 7)
        # compact hours for a narrow cell
        self.assertEqual(Home._pbme_hm_short('09:00'), '9')
        self.assertEqual(Home._pbme_hm_short('09:30'), '9:30')
        self.assertEqual(Home._pbme_hm_short('18:00'), '18')

    def test_04c_numbers_in_the_readers_language(self):
        Home = self.env['pb.me.home'].with_context(lang='en_US')
        self.assertEqual(Home.fmt_num(9.5), '9.5')
        self.assertEqual(Home.fmt_num(12.0), '12')
        self.assertEqual(Home.fmt_num(38), '38')
        self.assertEqual(Home.fmt_num(None), '')

    # ------------------------------------------------------------ test 5
    def test_05_grid(self):
        tpl = re.sub(r'<!--.*?-->', '', _read(_TEMPLATES), flags=re.S)
        bento = re.search(r'<template id="pbme_bento".*?</template>', tpl, re.S).group(0)
        marks = ['pb_me_portal.pbme_card_pay', 'pb_me_portal.pbme_card_leave',
                 'pb_me_portal.pbme_card_week', 'data-pbme-slot="needs"', 'data-pbme-slot="me"']
        pos = [bento.index(m) for m in marks]
        self.assertEqual(pos, sorted(pos), "slots in the order pay, leave, week, needs, me")
        home = {'pay': self._pay(), 'leave': self._leave(18.0, 20.0),
                'week': self._week(), 'needs_you': []}
        slots = _doc(self._render('pbme_bento', home)).xpath('//*[@data-pbme-slot]/@data-pbme-slot')
        self.assertEqual(slots, ['pay', 'leave', 'week', 'needs', 'me'])

        scss = _scss_code()
        desk = _block(scss, '@container (min-width: 1000px)')
        want = {'pay': ('1 / 6', '1 / 4'), 'leave': ('6 / 9', '1 / 3'),
                'week': ('9 / 13', '1 / 3'), 'needs': ('6 / 13', '3 / 4'),
                'me': ('1 / 13', '4 / 5')}
        for slot, (col, row) in want.items():
            self.assertRegex(desk, r'\.pbme-home \.pbme-b-%s\s*\{\s*grid-column:\s*%s;\s*'
                                   r'grid-row:\s*%s;' % (slot, re.escape(col), re.escape(row)), slot)
        # the three fallbacks: both absent (pay, needs, me), one absent
        for slot in ('pay', 'needs', 'me'):
            self.assertRegex(desk, r'\.pbme-bento--no-leave\.pbme-bento--no-week \.pbme-b-%s\s*\{'
                             % slot)
        self.assertIn('.pbme-bento--no-leave .pbme-b-week', desk)
        self.assertIn('.pbme-bento--no-week .pbme-b-leave', desk)
        self.assertIn('grid-auto-rows: minmax(84px, auto)', scss)
        # phone: one column, Pay → Needs you → This week → Leave → Me, in the
        # container query AND its media twin
        for head in ('@container (max-width: 700px)', '@media (max-width: 700px)'):
            phone = _block(scss, head)
            self.assertIn('flex-direction: column', phone, head)
            orders = {s: int(re.search(r'\.pbme-b-%s\s*\{\s*order:\s*(\d+)' % s, phone).group(1))
                      for s in ('pay', 'needs', 'week', 'leave', 'me')}
            self.assertEqual(sorted(orders, key=orders.get),
                             ['pay', 'needs', 'week', 'leave', 'me'], head)
            self.assertIn('.pbme-day-s', phone)

    # ------------------------------------------------------------ test 6
    def test_06_font(self):
        manifest = ast.literal_eval(_read(_MANIFEST))
        front = manifest['assets']['web.assets_frontend']
        fonts = 'pb_import_kit/static/src/scss/fonts.scss'
        tokens = 'pb_import_kit/static/src/scss/import_tokens.scss'
        self.assertIn(fonts, front)
        self.assertLess(front.index(fonts), front.index(tokens))
        self.assertEqual(manifest['version'], '19.0.3.4.0')
        kit = get_module_path('pb_import_kit')
        self.assertTrue(os.path.isfile(os.path.join(kit, 'static', 'fonts', 'InterVariable.woff2')))
        self.assertTrue(os.path.isfile(os.path.join(kit, 'static', 'fonts', 'Inter-OFL.txt')))
        face = _read(os.path.join(kit, 'static', 'src', 'scss', 'fonts.scss'))
        self.assertIn('font-weight: 100 900', face)
        self.assertIn('font-display: swap', face)

    # ------------------------------------------------------------ test 7
    def test_07_motion_and_clean_sources(self):
        scss = _scss_code()
        found = re.findall(r'[\w-]*gradient', scss)
        self.assertEqual(found, ['conic-gradient'], "the leave ring is the one two-tone")
        self.assertIn('conic-gradient', _block(scss, '.pbme-ring {'))
        reduced = _block(scss, '@media (prefers-reduced-motion: reduce)')
        for sel in ('.pbme-bento > .pbme-b', '.pbme-bar', '.pbme-ring'):
            self.assertIn(sel, reduced, sel)
        self.assertIn('animation: none', reduced)
        self.assertNotIn('pbme-reveal', reduced, "the reveal is not motion; it must survive")
        for name in ('pbme-enter', 'pbme-bar-grow', 'pbme-ring-fill', 'pbme-reveal'):
            self.assertIn('@keyframes %s' % name, scss, name)
        self.assertIn('animation: pbme-enter 320ms', scss)
        self.assertIn('animation: pbme-bar-grow 480ms', scss)
        self.assertIn('animation: pbme-ring-fill 600ms', scss)
        self.assertRegex(scss, r'&:not\(\.pbme-ready\) \.o_portal_docs \{ visibility: hidden; '
                               r'animation: pbme-reveal 0s 2s forwards; \}')
        prop = _block(scss, '@property --pbme-pct')
        self.assertIn("syntax: '<percentage>'", prop)
        self.assertIn('inherits: false', prop)
        self.assertIn('initial-value: 0%', prop)
        for delay, n in (('60ms', 2), ('120ms', 3), ('180ms', 4), ('240ms', 5)):
            self.assertIn('.pbme-b:nth-child(%s) { animation-delay: %s; }' % (n, delay), scss)


@tagged('post_install', '-at_install')
class TestMeHomeCardsPage(HttpCase):
    """The cards on the real page, over HTTP, as a new employee."""

    PASSWORD = 'pbme-cards-check-2026'

    def test_page_draws_the_cards(self):
        user = _make_user(self.env, 'test_pbme_cards', 'Card Person', password=self.PASSWORD)
        self.env['hr.employee'].create({'name': 'Card Person', 'user_id': user.id,
                                        'company_id': self.env.company.id})
        self.authenticate('test_pbme_cards', self.PASSWORD)
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        page = res.text
        self.assertIn('data-pbme-slot="pay"', page)
        self.assertIn('No payslips yet', page)
        if 'pb.ess.workforce' in self.env:
            self.assertIn('data-pbme-slot="leave"', page)
            self.assertIn('No leave allocated yet', page)
            self.assertIn('data-pbme-slot="week"', page)
            self.assertIn('No shifts scheduled this week', page)
        doc = lxml_html.fromstring(page)
        slots = doc.xpath('//*[@data-pbme-slot]/@data-pbme-slot')
        self.assertEqual(slots[0], 'pay')
        # TIERS T3b: cards other modules add (`_pbme_extra_cards`, e.g. the
        # notice board's) sit between Needs you and the Me strip
        self.assertEqual(slots[-1], 'me')
        extra = len(self.env['pb.me.home'].with_user(user)._pbme_extra_cards_safe(
            self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)))
        self.assertEqual(slots[-2 - extra], 'needs')
