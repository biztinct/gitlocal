/** @odoo-module **/
import { registry } from '@web/core/registry';
import { _t } from '@web/core/l10n/translation';
import { SETTINGS_CATEGORIES } from '@pb_settings/js/settings_hub';
registry.category(SETTINGS_CATEGORIES).add('attendance_calculation', {
    key: 'attendance_calculation', group: 'hr', icon: 'clock',
    label: _t('Attendance calculation'),
    blurb: _t('Set normal hours, breaks and lateness rules. Review employee groups and schedules before activation.'),
    groups: ['hr_attendance.group_hr_attendance_manager'],
    cards: [
        { id: 'policies', xmlid: 'pb_attendance_policy.action_policy', icon: 'sliders',
          label: _t('Calculation policies'), sub: _t('Shift boundaries, unpaid breaks and additional lateness deductions.') },
        { id: 'employees', xmlid: 'pb_attendance_policy.action_employee_policy', icon: 'users',
          label: _t('Employee attendance settings'), sub: _t('Choose Worker or Manager / supervisor and assign a policy.') },
        { id: 'rosters', xmlid: 'pb_hr_workforce.action_shift_planning_no_filter', icon: 'calendar',
          label: _t('Review rosters and hours'), sub: _t('Review suggested shifts, preview payable hours, then publish confirmed schedules.') },
        { id: 'patterns', tag: 'pb_shift_patterns', icon: 'calendar',
          label: _t('Recurring shift patterns'), sub: _t('Working days, rest days and recurring roster drafts.') },
        { id: 'calendars', xmlid: 'resource.action_resource_calendar_form', icon: 'calendar',
          label: _t('Normal working calendars'), sub: _t('Standard payroll days and paid holidays. Keep these aligned with reviewed normal shift hours.') },
    ],
}, { sequence: 40 });
