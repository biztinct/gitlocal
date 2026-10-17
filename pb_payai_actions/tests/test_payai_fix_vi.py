# -*- coding: utf-8 -*-
"""PAYAI FIX-1 cluster D — reading Vietnamese (and English dates) right.

P4 review findings vi-1 … vi-12, crit-3, test-5 and P3 wf-9. Every table is
the reviewer's own repro, before → after. Same rules as P1–P4: gates judged
for an explicit user (PA12), no AI provider reached, fixtures in 2031 (PA40),
other modules' fixtures reached through their module (PA56).
"""
import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.pb_payai_actions.payai import actions_red, i18n, registry, resolve, runner
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

_P3Case = p3._P3Case
VI = 'vi_VN'
#: The reviewers' "today".
TODAY = datetime.date(2026, 10, 13)


def _match(text):
    return registry.match(text)


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixVietnameseReading(_P3Case):
    """The phrase table and the date / month readers, as tables."""

    def _today(self):
        """`context_today` pinned to the reviewers' 13 Oct 2026."""
        p = patch.object(fields.Date, 'context_today',
                         lambda record, timestamp=None: TODAY)
        p.start()
        self.addCleanup(p.stop)

    def _day(self, text, lang='en_US'):
        token = i18n.set_lang(lang)
        try:
            day, origin, _label = resolve.parse_day(SimpleNamespace(env=self.env), text)
        finally:
            i18n.reset_lang(token)
        return day, origin

    # ------------------------------------------------------------- vi-1
    def test_vi1_a_question_never_starts_or_decides(self):
        for text in ('gửi phiếu lương tháng 6 chưa', 'chạy lương tháng 6 chưa',
                     'chạy lương tháng 6 chưa?', 'gửi duyệt bảng lương tháng 6 chưa',
                     'tính lương thế nào', 'tính lương tháng 6 bao nhiêu',
                     'chạy lương khi nào', 'duyệt bảng lương thế nào',
                     'Huy chạy lương tháng 6 chưa'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)
        # A status look asked the same way still answers it.
        for text in ('bảng lương tháng 6 thế nào', 'bảng lương tháng 6 ra sao',
                     'bảng lương tháng 6 sao rồi', 'đợt lương tháng 6 đang ở đâu',
                     'bảng lương tháng 6 đang ở đâu?'):
            got = _match(text)
            self.assertTrue(got and got[0] == 'run_status', '%s → %r' % (text, got))
        # A polite request is still a request.
        got = _match('chạy lương tháng 6 có được không')
        self.assertEqual(got, ('run_payroll', {'period': 'tháng 6'}))

    # ------------------------------------------------------------- vi-2
    def test_vi2_the_mark_on_sau_decides_june(self):
        nfd = __import__('unicodedata').normalize('NFD', 'tháng sáu')
        for text in ('tháng sáu', 'thang sáu', 'thàng sáu', 'Tháng Sáu', nfd):
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), (2026, 6), repr(text))
        self.assertEqual(resolve.parse_period('tháng sau', TODAY)[0], datetime.date(2026, 11, 1))
        self.assertEqual(resolve.sau_after_thang('chạy lương thang sau'), 'next')
        # No marks anywhere: June or next month? Asked, never assumed.
        self.assertEqual(resolve.sau_after_thang('thang sau'), 'unsure')
        self.assertIn('June or next month', resolve.period_problem('thang sau', TODAY))
        self.assertFalse(resolve.period_problem('tháng sau', TODAY))
        self._today()
        ctx = SimpleNamespace(env=self.env)
        self.assertEqual(resolve.resolve_period(ctx, 'thang sau')['status'], 'missing')
        self.assertEqual(resolve.resolve_period(ctx, 'thang sáu')['label'], 'June 2026')

    # ------------------------------------------------------------- vi-3
    def test_vi3_go_to_is_not_delete(self):
        for text, door in (('go to bảng lương', 'bảng lương'), ('go to phiếu lương', 'phiếu lương'),
                           ('go to Hồ sơ nhân viên', 'Hồ sơ nhân viên'), ('go to luong', 'luong')):
            self.assertEqual(_match(text), ('open_screen', {'door': door}), text)
        for text in ('gỡ bỏ hồ sơ nhân viên Lan', 'gỡ hợp đồng của Lan', 'go bo ho so nhan vien Lan',
                     'xoá bảng lương tháng 6'):
            self.assertEqual(_match(text)[0], 'never_destructive', text)

    # ------------------------------------------------------------- vi-4
    def test_vi4_names_that_are_also_forms_of_address(self):
        table = {
            'Chi': ['Chi'], 'chị Chi': ['Chi'], 'Lan Anh': ['Lan', 'Anh'],
            'anh Lan Anh': ['Lan', 'Anh'], 'nhân viên Chi': ['Chi'], 'Anh': ['Anh'],
            'cho chị Vũ Khánh Chi': ['Vũ', 'Khánh', 'Chi'], 'the employee Minh': ['Minh'],
            'Nguyễn Văn Nhân': ['Nguyễn', 'Văn', 'Nhân'],
        }
        for text, words in table.items():
            self.assertEqual(resolve.person_words(text), words, text)
        Emp = self.env['hr.employee']
        lan_anh = Emp.create({'name': 'Payai Lan Anh', 'company_id': self.company.id})
        chi = Emp.create({'name': 'Payai Chi', 'company_id': self.company.id})
        # Who may see whom is not under test here (the gate tests own it).
        ctx = SimpleNamespace(env=self.env)
        for text, emp in (('Payai Lan Anh', lan_anh), ('chị Payai Chi', chi),
                          ('Payai Chi', chi), ('nhân viên Payai Lan Anh', lan_anh)):
            got = resolve.resolve_person(ctx, text)
            self.assertEqual((got['status'], got['value'], got['origin']),
                             ('resolved', emp.id, 'said'), '%s → %r' % (text, got))

    # ------------------------------------------------------------- vi-5
    def test_vi5_has_it_been_sent_is_not_a_go_ahead(self):
        for text in ('Đã gửi đi', 'đã xác nhận', 'đã thực hiện', 'đã tiến hành', 'Đã gửi đi?',
                     'da gui di', 'ok', 'vâng'):
            self.assertFalse(runner.go_ahead_words(text), text)
        for text in ('dạ gửi đi', 'Dạ, tiến hành nhé', 'vâng, làm đi', 'ok làm đi', 'tiến hành',
                     'xác nhận', 'ừ làm đi', 'đồng ý, làm đi', 'go ahead', 'Yes, do it'):
            self.assertTrue(runner.go_ahead_words(text), text)

    # ------------------------------------------------------------- vi-6
    def test_vi6_effective_day_keeps_its_day(self):
        self._today()
        for text in ('15.11.2026', '15-11-2026', 'ngày 15.11.2026', 'ngày 15 tháng sau',
                     'ngày 15 tháng mười một', '15/11/2026', 'ngày 15 tháng 11'):
            self.assertEqual(self._day(text, VI), (datetime.date(2026, 11, 15), 'said'), text)
        # A day the month does not have is asked, never moved.
        self.assertEqual(self._day('31/2', VI)[0], None)
        self.assertEqual(self._day('31.11.2026', VI)[0], None)
        got = _match('đổi phụ cấp của Linh thành 500.000 từ ngày 15.11.2026')
        self.assertEqual(got[1]['from'], 'ngày 15.11.2026')

    # ------------------------------------------------------------- vi-7
    def test_vi7_raise_by_is_never_set_to(self):
        for text in ('tăng cho Linh phụ cấp thêm 500.000', 'tang cho Linh phu cap them 500.000',
                     'tăng phụ cấp thêm cho Linh lên 500.000', 'giảm cho Linh phụ cấp bớt 200.000',
                     'tăng cho Linh phụ cấp 500.000', 'giảm phụ cấp của Linh đi 200.000'):
            got = _match(text)
            self.assertFalse(got and got[0] == 'update_pay_data', '%s → %r' % (text, got))
        table = [
            ('cho Linh phụ cấp 500.000 từ tháng 7',
             {'person': 'Linh', 'field': 'phụ cấp', 'value': '500.000', 'from': 'tháng 7'}),
            ('tăng phụ cấp ăn trưa của Linh lên 500.000',
             {'person': 'Linh', 'field': 'phụ cấp ăn trưa', 'value': '500.000'}),
            ('tăng cho Linh phụ cấp ăn trưa lên 500.000',
             {'person': 'Linh', 'field': 'phụ cấp ăn trưa', 'value': '500.000'}),
            ('đổi phụ cấp làm thêm của Linh thành 300.000',
             {'person': 'Linh', 'field': 'phụ cấp làm thêm', 'value': '300.000'}),
        ]
        for text, slots in table:
            self.assertEqual(_match(text), ('update_pay_data', slots), text)

    # ------------------------------------------------------------- vi-8
    def test_vi8_short_orders_and_filler(self):
        for text in ('duyệt đi', 'duyệt nhé', 'duyệt giúp tôi', 'duyệt luôn'):
            self.assertEqual(_match(text), ('approve_item', {}), text)
        # The typed word alone is the card's confirmation, never a new request.
        for text in ('duyệt', 'DUYỆT', 'TRẢ LẠI', 'từ chối', 'tu choi'):
            self.assertIsNone(_match(text), text)
        table = [
            ('duyệt lại bảng lương tháng 6', 'approve_item', {'item': 'bảng lương tháng 6'}),
            ('từ chối duyệt bảng lương tháng 6', 'reject_item', {'item': 'bảng lương tháng 6'}),
            ('gửi bảng lương tháng 6 cho chị Hoa duyệt', 'submit_run', {'run': 'bảng lương tháng 6'}),
            ('gửi bảng lương tháng 6 sang trạng thái chờ duyệt', 'submit_run',
             {'run': 'bảng lương tháng 6'}),
            ('trợ giúp', 'what_can_you_do', {}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
        rest = resolve.parse_period('trạng thái duyệt bảng lương tháng 6', TODAY)[3]
        self.assertEqual(resolve.tokens(rest, resolve.RUN_STOP), [])

    # ------------------------------------------------------------- vi-9
    def test_vi9_marked_words_are_not_their_folded_twins(self):
        for text in ('Bắc Ninh tháng 6', 'Bạc Liêu tháng 6', 'bác sĩ Linh', 'trả lương về cho nhân viên',
                     'trả lời lại cho Linh', 'trả lại tiền thừa cho Linh'):
            self.assertIsNone(_match(text), text)
        # A person typing with no marks at all is still understood.
        for text, key in (('bac bo bang luong thang 6', 'reject_item'),
                          ('tra lai bang luong thang 6', 'send_back_item'),
                          ('huy bang luong thang 6', 'never_destructive'),
                          ('bác yêu cầu tăng ca của Lan', 'reject_item'),
                          ('trả bảng lương tháng 6 lại cho Lan vì sai số', 'send_back_item')):
            got = _match(text)
            self.assertTrue(got and got[0] == key, '%s → %r' % (text, got))

    # ------------------------------------------------------------ vi-10
    def test_vi10_year_words_and_month_counts(self):
        table = {
            'tháng 1 năm sau': (2027, 1), 'tháng 2 năm sau': (2027, 2), 'tháng 1 năm tới': (2027, 1),
            'tháng sáu năm ngoái': (2025, 6), 'tháng 6 năm trước': (2025, 6),
            'tháng này năm ngoái': (2025, 10), 'tháng 6 năm nay': (2026, 6),
            'tháng sau nữa': (2026, 12), 'hai tháng trước': (2026, 8), 'tháng trước nữa': (2026, 8),
            '2 tháng sau': (2026, 12), 'tháng qua': (2026, 9),
        }
        for text, ym in table.items():
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), ym, text)
            self.assertFalse(got[3].split(), '%s left %r' % (text, got[3]))

    # ------------------------------------------------------------ vi-11
    def test_vi11_a_reason_may_ask_why(self):
        table = [
            ('trả lại bảng lương tháng 6 vì không rõ tại sao tăng', 'send_back_item',
             'không rõ tại sao tăng'),
            ('từ chối bảng lương tháng 6 vì không biết làm sao giải thích', 'reject_item',
             'không biết làm sao giải thích'),
            ('trả lại bảng lương tháng 6 vì không rõ tính thế nào', 'send_back_item',
             'không rõ tính thế nào'),
        ]
        for text, key, reason in table:
            got = _match(text)
            self.assertTrue(got and got[0] == key and got[1].get('reason') == reason,
                            '%s → %r' % (text, got))
            self.assertFalse(registry.looks_like_question(text), text)
        for text in ('tại sao bảng lương tháng 6 bị trả lại?', 'làm sao để chạy lương?',
                     'phụ cấp ăn trưa là gì?', 'vì sao lương tháng 6 giảm'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)

    # ------------------------------------------------------------ vi-12
    def test_vi12_month_13_and_for_me(self):
        self.assertEqual(_match('chạy lương cho tôi'), ('run_payroll', {}))
        self.assertEqual(_match('chạy lương tháng 6 cho tôi'), ('run_payroll', {'period': 'tháng 6'}))
        self.assertIn('tháng 13', resolve.period_problem('tháng 13', TODAY))
        self.assertFalse(resolve.period_problem('tháng 12', TODAY))
        self._today()
        got = resolve.resolve_period(SimpleNamespace(env=self.env), 'tháng 13')
        self.assertEqual(got['status'], 'missing', got)
        self.assertNotEqual(got.get('origin'), 'default')

    # ----------------------------------------------------------- crit-3
    def test_crit3_slash_dates_follow_the_askers_language(self):
        self._today()
        # English (en_US writes 11/1/2026 for 1 November): month first.
        for text, day in (('11/1', datetime.date(2026, 11, 1)),
                          ('11/1/2026', datetime.date(2026, 11, 1)),
                          ('12/25', datetime.date(2026, 12, 25)),
                          ('13/1', datetime.date(2027, 1, 13))):      # only one way to read it
            self.assertEqual(self._day(text), (day, 'said'), text)
        # Vietnamese: day first.
        for text, day in (('1/11', datetime.date(2026, 11, 1)), ('11/1', datetime.date(2027, 1, 11)),
                          ('15/11/2026', datetime.date(2026, 11, 15))):
            self.assertEqual(self._day(text, VI), (day, 'said'), text)
        # A date with no year that would be months in the past is asked.
        for text, lang in (('6/3', 'en_US'), ('3/6', VI), ('1 June', 'en_US'), ('tháng 6', VI)):
            self.assertEqual(self._day(text, lang)[0], None, (text, lang))
        # Said with its year, a past date is what was said.
        self.assertEqual(self._day('1/6/2026', VI)[0], datetime.date(2026, 6, 1))

    # ----------------------------------------------------------- test-5
    def test_test5_parse_day_cases(self):
        self._today()
        table = [
            ('ngày 1 tháng 11 năm 2026', VI, datetime.date(2026, 11, 1), 'said'),
            ('1/11/2026', VI, datetime.date(2026, 11, 1), 'said'),
            ('tháng 11', VI, datetime.date(2026, 11, 1), 'said'),
            ('tháng này', VI, datetime.date(2026, 10, 1), 'said'),
            ('hôm nay', VI, TODAY, 'said'),
            ('', VI, TODAY, 'default'),
            ('1 November 2026', 'en_US', datetime.date(2026, 11, 1), 'said'),
            ('November 15', 'en_US', datetime.date(2026, 11, 15), 'said'),
            ('next month', 'en_US', datetime.date(2026, 11, 1), 'said'),
            ('2026-11-15', 'en_US', datetime.date(2026, 11, 15), 'said'),
        ]
        for text, lang, day, origin in table:
            self.assertEqual(self._day(text, lang), (day, origin), (text, lang))


    # ================================================ second pass (verifier)
    def test_vi1b_a_soft_word_after_the_question_word(self):
        """"… chưa ạ", "… thế nào vậy": the question word is read after the
        polite tail is cut, and the soft words after it are allowed."""
        for text in ('tính lương thế nào ạ', 'duyệt yêu cầu của Lan chưa ạ',
                     'gửi phiếu lương tháng 6 chưa ạ', 'gửi phiếu lương tháng 6 chưa nhé',
                     'chạy lương tháng 6 chưa vậy', 'chạy lương tháng 6 chưa nhỉ',
                     'chạy lương tháng 6 chưa bạn', 'gửi duyệt bảng lương tháng 6 chưa nhỉ',
                     'gửi phiếu lương tháng 6 khi nào vậy', 'tính lương tháng 6 như nào',
                     'gửi phiếu lương tháng 6 chưa, cảm ơn'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)
        for text in ('bảng lương tháng 6 thế nào ạ', 'bảng lương tháng 6 sao rồi vậy'):
            got = _match(text)
            self.assertEqual(got, ('run_status', {'run': 'bảng lương tháng 6'}), text)
        # An order with a soft ending stays an order.
        self.assertEqual(_match('duyệt bảng lương tháng 6 ạ'),
                         ('approve_item', {'item': 'bảng lương tháng 6'}))
        self.assertEqual(_match('trả lại bảng lương tháng 6 vì chưa đúng ạ'),
                         ('send_back_item', {'item': 'bảng lương tháng 6', 'reason': 'chưa đúng'}))
        # The family name Chua is not "chưa" (yet?).
        for text in ('Approve the leave for Chua', 'duyệt nghỉ phép của Chua'):
            self.assertFalse(registry.looks_like_question(text), text)
            self.assertEqual(_match(text)[0], 'approve_item', text)

    def test_vi4b_names_that_fold_to_little_words(self):
        """Minh / mình, Đặng / đang, Đỗ / đó, Thắng / tháng, Em / em: the
        name narrows a request or a run; the little word does not."""
        stop = actions_red.ITEM_STOP
        table = {
            'tăng ca của Minh': ['tang', 'ca', 'minh'],
            'nghỉ phép của Thắng': ['nghi', 'phep', 'thang'],
            'đơn của Đỗ Hùng': ['don', 'do', 'hung'],
            'yêu cầu đang chờ của Đặng': ['dang'],
            'tăng ca của mình': ['tang', 'ca'],
            'tang ca cua minh': ['tang', 'ca'],            # no marks: lower case is "mình"
            'tang ca cua Minh': ['tang', 'ca', 'minh'],    # a capital is a name
            'nghỉ phép cho Minh': ['nghi', 'phep', 'minh'],
            'cái đó': [],
        }
        for text, words in table.items():
            per, got, problem = resolve.item_query(text, TODAY, stop)
            self.assertEqual((got, problem), (words, ''), text)
        # The polite tail never cuts a name away.
        table = [
            ('gửi phiếu lương cho Minh', 'send_payslips', {'run': 'Minh'}),
            ('duyệt nghỉ phép cho Minh', 'approve_item', {'item': 'nghỉ phép cho Minh'}),
            ('duyệt nghỉ phép cho Minh nhé', 'approve_item', {'item': 'nghỉ phép cho Minh'}),
            ('duyệt yêu cầu tăng ca cho Minh', 'approve_item',
             {'item': 'yêu cầu tăng ca cho Minh'}),
            ('gửi phiếu lương cho Em', 'send_payslips', {'run': 'Em'}),
            ('chạy lương cho khối A', 'run_payroll', {'scheme': 'khối A'}),
            ('chạy lương tháng 6 cho mình nhé', 'run_payroll', {'period': 'tháng 6'}),
            ('chay luong thang 6 cho minh', 'run_payroll', {'period': 'thang 6'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
        self.assertEqual(resolve.drop_vi_filler('bảng lương của mình đang chờ'), 'bảng lương của chờ')
        self.assertEqual(resolve.drop_vi_filler('bảng lương của Minh'), 'bảng lương của Minh')
        self.assertNotIn('minh', resolve.RUN_STOP - resolve.NAME_LIKE)

    def test_vi12b_a_scheme_after_cho_and_unread_months(self):
        table = [
            ('chạy lương cho Bán lẻ', {'scheme': 'Bán lẻ'}),
            ('chạy lương tháng 6 cho Bán lẻ', {'period': 'tháng 6', 'scheme': 'Bán lẻ'}),
            ('chạy lương tháng 6, cho Bán lẻ', {'period': 'tháng 6', 'scheme': 'Bán lẻ'}),
            ('chạy lương hai tháng nữa', {'period': 'hai tháng nữa'}),
            ('chạy lương thôi', {}),
            ('chạy lương', {}),
        ]
        for text, slots in table:
            self.assertEqual(_match(text), ('run_payroll', slots), text)
        got = resolve.parse_period('hai tháng nữa', TODAY)
        self.assertEqual((got[0].year, got[0].month), (2026, 12))
        # The Red Actions' seam asks about a month it cannot read.
        for text in ('bảng lương tháng 13', 'duyet bang luong thang sau'):
            per, words, problem = resolve.item_query(text, TODAY, actions_red.ITEM_STOP)
            self.assertTrue(problem, text)
            self.assertEqual((per, words), (None, []), text)
        # A run or a team called "T15" is a name, never a bad month.
        for text in ('show the T15 run', 'T24 run', 'Team T15'):
            self.assertEqual(resolve.period_problem(text, TODAY), '', text)
        self.assertTrue(resolve.period_problem('month 14', TODAY))

    def test_vi10b_counted_months(self):
        table = {
            'hai tháng nữa': (2026, 12), '2 tháng nữa': (2026, 12), '13 tháng trước': (2025, 9),
            'mười hai tháng trước': (2025, 10), 'ba tháng tới': (2027, 1),
            '24 tháng trước': (2024, 10),
        }
        for text, ym in table.items():
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month, got[2]), ym + ('said',), text)
            self.assertFalse(got[3].split(), '%s left %r' % (text, got[3]))

    def test_vi6b_year_first_and_this_month(self):
        self._today()
        for text in ('2026-11-15', '2026/11/15', '2026.11.15', 'ngày 2026/11/15'):
            for lang in (VI, 'en_US'):
                self.assertEqual(self._day(text, lang), (datetime.date(2026, 11, 15), 'said'),
                                 (text, lang))
        self.assertEqual(self._day('2026/2/31', VI)[0], None)
        self.assertEqual(self._day('15 this month'), (datetime.date(2026, 10, 15), 'said'))
        self.assertEqual(self._day('the 15th of next month'), (datetime.date(2026, 11, 15), 'said'))

    def test_vi8b_a_reason_alone_and_who_is_asked(self):
        table = [
            ('từ chối vì sai số', 'reject_item', {'reason': 'sai số'}),
            ('trả lại vì sai số', 'send_back_item', {'reason': 'sai số'}),
            ('duyệt đi bạn', 'approve_item', {}),
            ('duyệt thôi', 'approve_item', {}),
            ('gửi bảng lương tháng 6 cho anh Nguyễn Văn Hoa duyệt', 'submit_run',
             {'run': 'bảng lương tháng 6'}),
            ('gửi bảng lương tháng 6 lên sếp duyệt', 'submit_run', {'run': 'bảng lương tháng 6'}),
            ('từ chối bảng lương tháng 6 vì sai số', 'reject_item',
             {'item': 'bảng lương tháng 6', 'reason': 'sai số'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)

    def test_vi9b_uncle_and_mixed_typing(self):
        # "bác" + a person is "uncle / aunt", never "turn down".
        for text in ('bác Hùng gửi bảng lương tháng 6 rồi', 'bác Lan nghỉ phép hôm nay',
                     'Huy chạy lương tháng 6', 'Huy gửi bảng lương tháng 6'):
            self.assertIsNone(_match(text), text)
        self.assertEqual(_match('bác yêu cầu của Lan'), ('reject_item', {'item': 'yêu cầu của Lan'}))
        self.assertEqual(_match('bác bảng lương tháng 6 vì sai số'),
                         ('reject_item', {'item': 'bảng lương tháng 6', 'reason': 'sai số'}))
        # Partly marked messages whose order words carry no marks still match.
        table = [
            ('duyet bảng lương tháng 6', 'approve_item', {'item': 'bảng lương tháng 6'}),
            ('chay luong tháng 6', 'run_payroll', {'period': 'tháng 6'}),
            ('tra lai bảng lương tháng 6', 'send_back_item', {'item': 'bảng lương tháng 6'}),
            ('doi phu cap an trua cua Vũ Khánh Chi thanh 500.000', 'update_pay_data',
             {'field': 'phu cap an trua', 'person': 'Vũ Khánh Chi', 'value': '500.000'}),
            ('tu choi bang luong thang 6 vì sai so', 'reject_item',
             {'item': 'bang luong thang 6', 'reason': 'sai so'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)

    # ================================================= third pass (verifier)
    def test_vi1c_more_question_endings(self):
        """"lúc nào / hôm nào" (when?), "… khi nào được", and a bare "hả /
        sao / à" at the end ask; a name after "của / for" is a name."""
        for text in ('chạy lương tháng 6 lúc nào', 'chạy lương tháng 6 hôm nào',
                     'gửi phiếu lương tháng 6 khi nào được', 'gửi phiếu lương tháng 6 lúc nào vậy',
                     'gửi phiếu lương tháng 6 hả', 'gửi phiếu lương tháng 6 hả bạn',
                     'duyệt yêu cầu của Lan hả', 'duyệt yêu cầu của Lan sao',
                     'duyệt bảng lương tháng 6 à', 'chạy lương tháng nào', 'duyệt cái nào',
                     'chay luong thang 6 ha'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)
        table = [
            ('approve leave for chua', 'approve_item', {'item': 'leave for chua'}),
            ('duyệt nghỉ phép của Hà', 'approve_item', {'item': 'nghỉ phép của Hà'}),
            ('duyet nghi phep cua ha', 'approve_item', {'item': 'nghi phep cua ha'}),
            ('duyệt nghỉ phép của Chu', 'approve_item', {'item': 'nghỉ phép của Chu'}),
            ('duyệt nghỉ phép của Sao', 'approve_item', {'item': 'nghỉ phép của Sao'}),
            ('duyệt bảng lương tháng 6 ạ', 'approve_item', {'item': 'bảng lương tháng 6'}),
            ('bảng lương tháng 6 thế nào hả', 'run_status', {'run': 'bảng lương tháng 6'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
        for text in ('approve leave for chua', 'duyệt nghỉ phép của Hà', 'duyet nghi phep cua ha'):
            self.assertFalse(registry.looks_like_question(text), text)

    def test_vi12c_show_me_and_for_you(self):
        table = [
            ('cho tôi xem bảng lương tháng 6', 'run_status', {'run': 'bảng lương tháng 6'}),
            ('cho toi xem bang luong thang 6', 'run_status', {'run': 'bang luong thang 6'}),
            ('chạy lương tháng 6 cho bạn', 'run_payroll', {'period': 'tháng 6'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
        got = _match('cho tôi biết lương tháng 6')
        self.assertFalse(got and got[0] == 'update_pay_data', got)

    def test_vi10c_year_words_counts_and_directions(self):
        table = {
            'tháng 1 sang năm': (2027, 1), 'năm tháng trước': (2026, 5),
            'tháng 1 năm sau nữa': (2028, 1), 'tháng sáu tới': (2027, 6), 'tháng 6 tới': (2027, 6),
            'tháng 6 tới đây': (2027, 6), 'tháng 6 vừa rồi': (2026, 6), 'tháng 11 vừa qua': (2025, 11),
            'tháng 6 này': (2026, 6), 'tháng 6 năm kia': (2024, 6), 'tháng 3 năm trước nữa': (2024, 3),
            'mười lăm tháng trước': (2025, 7),
        }
        for text, ym in table.items():
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), ym, text)
            self.assertFalse(got[3].split(), '%s left %r' % (text, got[3]))
        # "tới" / "qua" that do not end the month are "to" / "by".
        got = resolve.parse_period('tháng 11 qua email', TODAY)
        self.assertEqual((got[0].year, got[0].month, got[3].split()), (2026, 11, ['qua', 'email']))
        got = resolve.parse_period('tháng 6 tới nhân viên', TODAY)
        self.assertEqual((got[0].year, got[0].month), (2026, 6))

    def test_regression_parse_day_month_counts(self):
        """"6 tháng trước" is six months ago, never the 6th of last month."""
        self._today()
        table = [
            ('2 tháng trước', datetime.date(2026, 8, 1)), ('6 tháng trước', datetime.date(2026, 4, 1)),
            ('10 tháng trước', datetime.date(2025, 12, 1)), ('3 tháng tới', datetime.date(2027, 1, 1)),
            ('2 tháng sau', datetime.date(2026, 12, 1)), ('mười hai tháng nữa', datetime.date(2027, 10, 1)),
            ('13 tháng nữa', datetime.date(2027, 11, 1)), ('năm tháng trước', datetime.date(2026, 5, 1)),
            ('tháng sáu tới', datetime.date(2027, 6, 1)), ('ngày 5 tháng 1 sang năm', datetime.date(2027, 1, 5)),
            # A day is still a day.
            ('ngày 2 tháng trước', datetime.date(2026, 9, 2)), ('ngày 15 tháng sau', datetime.date(2026, 11, 15)),
            ('3 tháng 11', datetime.date(2026, 11, 3)),
        ]
        for text, day in table:
            for lang in (VI, 'en_US'):
                self.assertEqual(self._day(text, lang), (day, 'said'), (text, lang))
        got = _match('đổi phụ cấp của Linh thành 500.000 từ 6 tháng trước')
        self.assertEqual(self._day(got[1]['from'], VI), (datetime.date(2026, 4, 1), 'said'))

    def test_regression_a_name_at_the_end(self):
        """"của Bạn / Thôi / Luôn": a capital at the end is a name."""
        table = [
            ('duyệt nghỉ phép của Bạn', 'approve_item', {'item': 'nghỉ phép của Bạn'}),
            ('duyệt nghỉ phép của Thôi', 'approve_item', {'item': 'nghỉ phép của Thôi'}),
            ('duyệt nghỉ phép của Luôn', 'approve_item', {'item': 'nghỉ phép của Luôn'}),
            ('duyệt bảng lương tháng 6 luôn', 'approve_item', {'item': 'bảng lương tháng 6'}),
            ('duyệt đi bạn', 'approve_item', {}),
            ('DUYỆT ĐI BẠN', 'approve_item', {}),
            ('chạy lương thôi', 'run_payroll', {}),
            # Fourth pass: right after "của" the word says whose it is —
            # kept however it is typed (HEAD kept it too).
            ('duyệt nghỉ phép của bạn', 'approve_item', {'item': 'nghỉ phép của bạn'}),
            ('duyet nghi phep cua ban', 'approve_item', {'item': 'nghi phep cua ban'}),
            ('duyet nghi phep cua thoi', 'approve_item', {'item': 'nghi phep cua thoi'}),
            ('duyet nghi phep cua luon', 'approve_item', {'item': 'nghi phep cua luon'}),
            ('duyệt nghỉ phép của Luôn nhé', 'approve_item', {'item': 'nghỉ phép của Luôn'}),
            ('duyệt nghỉ phép của Lan đi bạn', 'approve_item', {'item': 'nghỉ phép của Lan'}),
            ('duyệt yêu cầu của Lan luôn', 'approve_item', {'item': 'yêu cầu của Lan'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
        # … and the Approvals narrowing keeps the capital name too (it was
        # dropped as "bạn" / "thôi" / "luôn").
        for text, words in (('nghỉ phép của Bạn', ['nghi', 'phep', 'ban']),
                            ('nghỉ phép của Thôi', ['nghi', 'phep', 'thoi']),
                            ('nghỉ phép của Luôn', ['nghi', 'phep', 'luon'])):
            per, got, problem = resolve.item_query(text, TODAY, actions_red.ITEM_STOP)
            self.assertEqual((got, problem), (words, ''), text)
        self.assertEqual(resolve.drop_vi_filler('Đang chờ của mình'), 'chờ của')

    def test_regression_mixed_typing_in_the_order_word(self):
        """A slip in the order word still decides; a different word does not."""
        table = [
            ('tu chối yêu cầu', 'reject_item', {'item': 'yêu cầu'}),
            ('Từ chói nghỉ phép của Lan', 'reject_item', {'item': 'nghỉ phép của Lan'}),
            ('Tư chối yêu cầu', 'reject_item', {'item': 'yêu cầu'}),
            ('huy bỏ phiếu lương', 'never_destructive', {'what': 'phiếu lương'}),
            ('huy bảng lương tháng 6', 'never_destructive', {'what': 'bảng lương tháng 6'}),
            ('Huy bảng lương tháng 6', 'never_destructive', {'what': 'bảng lương tháng 6'}),
            ('bac bang luong thang 6', 'reject_item', {'item': 'bang luong thang 6'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
        for text in ('Bắc bảng lương tháng 6', 'Trà lại bảng lương tháng 6',
                     'Đội phụ cấp của Linh thành 500.000', 'Huy chay luong thang 6',
                     'Bac Ninh thang 6', 'bac si Linh'):
            self.assertIsNone(_match(text), text)

    def test_regression_extra_in_a_pay_item_name(self):
        """"phụ cấp thêm giờ" (overtime allowance) is a name; "thêm 500.000"
        is a change BY."""
        table = [
            ('đổi phụ cấp thêm giờ của Linh thành 500.000',
             {'field': 'phụ cấp thêm giờ', 'person': 'Linh', 'value': '500.000'}),
            ('tăng phụ cấp thêm giờ của Linh lên 500.000',
             {'field': 'phụ cấp thêm giờ', 'person': 'Linh', 'value': '500.000'}),
            ('đổi thưởng thêm của Linh thành 1 triệu',
             {'field': 'thưởng thêm', 'person': 'Linh', 'value': '1 triệu'}),
        ]
        for text, slots in table:
            self.assertEqual(_match(text), ('update_pay_data', slots), text)
        for text in ('tăng thêm phụ cấp cho Linh lên 500.000', 'tăng phụ cấp của Linh lên 500.000 nữa',
                     'đổi phụ cấp của Linh thành thêm 500.000'):
            got = _match(text)
            self.assertFalse(got and got[0] == 'update_pay_data', '%s → %r' % (text, got))

    def test_vi_red_narrowing_keeps_names_and_asks_months(self):
        """P4 vi-2 / vi-4 / vi-12, the Red half: the Approvals narrowing reads
        WHICH request through `resolve.item_query` — a name that folds to a
        little word narrows (Minh, Thắng, Đặng, Đỗ), and a month it cannot
        read ("tháng 13", "thang sau" with no marks) is asked, never matched
        against every waiting pay run."""
        self._today()
        ctx = SimpleNamespace(env=self.env)
        cards = [{'id': 1, 'title': 'Tăng ca của Minh'}, {'id': 2, 'title': 'Tăng ca của Lan'},
                 {'id': 3, 'title': 'Nghỉ phép của Thắng'}, {'id': 4, 'title': 'Nghỉ phép của Hoa'},
                 {'id': 5, 'title': 'Yêu cầu của Đặng Văn An'}, {'id': 6, 'title': 'Đơn của Đỗ Hùng'},
                 {'id': 7, 'title': 'Đơn của Lê Hùng'}, {'id': 8, 'title': 'Bảng lương Bán lẻ'}]

        def words(_inbox, card):
            return resolve.tokens(card['title']), None

        class _Inbox:
            def list_requests(self, tab='mine', scope='me'):
                return {'cards': cards}

            def _can_org(self):
                return False

        with patch.object(actions_red, '_card_words', words):
            for text, ids in (('tăng ca của Minh', [1]), ('nghỉ phép của Thắng', [3]),
                              ('yêu cầu của Đặng', [5]), ('đơn của Đỗ Hùng', [6])):
                hits = actions_red.match_cards(ctx, None, text, cards) or []
                self.assertEqual([c['id'] for _e, c in hits], ids, text)
            action = registry.ACTIONS['approve_item']
            with patch.object(type(action), '_inbox', lambda self_, ctx_: _Inbox()):
                for text in ('bảng lương tháng 13', 'bang luong thang sau'):
                    got = action._resolve_item(ctx, text)
                    self.assertEqual(got['status'], 'missing', (text, got))
                    self.assertTrue(got.get('note'), (text, got))
            self.assertEqual(registry.match('duyet bang luong thang sau'),
                             ('approve_item', {'item': 'bang luong thang sau'}))

    def test_vi4c_a_form_of_address_that_is_part_of_the_name(self):
        """"Anh Tuấn": the name as said is looked for first."""
        self.assertEqual(resolve.person_words('Anh Tuấn'), ['Tuấn'])
        Emp = self.env['hr.employee']
        tuan = Emp.create({'name': 'Anh Payai Tuan', 'company_id': self.company.id})
        Emp.create({'name': 'Payai Tuan Le', 'company_id': self.company.id})
        got = resolve.resolve_person(SimpleNamespace(env=self.env), 'Anh Payai Tuan')
        self.assertEqual((got['status'], got['value'], got['origin']), ('resolved', tuan.id, 'said'))

    # ============================================== fourth pass (verifier)
    def test_regression_a_name_ends_the_order(self):
        """An unmarked "ha / ho / nhi / chu" after "của / cho" or a form of
        address is a name (Hà, Hồ, Nhi, Chu) — the order stands, as at HEAD;
        with nothing naming someone before it, it still asks."""
        table = [
            ('duyet nghi phep cua chi ha', 'approve_item', {'item': 'nghi phep cua chi ha'}),
            ('duyet nghi phep cua anh ho', 'approve_item', {'item': 'nghi phep cua anh ho'}),
            ('duyet nghi phep cua chi nhi', 'approve_item', {'item': 'nghi phep cua chi nhi'}),
            ('duyet nghi phep cua anh chu', 'approve_item', {'item': 'nghi phep cua anh chu'}),
            ('duyet don cua ba ha', 'approve_item', {'item': 'don cua ba ha'}),
            ('duyet nghi phep cua nguyen thi ha', 'approve_item',
             {'item': 'nghi phep cua nguyen thi ha'}),
            ('duyet nghi phep chi ha', 'approve_item', {'item': 'nghi phep chi ha'}),
            ('tu choi tang ca cua anh ho', 'reject_item', {'item': 'tang ca cua anh ho'}),
            ('gui phieu luong thang 6 cho chi ha', 'send_payslips', {'run': 'thang 6 cho chi ha'}),
        ]
        for text, key, slots in table:
            self.assertEqual(_match(text), (key, slots), text)
            self.assertFalse(registry.looks_like_question(text), text)
        for text in ('chay luong thang 6 ha', 'gui phieu luong thang 6 ha',
                     'duyệt yêu cầu của Lan hả', 'gửi phiếu lương tháng 6 hả'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)

    def test_regression_the_verb_with_a_filler_word(self):
        """"duyệt hết / lại / hộ" asks for what is waiting, as "duyệt hết đi"
        does; the verb on its own is the card's typed word, never a request."""
        for text, key in (('duyệt hết', 'approve_item'), ('duyệt lại', 'approve_item'),
                          ('duyệt hộ tôi', 'approve_item'), ('duyệt dùm', 'approve_item'),
                          ('trả lại hết', 'send_back_item'), ('từ chối hết', 'reject_item'),
                          ('phê duyệt hết', 'approve_item'), ('DUYỆT HẾT', 'approve_item'),
                          ('duyet het', 'approve_item'), ('duyệt hết đi', 'approve_item')):
            self.assertEqual(_match(text), (key, {}), text)
        for text in ('DUYỆT', 'duyệt', 'trả lại', 'từ chối', 'TỪ CHỐI', 'từ chốı'):
            self.assertIsNone(_match(text), text)

    def test_regression_a_name_vi_or_a_dash_is_no_reason(self):
        """Only an order to decide carries a reason: elsewhere " Vi" is a name
        and " - " a dash, and the question is still a question."""
        for text in ('luong cua Vi la gi', 'phieu luong cua Vi nghia la gi',
                     'gross - net nghia la gi', 'phụ cấp - là gì',
                     'bang luong cua chi Vi tinh nhu the nao'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)
        got = _match('tra lai yeu cau cua Lan vi khong ro tai sao tang')
        self.assertEqual(got, ('send_back_item', {'item': 'yeu cau cua Lan',
                                                  'reason': 'khong ro tai sao tang'}))
        self.assertFalse(registry.looks_like_question('trả lại yêu cầu của Lan vì không rõ tại sao tăng'))

    def test_regression_a_day_or_a_name_before_thang(self):
        """"ngày 2 / mùng 5 / 05 tháng sau" is a day of that month, and "của
        Năm tháng trước" is Năm's — never a count of months."""
        self._today()
        for text, ym in (('ngày 2 tháng trước', (2026, 9)), ('ngày 15 tháng sau', (2026, 11)),
                         ('nghỉ phép ngày 20 tháng tới', (2026, 11)), ('mùng 5 tháng sau', (2026, 11)),
                         ('mồng 5 tháng sau', (2026, 11)), ('05 tháng sau', (2026, 11)),
                         ('nghỉ phép của Năm tháng trước', (2026, 9)),
                         ('của Hai tháng trước', (2026, 9)), ('phiếu lương của Ba tháng trước', (2026, 9)),
                         ('của Năm tháng sau', (2026, 11)),
                         # Counts stay counts.
                         ('6 tháng trước', (2026, 4)), ('năm tháng trước', (2026, 5)),
                         ('hai tháng trước', (2026, 8)), ('13 tháng trước', (2025, 9))):
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), ym, text)
        self.assertIn('nam', resolve.parse_period('nghỉ phép của Năm tháng trước', TODAY)[3].split())
        for text, day in (('mồng 5 tháng sau', datetime.date(2026, 11, 5)),
                          ('từ mùng 5 tháng sau', datetime.date(2026, 11, 5)),
                          ('mùng 10 tháng sau', datetime.date(2026, 11, 10)),
                          ('05 tháng sau', datetime.date(2026, 11, 5)),
                          ('ngày 5 tháng sau', datetime.date(2026, 11, 5)),
                          ('6 tháng trước', datetime.date(2026, 4, 1))):
            for lang in (VI, 'en_US'):
                self.assertEqual(self._day(text, lang), (day, 'said'), (text, lang))

    def test_regression_approvals_search_words(self):
        """The Approvals search: a "tháng" that is a length of time never
        narrows (only the name Thắng does), "thưởng / lương tháng 13" is the
        13th-month pay item, and the word right after "của" is kept."""
        stop = actions_red.ITEM_STOP
        table = {
            'đơn nghỉ thai sản 6 tháng của Lan': ['don', 'nghi', 'thai', 'san', 'lan'],
            'nghỉ phép 1 tháng của Lan': ['nghi', 'phep', 'lan'],
            'tạm ứng 2 tháng lương của Lan': ['tam', 'ung', 'luong', 'lan'],
            'tăng ca cuối tháng của Lan': ['tang', 'ca', 'cuoi', 'lan'],
            'phụ cấp hàng tháng của Lan': ['phu', 'cap', 'hang', 'lan'],
            'nghỉ phép của Thắng': ['nghi', 'phep', 'thang'],
            'thưởng tháng 13 của Lan': ['thuong', 'lan'],
            'lương tháng 13 của Lan': ['luong', 'lan'],
            'nghi phep cua ban': ['nghi', 'phep', 'ban'],
            'nghỉ phép của thôi': ['nghi', 'phep', 'thoi'],
            'nghỉ phép của luôn': ['nghi', 'phep', 'luon'],
            'nghỉ phép của mình': ['nghi', 'phep'],
            'nghỉ phép của tôi': ['nghi', 'phep'],
            'nghỉ phép của Năm tháng trước': ['nghi', 'phep', 'nam'],
        }
        for text, words in table.items():
            per, got, problem = resolve.item_query(text, TODAY, stop)
            self.assertEqual((got, problem), (words, ''), text)
        per, _got, _p = resolve.item_query('tăng ca ngày 2 tháng trước của Lan', TODAY, stop)
        self.assertEqual((per[0].year, per[0].month), (2026, 9))
        for text in ('bảng lương tháng 13', 'duyệt bảng lương tháng 13'):
            per, got, problem = resolve.item_query(text, TODAY, stop)
            self.assertIn('tháng 13', problem, text)

    # ================================================= fifth pass (verifier)
    def test_regression_from_label_and_year_are_not_counts(self):
        """"từ tháng trước" is FROM last month (not four months ago); "đợt 2 /
        kỳ 2 / tuần 2 / quý 3 tháng trước" label last month's round, week or
        quarter; "cuối / đầu / giữa năm" is the year; in a marked message
        "bà / sau" are not three and six. The counts stay counts."""
        table = {
            'chạy lương từ tháng trước': (2026, 9), 'gửi phiếu lương từ tháng trước': (2026, 9),
            'xem bảng lương từ tháng trước': (2026, 9), 'chạy lương từ tháng sau': (2026, 11),
            'chạy lương từ tháng tới': (2026, 11), 'tu thang truoc': (2026, 9),
            'chạy lương bà tháng trước': (2026, 9), 'sau tháng trước': (2026, 9),
            'gửi phiếu lương đợt 2 tháng trước': (2026, 9), 'xem bảng lương kỳ 2 tháng trước': (2026, 9),
            'chạy lương khối 2 tháng trước': (2026, 9), 'duyệt tăng ca tuần 2 tháng trước': (2026, 9),
            'chạy lương đợt 2 tháng sau': (2026, 11), 'duyệt thưởng quý 3 tháng trước': (2026, 9),
            'duyệt thưởng cuối năm tháng trước': (2026, 9),
            'duyệt nghỉ phép đầu năm tháng trước': (2026, 9),
            'duyệt bảng lương giữa năm tháng sau': (2026, 11),
            # Still counts.
            'ba tháng tới': (2027, 1), 'năm tháng trước': (2026, 5), 'bốn tháng trước': (2026, 6),
            'mười hai tháng trước': (2025, 10), '6 tháng trước': (2026, 4),
            'sáu tháng trước': (2026, 4), 'duyệt tăng ca 2 tháng trước': (2026, 8),
            'nam thang truoc': (2026, 5),
        }
        for text, ym in table.items():
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), ym, text)
        stop = actions_red.ITEM_STOP
        for text, (ym, words) in {
                'tăng ca từ tháng trước của Lan': ((2026, 9), ['tang', 'ca', 'tu', 'lan']),
                'thưởng cuối năm tháng trước': ((2026, 9), ['thuong', 'cuoi', 'nam']),
        }.items():
            per, got, problem = resolve.item_query(text, TODAY, stop)
            self.assertEqual(((per[0].year, per[0].month), got, problem), (ym, words, ''), text)

    def test_regression_send_back_takes_any_item(self):
        """"trả lại …" sends back whatever is named ("lương tháng 6", "cho
        Mai"); only a refund ("trả lại tiền thừa") is not a send-back."""
        table = [
            ('trả lại lương tháng 6 vì sai', {'item': 'lương tháng 6', 'reason': 'sai'}),
            ('trả lại tháng 6 vì sai', {'item': 'tháng 6', 'reason': 'sai'}),
            ('trả lại đợt chạy lương tháng 6', {'item': 'đợt chạy lương tháng 6'}),
            ('trả lại cho Mai', {'item': 'cho Mai'}),
            ('gửi trả lại cho Mai', {'item': 'cho Mai'}),
            ('trả lại Lan', {'item': 'Lan'}),
            ('trả lại hết', {}),
        ]
        for text, slots in table:
            self.assertEqual(_match(text), ('send_back_item', slots), text)
        for text in ('trả lại tiền thừa cho Linh', 'tra lai tien thua cho Linh',
                     'trả lương về', 'trả lời lại cho Linh'):
            self.assertIsNone(_match(text), text)

    def test_regression_emphasis_after_di_is_an_order(self):
        """"… đi chứ / đi nhỉ / đi à" presses the order; a bare "… hả" asks."""
        table = [
            ('chạy lương tháng 6 đi chứ', 'run_payroll'),
            ('gửi phiếu lương tháng 6 đi chứ', 'send_payslips'),
            ('chạy lương tháng 6 đi nhỉ', 'run_payroll'),
            ('duyệt nghỉ phép của Lan đi à', 'approve_item'),
        ]
        for text, key in table:
            got = _match(text)
            self.assertTrue(got and got[0] == key, '%s → %r' % (text, got))
            self.assertFalse(registry.looks_like_question(text), text)
        self.assertEqual(_match('duyệt nghỉ phép của Lan đi à'),
                         ('approve_item', {'item': 'nghỉ phép của Lan'}))
        for text in ('gửi phiếu lương tháng 6 hả', 'duyệt yêu cầu của Lan sao'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)

    def test_regression_title_case_little_words(self):
        """Title Case typing ("Của Mình", "Đang Chờ", "Cái Đó") never makes a
        little word a search word; "của Bạn / Thôi / Luôn" stay names."""
        stop = actions_red.ITEM_STOP
        for text in ('Duyệt Cái Đó', 'Duyệt Yêu Cầu Của Mình', 'Duyệt Yêu Cầu Đang Chờ'):
            _per, got, _p = resolve.item_query(text, TODAY, stop)
            self.assertNotIn('do', got, text)
            self.assertNotIn('minh', got, text)
            self.assertNotIn('dang', got, text)
        for text in ('Gửi Phiếu Lương Tháng 6 Của Mình', 'Xem Bảng Lương Tháng 6 Đang Chờ'):
            kept = resolve.fold(resolve.drop_vi_filler(text)).split()
            self.assertFalse({'minh', 'dang'} & set(kept), text)
        self.assertIn('Bạn', resolve.drop_vi_filler('nghỉ phép của Bạn'))

    def test_regression_lower_case_slip_in_tra_doi(self):
        """A lower-case "trà / trá lại", "đội lương" is a slip for "trả" /
        "đổi"; the capitalised "Trà" / "Đội" is a name or a team."""
        self.assertEqual(_match('trà lại bảng lương tháng 6'),
                         ('send_back_item', {'item': 'bảng lương tháng 6'}))
        self.assertEqual(_match('trá lại bảng lương tháng 6'),
                         ('send_back_item', {'item': 'bảng lương tháng 6'}))
        got = _match('đội lương của Lan thành 10.000.000')
        self.assertTrue(got and got[0] == 'update_pay_data', got)
        for text in ('Trà lại bảng lương tháng 6', 'Đội phụ cấp của Linh thành 500.000'):
            self.assertIsNone(_match(text), text)

    def test_regression_the_verb_asked_about(self):
        """"duyệt: là gì", "trả lại - nghĩa là gì" ask what the word means; an
        order with a reason that says "tại sao" stays an order."""
        for text in ('duyệt: là gì', 'duyet - la gi', 'từ chối: nghĩa là gì',
                     'trả lại - nghĩa là gì', 'duyệt - là gì'):
            self.assertIsNone(_match(text), text)
            self.assertTrue(registry.looks_like_question(text), text)
        got = _match('trả lại bảng lương tháng 6 vì không rõ tại sao tăng')
        self.assertEqual(got, ('send_back_item', {'item': 'bảng lương tháng 6',
                                                  'reason': 'không rõ tại sao tăng'}))

    # ============================================ final round (FIX1_OPEN2)
    def test_final_round_sentences_read_as_at_head(self):
        """Every sentence of the final review round reads as it did before
        FIX-1 (the live version): "từ" is "from", a label number or the
        "năm" of "cuối năm" is no count, "trả lại …" takes any item, "… đi
        chứ" presses an order, Title Case little words never narrow, a
        lower-case "trà / đội" is a slip, "duyệt: là gì" asks."""
        self._today()
        stop = actions_red.ITEM_STOP
        # "từ" (from) is never the count four.
        for text, ym in {'từ tháng trước': (2026, 9), 'từ tháng sau': (2026, 11),
                         'từ tháng tới': (2026, 11), 'bà tháng trước': (2026, 9)}.items():
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), ym, text)
        for text in ('kể từ tháng sau', 'bắt đầu từ tháng sau', 'áp dụng từ tháng sau'):
            self.assertEqual(self._day(text, VI), (datetime.date(2026, 11, 1), 'said'), text)
        for text, (key, slots, ym, words) in {
                'duyệt tăng ca từ tháng trước của Lan': (
                    'approve_item', {'item': 'tăng ca từ tháng trước của Lan'}, (2026, 9),
                    ['tang', 'ca', 'tu', 'lan']),
                'trả lại yêu cầu tăng ca từ tháng trước vì sai giờ': (
                    'send_back_item', {'item': 'yêu cầu tăng ca từ tháng trước', 'reason': 'sai giờ'},
                    (2026, 9), ['tang', 'ca', 'tu']),
                # A label number, and the "năm" of "đầu / giữa năm".
                'duyệt bảng lương đợt 2 tháng trước': (
                    'approve_item', {'item': 'bảng lương đợt 2 tháng trước'}, (2026, 9),
                    ['bang', 'luong', 'dot']),
                'duyệt nghỉ phép đầu năm tháng trước': (
                    'approve_item', {'item': 'nghỉ phép đầu năm tháng trước'}, (2026, 9),
                    ['nghi', 'phep', 'dau', 'nam']),
                'duyệt bảng lương giữa năm tháng sau': (
                    'approve_item', {'item': 'bảng lương giữa năm tháng sau'}, (2026, 11),
                    ['bang', 'luong', 'giua', 'nam']),
                # "trả lại …": any item, as before.
                'trả lại lương tháng 6 vì sai': (
                    'send_back_item', {'item': 'lương tháng 6', 'reason': 'sai'}, (2026, 6), ['luong']),
        }.items():
            got = _match(text)
            self.assertEqual(got, (key, slots), text)
            per, q, problem = resolve.item_query(got[1]['item'], TODAY, stop)
            self.assertEqual(((per[0].year, per[0].month), q, problem), (ym, words, ''), text)
        for text in ('trả lại đợt tháng 6', 'trả lại kỳ tháng 6', 'trả lại lần chạy lương tháng 6',
                     'trả lại bảng tính lương tháng 6', 'trả lại payroll tháng 6',
                     'trả lại pay run tháng 6'):
            got = _match(text)
            self.assertEqual(got, ('send_back_item', {'item': text[len('trả lại '):]}), text)
            per, _q, _p = resolve.item_query(got[1]['item'], TODAY, stop)
            self.assertEqual((per[0].year, per[0].month), (2026, 6), text)
        for text, slots in (('trả lại của Lan', {'item': 'của Lan'}),
                            ('trả lại cho Mai vì sai', {'item': 'cho Mai', 'reason': 'sai'}),
                            ('trả về cho Mai sửa', {'item': 'cho Mai sửa'})):
            self.assertEqual(_match(text), ('send_back_item', slots), text)
        # "… đi chứ": an order pressed, not a question.
        for text, slots in (('duyệt bảng lương tháng 6 đi chứ', {'item': 'bảng lương tháng 6 đi chứ'}),
                            ('duyệt đi chứ', {'item': 'đi chứ'})):
            self.assertEqual(_match(text), ('approve_item', slots), text)
            self.assertFalse(registry.looks_like_question(text), text)
        got = _match('duyệt luôn đi chứ')
        self.assertTrue(got and got[0] == 'approve_item', got)
        got = _match('chạy lương tháng 6 đi chứ')
        per = resolve.parse_period(got[1]['period'], TODAY)
        self.assertEqual((got[0], per[0].year, per[0].month), ('run_payroll', 2026, 6))
        # Title Case "Của Mình" / "Đang Chờ" never narrows the run.
        for text in ('Gửi Phiếu Lương Tháng 6 Của Mình', 'Gửi phiếu lương tháng 6 Của Mình',
                     'Xem Bảng Lương Tháng 6 Đang Chờ'):
            got = _match(text)
            per = resolve.parse_period(resolve.drop_vi_filler(got[1]['run']), TODAY)
            self.assertEqual((per[0].year, per[0].month), (2026, 6), text)
            self.assertEqual([t for t in resolve.tokens(per[3], resolve.RUN_STOP - resolve.NAME_LIKE)
                              if not t.isdigit()], [], text)
        # A lower-case tone slip in the order word.
        got = _match('trà lại bảng lương tháng 6')
        per, q, _p = resolve.item_query(got[1]['item'], TODAY, stop)
        self.assertEqual((got[0], per[0].month, q), ('send_back_item', 6, ['bang', 'luong']))

    # ======================================== final round, safety check
    def test_final_safety_a_label_typed_without_marks_is_still_a_label(self):
        """FIX-1 final round, safety check (HEAD vs tree): in a marked message
        a label typed without its marks ("khoi 2", "nhom 2") still labels a
        team — last month's, not two months ago. "lan" stays out (Lan is a
        name), and a count stays a count."""
        for text, ym in {'chạy lương khoi 2 tháng trước': (2026, 9),
                         'gửi phiếu lương nhom 2 tháng sau': (2026, 11),
                         'xem bảng lương tuan 2 tháng trước': (2026, 9),
                         'chạy lương khối văn phòng 2 tháng trước': (2026, 8),
                         'duyệt tăng ca 2 tháng trước': (2026, 8)}.items():
            got = resolve.parse_period(text, TODAY)
            self.assertEqual((got[0].year, got[0].month), ym, text)


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixVietnameseCards(_P3Case):
    """End to end, as the person: the cards these readings lead to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['res.lang']._activate_lang(VI)
        cls.vi_hr = cls._user('Payai VI Records', [cls.env.ref('hr.group_hr_user').id,
                                                   cls.g_officer, cls.g_pay_user])
        cls.vi_hr.lang = VI

    def _records_fixture(self):
        """P2's Records fixture: a numeric pay value on our scheme."""
        if 'pb.records.desk' not in self.env:
            self.skipTest('Records Desk not installed.')
        if 'pb.scheme.map' in self.env:
            p = patch.object(self.registry['pb.scheme.map'], 'resolve',
                             lambda self_, employee, cycle_type='any', on_date=None: {
                                 'config_id': self.retail_end.id, 'config_name': '',
                                 'rung': 'test', 'via': ''})
            p.start()
            self.addCleanup(p.stop)
        self.env['hr.formula.rule'].create({
            'config_id': self.retail_end.id, 'name': 'Payai Meal allowance',
            'code': 'PAYAIMEAL', 'column_type': 'input', 'sequence': 1,
            'default_value': 0.0, 'is_contract_component': True})
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'records')

    # ----------------------------------------------------------- test-5
    def test_test5_vietnamese_pay_value_card(self):
        """"đổi … thành 500.000 từ tháng này": the card shows 500.000 the
        Vietnamese way, the stored value is 500000, the day is said."""
        self._records_fixture()
        Conv = self.env['payroll.ai.conversation'].with_user(self.vi_hr).with_context(lang=VI)
        session = self._session(self.vi_hr)
        card = Conv.rpc_send_message(
            'đổi Payai Meal allowance của Payai Linh Nguyen thành 500.000 từ tháng này',
            session.id, None)['card']
        self.assertEqual(card['kind'], 'plan', card)
        slots = {s['key']: s for s in card['slots']}
        self.assertIn('500.000', slots['value']['value_label'])
        self.assertNotIn('500,000', slots['value']['value_label'])
        today = fields.Date.context_today(self.vi_hr)
        self.assertEqual(slots['from']['value_label'],
                         '1 tháng %d năm %d' % (today.month, today.year))
        self.assertEqual(slots['from']['origin'], 'said')
        vals = json.loads(self._task(card).params_json)['vals']
        self.assertEqual(vals['changes'][0]['value'], 500000)

    # ------------------------------------------------------------- wf-9
    def test_wf9_the_named_run_is_not_approved(self):
        """June: Retail is a draft, Office is approved. "Send the June Retail
        payslips" names Retail — never "No approved run for June"."""
        if 'pb.pay.delivery' not in self.env:
            self.skipTest('Pay & Deliver not installed.')
        retail = self._run_with_slip(self.retail_end, 'Payai Retail Shop')
        office = self._run_with_slip(self.retail_mid, 'Payai Office Desk', employee=self.e2)
        self.env.cr.execute("UPDATE hr_payslip SET state = 'done' WHERE payslip_run_id = %s",
                            (office.id,))
        self.env.cr.execute("UPDATE hr_payslip_run SET state = 'done' WHERE id = %s", (office.id,))
        self.env.invalidate_all()
        card, _s = self._send(self.manager, 'Send the June 2031 Payai Retail Shop payslips')
        text = json.dumps(card, ensure_ascii=False)
        self.assertNotIn('No approved run for June 2031 yet', text)
        self.assertIn('"Payai Retail Shop" is Draft now', text.replace('\\"', '"'))
        self.assertEqual(retail.state, 'draft')
        # With no run of the month approved, the month-wide sentence stays.
        self.env.cr.execute("UPDATE hr_payslip_run SET state = 'draft' WHERE id = %s", (office.id,))
        self.env.invalidate_all()
        card, _s = self._send(self.manager, 'Send the June 2031 Payai Retail Shop payslips')
        self.assertIn('No approved run for June 2031 yet', json.dumps(card))

