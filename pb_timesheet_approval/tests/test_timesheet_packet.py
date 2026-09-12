# -*- coding: utf-8 -*-
"""The weekly timesheet packet, end to end.

Every case runs the REAL path — the engine's own `submit` and `decide`, as the
real acting user — because the promise of the phase is that a week is signed
off by whoever the business published, and a test that wrote the states itself
would prove nothing about that.

S01 build · S02 route and apply · S03 the frozen week · S04 payroll inputs ·
S05 the cut-off and the block. S11's seed half is here too; S12 is in
`test_static.py`.
"""
from datetime import date, datetime, time, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


def _route(steps, independent=False):
    return {
        'schema_version': 1,
        'steps': steps,
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': independent,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


def _manager_step(key='s1', title='Their manager', kind='review'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'manager'}, 'min_amount': 0, 'condition': None}


def _role_step(key, role, title, kind='approve', scope='company'):
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'role', 'role': role, 'scope': scope},
            'min_amount': 0, 'condition': None}


@tagged('post_install', '-at_install')
class TimesheetPacketCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['biz.approval.engine']
        cls.Packet = cls.env['pb.timesheet.packet']
        cls.Grid = cls.env['hr.attendance.weekentry']
        cls.process = cls.env['biz.approval.process']._by_key('timesheet')
        cls.company = cls.env.company
        cls.company.write({'pb_timesheet_payroll': True,
                           'pb_timesheet_block_run': False})
        cls.department = cls.env['hr.department'].create(
            {'name': 'TS Line 1', 'company_id': cls.company.id})

        cls.officer = cls._user('ts_officer', 'Olive Officer', attendance=True)
        cls.manager_user = cls._user('ts_manager', 'Mai Manager')
        cls.hr_user = cls._user('ts_hr', 'Hana HR')

        cls.manager = cls.env['hr.employee'].create({
            'name': 'Mai Manager', 'company_id': cls.company.id,
            'department_id': cls.department.id,
            'user_id': cls.manager_user.id})
        cls.worker = cls.env['hr.employee'].create({
            'name': 'Wanda Worker', 'company_id': cls.company.id,
            'department_id': cls.department.id,
            'parent_id': cls.manager.id})
        # A Monday well inside a quiet past month, so nothing in the database
        # can already own these days.
        cls.monday = date(2026, 3, 2)

    @classmethod
    def _user(cls, login, name, attendance=False):
        groups = [cls.env.ref('base.group_user').id]
        if attendance:
            for xmlid in ('hr_attendance.group_hr_attendance_officer',
                          'hr_attendance.group_hr_attendance_manager',
                          'hr.group_hr_user'):
                group = cls.env.ref(xmlid, raise_if_not_found=False)
                if group:
                    groups.append(group.id)
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, groups)],
            })

    def setUp(self):
        super().setUp()
        if not self.process:
            self.skipTest('the approval catalogue is not installed here')

    # ------------------------------------------------------------ fixtures
    def _punch(self, day, hours=8.0, source='grid', employee=None):
        employee = employee or self.worker
        check_in = datetime.combine(day, time(8, 0))
        return self.env['hr.attendance'].sudo().create({
            'employee_id': employee.id,
            'check_in': check_in,
            'check_out': check_in + timedelta(hours=hours),
            'pb_entry_source': source,
        })

    def _overtime(self, day, hours=2.0, ot_type='weekday', employee=None):
        employee = employee or self.worker
        return self.env['hr.overtime.request'].sudo().create({
            'employee_id': employee.id,
            'date': day,
            'overtime_type': ot_type,
            'planned_hours': hours,
            'actual_hours': hours,
            'approved_hours': hours,
            'reason': 'Test overtime',
            'company_id': self.company.id,
        })

    def _week_of_work(self, days=5, hours=8.0):
        for index in range(days):
            self._punch(self.monday + timedelta(days=index), hours)

    def _hold(self, role_key, user, scope_key=''):
        role = self.env['biz.approval.role'].search(
            [('key', '=', role_key)], limit=1)
        if not role:
            self.skipTest("the '%s' responsibility is not here" % role_key)
        existing = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', scope_key), ('active', '=', True)], limit=1)
        if existing:
            existing.write({'user_id': user.id})
            return existing
        return self.env['biz.approval.responsibility'].sudo().create({
            'company_id': self.company.id, 'role_id': role.id,
            'scope_key': scope_key,
            'scope_label': scope_key or self.company.name,
            'user_id': user.id})

    def _bind(self, definition, scope_key='', kind_key='any',
              name='TS route'):
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', scope_key),
            ('kind_key', '=', kind_key),
            ('active', '=', True)]).write({'active': False})
        workflow = self.env['biz.approval.workflow'].sudo().create({
            'name': name, 'company_id': self.company.id,
            'process_id': self.process.id,
            'owner_user_id': self.env.user.id})
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id, 'revision': 1, 'status': 'draft',
            'definition': definition})
        checks = self.engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'], checks['errors'])
        self.engine.publish(version.id, version.draft_revision, None, 'test',
                            [w['code'] for w in checks['warnings']])
        Binding.create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'scope_key': scope_key,
            'scope_label': scope_key or self.company.name,
            'kind_key': kind_key, 'workflow_id': workflow.id,
            'mode': 'follow'})
        return workflow

    def _manager_then_hr(self):
        self._hold('hr_lead', self.hr_user)
        return self._bind(_route([
            _manager_step(),
            _role_step('s2', 'hr_lead', 'HR lead'),
        ]))

    def _packet(self):
        return self.Packet.packet_for(self.worker, self.monday)

    def _decide(self, packet, user, action='approve', reason='ok'):
        request = packet.approval_request_id
        self.engine.with_user(user).decide(
            request.id, request.current_step_key, action, reason)
        packet.invalidate_recordset()

    # ==================================================================
    # S01 — the packet is built from what is actually recorded
    # ==================================================================
    def test_s01_build_snapshots_hours_and_overtime(self):
        self._week_of_work(days=5, hours=8.0)
        self._overtime(self.monday, hours=2.5)
        packet = self._packet()

        self.assertEqual(packet.reg_hours, 40.0)
        self.assertEqual(packet.ot_hours, 2.5)
        self.assertEqual(packet.total_hours, 42.5)
        self.assertEqual(packet.days_with_hours, 5)
        self.assertEqual(len(packet.days()), 7)
        self.assertTrue(packet.source_hash)

    def test_s01_the_stamp_moves_when_the_hours_move(self):
        self._week_of_work(days=3)
        packet = self._packet()
        before = packet.source_hash
        self._punch(self.monday + timedelta(days=3), 6.0)
        packet._refresh_snapshot()
        self.assertNotEqual(packet.source_hash, before)
        self.assertEqual(packet.reg_hours, 30.0)

    def test_s01_one_packet_per_person_per_week(self):
        self._week_of_work(days=2)
        first = self._packet()
        second = self._packet()
        self.assertEqual(first, second)

    # ==================================================================
    # S02 — the route, and what approving it does
    # ==================================================================
    def test_s02_a_week_goes_to_the_manager_then_the_hr_lead(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()

        self.assertEqual(packet.state, 'pending')
        request = packet.approval_request_id
        self.assertEqual(request.state, 'pending')
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)
        self.assertEqual(step.seat_ids.acting_user_id, self.manager_user)

        self._decide(packet, self.manager_user)
        self._decide(packet, self.hr_user)
        self.assertEqual(packet.state, 'approved')
        self.assertEqual(packet.approved_hash, packet.source_hash)

    def test_s02_no_manager_means_a_named_refusal_not_a_guess(self):
        self._manager_then_hr()
        self.worker.sudo().parent_id = False
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        request = packet.approval_request_id
        self.assertEqual(request.state, 'blocked')
        self.assertIn('manager', (request.block_reason or '').lower())

    def test_s02_approving_the_week_approves_its_overtime(self):
        self._manager_then_hr()
        self._week_of_work()
        overtime = self._overtime(self.monday, hours=2.0)
        overtime.sudo().write({'state': 'draft'})
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        self._decide(packet, self.manager_user)
        self._decide(packet, self.hr_user)

        overtime.invalidate_recordset()
        self.assertEqual(packet.state, 'approved')
        self.assertEqual(overtime.state, 'approved')

    def test_s02_already_approved_overtime_is_not_approved_twice(self):
        self._manager_then_hr()
        self._week_of_work()
        overtime = self._overtime(self.monday, hours=2.0)
        overtime.sudo().write({'state': 'approved', 'approved_hours': 2.0})
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        self._decide(packet, self.manager_user)
        self._decide(packet, self.hr_user)
        overtime.invalidate_recordset()
        self.assertEqual(overtime.state, 'approved')
        self.assertEqual(overtime.approved_hours, 2.0)

    def test_s02_sent_back_thaws_the_week_and_keeps_the_reason(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        self._decide(packet, self.manager_user, action='return',
                     reason='Tuesday looks wrong')
        self.assertEqual(packet.state, 'returned')
        self.assertIn('Tuesday', packet.packet_note or '')
        # and it is editable again
        self._punch(self.monday + timedelta(days=5), 4.0)

    def test_s02_the_state_cannot_be_written_by_hand(self):
        self._week_of_work()
        packet = self._packet()
        with self.assertRaises(AccessError):
            packet.with_user(self.officer).write({'state': 'approved'})

    # ==================================================================
    # S03 — a week under approval does not move
    # ==================================================================
    def test_s03_a_pending_week_refuses_an_edit(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        with self.assertRaises(ValidationError):
            self._punch(self.monday + timedelta(days=5), 4.0)

    def test_s03_an_approved_week_refuses_an_edit_and_says_so(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        self._decide(packet, self.manager_user)
        self._decide(packet, self.hr_user)
        with self.assertRaises(ValidationError) as caught:
            self._punch(self.monday + timedelta(days=5), 4.0)
        self.assertIn('approved', str(caught.exception).lower())

    def test_s03_a_returned_week_is_editable_again(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        self._decide(packet, self.manager_user, action='return',
                     reason='please fix')
        attendance = self._punch(self.monday + timedelta(days=5), 4.0)
        self.assertTrue(attendance.id)

    def test_s03_a_locked_day_cannot_be_sent_in(self):
        Lock = self.env.get('pb.wf.lock')
        if Lock is None:
            self.skipTest('the workforce close is not installed here')
        self._manager_then_hr()
        self._week_of_work()
        Lock.sudo().create({
            'company_id': self.company.id,
            'date': self.monday,
            'state': 'locked'})
        packet = self._packet()
        with self.assertRaises(UserError):
            packet.with_user(self.officer).action_submit_week()

    def test_s03_overtime_inside_a_pending_week_is_refused(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        with self.assertRaises(ValidationError):
            self._overtime(self.monday + timedelta(days=1), hours=3.0)

    # ==================================================================
    # S04 — what payroll reads
    # ==================================================================
    def _approved_week(self):
        self._manager_then_hr()
        self._week_of_work(days=5, hours=8.0)
        self._overtime(self.monday, hours=3.0, ot_type='weekday')
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        self._decide(packet, self.manager_user)
        self._decide(packet, self.hr_user)
        return packet

    def test_s04_approved_weeks_answer_the_hour_codes(self):
        packet = self._approved_week()
        self.assertEqual(packet.state, 'approved')
        rows = self.Packet.approved_in_period(
            self.worker.id, self.monday, self.monday + timedelta(days=6))
        self.assertEqual(rows, packet)
        self.assertEqual(rows.reg_hours, 40.0)
        self.assertEqual(rows.ot_weekday_hours, 3.0)

    def test_s04_an_unapproved_week_answers_nothing(self):
        self._week_of_work()
        self._packet()
        rows = self.Packet.approved_in_period(
            self.worker.id, self.monday, self.monday + timedelta(days=6))
        self.assertFalse(rows)

    def test_s04_the_rung_is_silent_when_the_setting_is_off(self):
        """With the setting off, this module contributes no value at all."""
        self.company.pb_timesheet_payroll = False
        packet = self.Packet.sudo().create({
            'employee_id': self.worker.id, 'week_start': self.monday,
            'company_id': self.company.id})
        self.assertTrue(packet.id)
        config = self._fake_config(['REGHRS'])
        if config is None:
            self.skipTest('the formula engine is not installed here')
        slip = self._slip(config)
        values = slip._get_formula_input_values(config, provenance={})
        self.assertNotIn('REGHRS', values)

    def test_s04_the_rung_fills_the_codes_the_scheme_declares(self):
        packet = self._approved_week()
        config = self._fake_config(['REGHRS', 'WORKDAYS', 'OTHRS150'])
        if config is None:
            self.skipTest('the formula engine is not installed here')
        slip = self._slip(config)
        provenance = {}
        values = slip._get_formula_input_values(config, provenance=provenance)
        self.assertEqual(values['REGHRS'], 40.0)
        self.assertEqual(values['WORKDAYS'], 5)
        self.assertEqual(values['OTHRS150'], 3.0)
        self.assertEqual(provenance['REGHRS']['via'], 'timesheet_packet')
        self.assertIn('week of', provenance['REGHRS']['key'])
        self.assertEqual(packet.state, 'approved')

    def _slip(self, config):
        """A real payslip for the week, so the whole input chain runs."""
        contract = self.env['hr.contract'].sudo().search(
            [('employee_id', '=', self.worker.id)], limit=1)
        if not contract:
            contract = self.env['hr.contract'].sudo().create({
                'name': 'TS contract', 'employee_id': self.worker.id,
                'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
                'company_id': self.company.id})
        return self.env['hr.payslip'].sudo().create({
            'employee_id': self.worker.id, 'name': 'TS slip',
            'contract_id': contract.id,
            'date_from': self.monday,
            'date_to': self.monday + timedelta(days=6),
            'company_id': self.company.id,
            'calculation_method': 'formula',
            'formula_config_id': config.id,
        })

    def _fake_config(self, codes):
        """A pay scheme declaring exactly these input codes, and nothing else."""
        Config = self.env.get('hr.formula.config')
        if Config is None:
            return None
        values = {'name': 'TS scheme', 'code': 'TSCHEME',
                  'company_id': self.company.id}
        field = Config._fields.get('country_code')
        if field is not None:
            allowed = [key for key, _label
                       in (field.get_description(self.env)['selection'] or [])]
            values['country_code'] = 'VN' if 'VN' in allowed else allowed[0]
        config = Config.sudo().create(values)
        for index, code in enumerate(codes):
            self.env['hr.formula.rule'].sudo().create({
                'config_id': config.id, 'name': code, 'code': code,
                'column_type': 'input', 'sequence': (index + 1) * 10,
            })
        return config

    # ==================================================================
    # S05 — late, and the block
    # ==================================================================
    def test_s05_late_is_a_fact_the_route_can_read(self):
        self._week_of_work()
        packet = self._packet()
        # A week of March, read from well inside April, is late whatever the
        # cut-off day is.
        self.assertTrue(packet._is_late(date(2026, 4, 28)))
        self.assertFalse(packet._is_late(self.monday + timedelta(days=6)))

    def test_s05_the_late_fact_reaches_the_request(self):
        self._manager_then_hr()
        self._week_of_work()
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        facts = packet.approval_request_id.facts or {}
        self.assertIn('late_submission', facts)
        self.assertTrue(packet.late_submission)

    def test_s05_the_block_names_the_weeks_nobody_approved(self):
        self._week_of_work()
        self._packet()
        self.company.pb_timesheet_block_run = True
        wizard = self.env['pb.payrun.wizard']
        with self.assertRaises(UserError) as caught:
            wizard._timesheet_require_approved(
                [self.worker.id], self.monday,
                self.monday + timedelta(days=6))
        self.assertIn('Wanda Worker', str(caught.exception))

    def test_s05_without_the_block_it_is_only_a_note(self):
        self._week_of_work()
        self._packet()
        exceptions = []
        self.env['pb.payrun.wizard']._timesheet_append_exceptions(
            exceptions, [self.worker.id], self.monday,
            self.monday + timedelta(days=6))
        self.assertTrue(exceptions)
        self.assertTrue(any('note, not a block' in row['why']
                            for row in exceptions))

    def test_s05_an_approved_week_raises_nothing(self):
        self._approved_week()
        self.company.pb_timesheet_block_run = True
        self.env['pb.payrun.wizard']._timesheet_require_approved(
            [self.worker.id], self.monday, self.monday + timedelta(days=6))

    # ==================================================================
    # S11 — the seed, and the catalogue row it repoints
    # ==================================================================
    def test_s11_the_catalogue_names_the_record_not_the_screen(self):
        self.assertEqual(self.process.model_name, 'pb.timesheet.packet')
        self.assertTrue(self.process.connected)

    def test_s11_every_company_has_a_published_weekly_route(self):
        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        self.assertTrue(binding, 'the seed laid no company-wide route')
        self.assertEqual(binding.workflow_id.published_version_id.status,
                         'published')

    def test_s11_the_seed_is_safe_to_run_again(self):
        before = self.env['biz.approval.workflow'].sudo().search_count([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id)])
        self.Packet._approval_seed_default(self.company)
        after = self.env['biz.approval.workflow'].sudo().search_count([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id)])
        self.assertEqual(before, after)

    # ==================================================================
    # The grid facade
    # ==================================================================
    def test_grid_sends_the_visible_week_in(self):
        self._manager_then_hr()
        self._week_of_work()
        result = self.Grid.with_user(self.officer).submit_week_packets(
            self.monday.isoformat(), self.department.id, False)
        self.assertEqual(result['weeks_submitted'], 1)
        packet = self.Packet.sudo().search([
            ('employee_id', '=', self.worker.id),
            ('week_start', '=', self.monday)])
        self.assertEqual(packet.state, 'pending')

    def test_grid_status_rows_name_who_it_is_with(self):
        self._manager_then_hr()
        self._week_of_work()
        self.Grid.with_user(self.officer).submit_week_packets(
            self.monday.isoformat(), self.department.id, False)
        payload = self.Grid.with_user(self.officer).week_packets(
            self.monday.isoformat(), self.department.id, False)
        row = [r for r in payload['rows']
               if r['employee_id'] == self.worker.id][0]
        self.assertEqual(row['state'], 'pending')
        self.assertIn('Mai Manager', row['state_label'])

    def test_grid_submit_week_still_submits_loose_overtime(self):
        self._manager_then_hr()
        self._week_of_work()
        overtime = self._overtime(self.monday, hours=2.0)
        overtime.sudo().write({'state': 'draft'})
        result = self.Grid.with_user(self.officer).submit_week(
            self.monday.isoformat(), self.department.id, False)
        self.assertIn('submitted', result)
        self.assertIn('weeks_submitted', result)

    # ==================================================================
    # The inbox
    # ==================================================================
    def test_the_card_counts_hours_not_payslips(self):
        self._manager_then_hr()
        self._week_of_work()
        self._overtime(self.monday, hours=4.5)
        packet = self._packet()
        packet.with_user(self.officer).action_submit_week()
        packet.invalidate_recordset()
        payload = self.env['pb.approval.inbox'].with_user(
            self.manager_user).get_request(packet.approval_request_id.id)
        self.assertIn('h', payload['count'])
        self.assertIn('overtime', payload['count'])
        self.assertTrue(payload['detail'])
        self.assertEqual(len(payload['detail']['rows']), 7)
