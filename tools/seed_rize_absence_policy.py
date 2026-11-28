"""Explicit Rize-only prospective absence activation, intended for Odoo shell.

This is not a module data file and never runs on install. Call
``seed_rize_absence_policy(env, activation_date, ..., apply=False)`` to inspect
counts and unmatched records, then call with apply=True inside the reviewed
migration transaction. The caller owns commit/rollback.

Full-time reviews are {employee_id: {'confirmed': bool, 'reference': str}}.
Type mappings are {company_id: {country_code: {category: leave_type_id}}}.
Neither nationality, employee_type='employee', work-hour thresholds nor names
are used to infer eligibility. No balances or historical leave are created.
"""
from collections import defaultdict
from odoo import fields
from odoo.exceptions import UserError


def seed_rize_absence_policy(env, activation_date, full_time_reviews=None,
                            country_type_mappings=None, apply=False, create_missing_types=False,
                            employee_ids=None, employee_country_reviews=None):
    if env.cr.dbname != 'rize':
        raise UserError('This activation is restricted to the rize database.')
    activation = fields.Date.to_date(activation_date)
    if not activation or activation < fields.Date.today():
        raise UserError('Activation must be today or later; historical balances need a separate reviewed cutover.')
    reviews = {int(key): value for key, value in (full_time_reviews or {}).items()}
    mappings = {int(key): value for key, value in (country_type_mappings or {}).items()}
    domain = [('active', '=', True)]
    if employee_ids is not None:
        domain.append(('id', 'in', employee_ids))
    employees = env['hr.employee'].search(domain)
    country_reviews = {int(key): value for key, value in (employee_country_reviews or {}).items()}
    if set(country_reviews) - set(employees.ids):
        raise UserError('Country evidence refers to an employee outside the reviewed scope.')
    groups = defaultdict(list)
    skipped = []
    for employee in employees:
        country = employee.payroll_country if 'payroll_country' in employee._fields else False
        evidence = country_reviews.get(employee.id)
        if evidence:
            selected = evidence.get('country')
            if selected not in ('VN', 'IN', 'SG', 'ID') or not str(evidence.get('reference', '')).strip():
                raise UserError('Country selection needs a supported payroll country and explicit evidence.')
            if country and country != selected:
                raise UserError('Country evidence conflicts with the employee payroll country.')
            country = selected
        if country not in ('VN', 'IN', 'SG', 'ID'):
            skipped.append({'employee_id': employee.id, 'reason': 'No supported explicit payroll country'})
            continue
        groups[(employee.company_id.id, country)].append(employee.id)
    for company_id, countries in mappings.items():
        for country in countries:
            if country not in ('VN', 'IN', 'SG', 'ID'):
                raise UserError('Only the four reviewed Rize employment countries can be activated.')
            groups.setdefault((company_id, country), [])
    unknown = set(reviews) - set(employees.ids)
    if unknown:
        raise UserError('Full-time review refers to inactive, inaccessible or unknown employees: %s' % sorted(unknown))
    for employee_id, review in reviews.items():
        if not isinstance(review.get('confirmed'), bool) or not str(review.get('reference', '')).strip():
            raise UserError('Each full-time decision needs an explicit boolean and an evidence reference.')
    result = {'activation': str(activation), 'apply': bool(apply), 'groups': [], 'skipped': skipped,
              'no_balance_changes': True, 'no_historical_request_changes': True,
              'employee_country_evidence': country_reviews}
    for (company_id, country), employee_ids in sorted(groups.items()):
        type_map = dict(mappings.get(company_id, {}).get(country, {}))
        categories = ['annual', 'wellness', 'maternity', 'paternity', 'miscarriage', 'bereavement', 'marriage', 'unpaid']
        categories += {'SG': ['hospitalization', 'childcare', 'adoption'], 'IN': ['adoption', 'surrogacy'],
                       'ID': ['menstrual', 'child_marriage', 'family_death', 'household_death', 'baptism']}.get(country, [])
        planned_types = []
        labels = dict(env['hr.leave.type']._fields['pb_policy_category']._description_selection(env))
        for category in categories:
            code = 'RIZE:%s:%s:%s' % (company_id, country, category)
            existing = env['hr.leave.type'].search([('pb_policy_code', '=', code)])
            if existing and category not in type_map:
                type_map[category] = existing.id
            if category not in type_map:
                planned_types.append({'category': category, 'code': code,
                                      'name': 'Rize %s · %s' % (country, labels[category]),
                                      'requires_allocation': category == 'annual',
                                      'approval': 'both'})
        for category, type_id in type_map.items():
            leave_type = env['hr.leave.type'].browse(type_id).exists()
            if len(leave_type) != 1 or (leave_type.company_id and leave_type.company_id.id != company_id):
                raise UserError('Explicit leave type mapping is missing or belongs to another company.')
            if leave_type.pb_policy_country_id and leave_type.pb_policy_country_id.code != country:
                raise UserError('The explicit leave type belongs to another policy employment country.')
            if not leave_type.pb_policy_country_id and leave_type.country_id and leave_type.country_id.code != country:
                raise UserError('The existing localized leave type belongs to another country. Create the country-specific Rize type instead.')
        group = {'company_id': company_id, 'payroll_country': country,
                 'employee_ids': employee_ids, 'type_mappings': type_map,
                 'types_to_create': planned_types if create_missing_types else [],
                 'unmapped_categories': [t['category'] for t in planned_types] if not create_missing_types else [],
                 'reviewed_full_time_ids': [eid for eid in employee_ids if reviews.get(eid, {}).get('confirmed')],
                 'eligibility_review_required_ids': [eid for eid in employee_ids
                     if not (reviews[eid]['confirmed'] if eid in reviews else env['hr.employee'].browse(eid).pb_policy_full_time_confirmed)]}
        if apply:
            edition = env['pb.leave.policy.edition']._seed_rize_policy(company_id, country, activation, type_map)
            group['policy_id'] = edition.id
            if planned_types and not create_missing_types:
                raise UserError('Some policy categories lack native leave types; supply explicit mappings or enable reviewed type creation.')
            for plan in planned_types:
                rule = edition._rule_for(plan['category'])
                leave_type = env['hr.leave.type'].create({
                    'name': plan['name'], 'company_id': company_id,
                    'pb_policy_code': plan['code'], 'pb_policy_country_id': edition.country_id.id,
                    'pb_policy_category': rule.category, 'pb_pay_treatment': rule.pay_treatment,
                    'pb_paid_fraction': rule.paid_fraction, 'pb_pay_funding': rule.pay_funding,
                    'requires_allocation': plan['requires_allocation'], 'request_unit': 'day',
                    'leave_validation_type': 'both', 'allocation_validation_type': 'hr',
                    'include_public_holidays_in_duration': rule.counting in ('calendar', 'months'),
                })
                type_map[rule.category] = leave_type.id
            # Policy approval is manager then HR for future requests, including
            # existing explicitly selected ID types. Existing requests are not edited.
            for category, type_id in type_map.items():
                leave_type = env['hr.leave.type'].browse(type_id)
                code = 'RIZE:%s:%s:%s' % (company_id, country, category)
                if leave_type.pb_policy_code and leave_type.pb_policy_code != code:
                    raise UserError('This leave type is already bound to a different company policy category.')
                rule = edition._rule_for(category)
                leave_type.write({'pb_policy_code': code, 'pb_policy_country_id': edition.country_id.id,
                    'leave_validation_type': 'both',
                    'include_public_holidays_in_duration': rule.counting in ('calendar', 'months')})
            edition._bind_policy_types(type_map)
            group['type_mappings'] = type_map
            for employee in env['hr.employee'].browse(employee_ids):
                assigned = employee.pb_leave_policy_id
                if assigned and (assigned.code != edition.code or assigned.country_id != edition.country_id):
                    raise UserError('Employee %s already has another policy family or employment country; review the transfer.' % employee.id)
                values = {'pb_leave_policy_id': edition.id}
                review = reviews.get(employee.id)
                if review:
                    values['pb_policy_full_time_confirmed'] = review['confirmed']
                    values['pb_policy_eligibility_review_ref'] = review['reference']
                employee.write(values)
        result['groups'].append(group)
    return result


def seed_owner_approved_rize_scope(env, activation_date, apply=False):
    """The explicit 21 October 2026 owner decision, restricted to four schemes."""
    if env.cr.dbname != 'rize':
        raise UserError('This owner decision applies only to rize.')
    expected = {4760: ('Rize Vietnam Payroll', 'VN'), 6382: ('Rize India Payroll', 'IN'),
                7095: ('Rize Singapore Payroll', 'SG'), 7096: ('Rize Indonesia Payroll', 'ID')}
    Config = env['hr.formula.config']
    schemes = Config.browse(list(expected)).exists()
    if len(schemes) != 4 or any(not s.active or s.state != 'active' or s.name != expected[s.id][0]
                               or s.country_code != expected[s.id][1] for s in schemes):
        raise UserError('The four approved mainline payroll schemes changed; review the exact scope before activation.')
    employees = env['hr.employee'].search([('active', '=', True)])
    covered = employees.filtered(lambda employee: bool(Config.schemes_for_employee(employee) & schemes))
    if not covered:
        raise UserError('No active employees resolve to the four approved payroll schemes; review their scheme assignments.')
    country_reviews = {}
    for employee in covered:
        matching = Config.schemes_for_employee(employee) & schemes
        countries = set(matching.mapped('country_code'))
        if employee.payroll_country and employee.payroll_country not in countries:
            raise UserError('A covered employee payroll country conflicts with the paying scheme; review before activation.')
        if not employee.payroll_country:
            if len(countries) != 1:
                raise UserError('A missing payroll country cannot be resolved across multiple country schemes.')
            # The owner approved the employees covered by these exact schemes.
            # Use that recorded relationship, never nationality or a company
            # default, and do not silently rewrite the employee payroll record.
            country_reviews[employee.id] = {
                'country': next(iter(countries)),
                'reference': 'Owner-approved Rize paying schema assignment: %s; employee payroll country blank'
                             % ','.join(str(i) for i in sorted(matching.ids)),
            }
    evidence = 'Owner confirmed full-time policy eligibility on 2026-10-21 for current employees covered by four Rize payroll schemas'
    reviews = {employee.id: {'confirmed': True, 'reference': evidence} for employee in covered}
    type_maps = {}
    for scheme in schemes:
        type_maps.setdefault(scheme.company_id.id, {})[scheme.country_code] = {}
    # These seven IDs were individually observed in the read-only source audit.
    # Recheck labels and actual country codes rather than trusting numeric IDs.
    known_id = {'annual': (46, 'ID Annual Leaves'), 'wellness': (47, 'ID Sick Leaves'),
                'unpaid': (48, 'ID Unpaid Leaves'), 'marriage': (49, 'ID Marriage Leaves'),
                'maternity': (50, 'ID Maternity Leaves'), 'paternity': (51, 'ID Paternity Leaves'),
                'bereavement': (52, 'ID Bereavement Leaves')}
    id_companies = schemes.filtered(lambda s: s.country_code == 'ID').company_id
    if len(id_companies) > 1:
        raise UserError('Existing shared Indonesian leave types need an explicit company ownership review.')
    if id_companies:
        reviewed_map = {}
        for category, (type_id, name) in known_id.items():
            leave_type = env['hr.leave.type'].with_context(lang='en_US').browse(type_id).exists()
            if len(leave_type) != 1 or leave_type.name != name or leave_type.country_id.code != 'ID':
                raise UserError('An observed Indonesian leave type changed; review the mapping again.')
            reviewed_map[category] = type_id
        type_maps[id_companies.id]['ID'] = reviewed_map
    result = seed_rize_absence_policy(env, activation_date, full_time_reviews=reviews,
        country_type_mappings=type_maps, apply=apply, create_missing_types=True, employee_ids=covered.ids,
        employee_country_reviews=country_reviews)
    result['covered_schema_ids'] = schemes.ids
    result['owner_full_time_review_reference'] = evidence
    result['uncovered_active_employee_ids'] = (employees - covered).ids
    return result
