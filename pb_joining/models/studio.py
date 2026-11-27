from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.addons.pb_new_hire.models.docs_legs import PROPOSAL_CTX
from odoo.addons.pb_new_hire.models.studio import _int

# A recordset in an internal context cannot be supplied by a JSON client.
JOINING_CTX = 'pb_joining_studio_record'
RESOLVED = object()


class StudioDoor(models.AbstractModel):
    _inherit = 'pb.joining.board'

    @api.model
    def studio_door(self, joining_id):
        j = self.env['pb.new.hire']._checked_joining(joining_id)
        action = self.env['ir.actions.actions']._for_xml_id('pb_new_hire.action_new_hire_studio')
        action.update(context={'joining_id': j.id}, params={'joining_id': j.id})
        return action


class JoiningStudio(models.AbstractModel):
    _inherit = 'pb.new.hire'

    def _draft_keys(self):
        return super()._draft_keys() + ('joining_id',)

    def _checked_joining(self, joining_id, lock=False):
        self._gate()
        j = (
            self.env['pb.joining']
            .sudo()
            .search([('id', '=', _int(joining_id)), ('company_id', '=', self.env.company.id)], limit=1)
        )
        if not j:
            raise AccessError(_('You cannot open this joining.'))
        if lock:
            j._lock()
        if not j._can_add():
            raise UserError(_('Finish checking the joining before adding the employee.'))
        return j

    def _offer_row(self, offer):
        row = super()._offer_row(offer)
        j = (
            self.env['pb.joining']
            .sudo()
            .search([('offer_id', '=', offer.id), ('company_id', '=', self.env.company.id)], limit=1)
        )
        if j and j.state != 'cancelled':
            checked = j._can_add()
            label = (
                _('Link not opened')
                if not j.opened_at
                else (
                    _('Details %(percent)s%% in · checked', percent=j.progress)
                    if checked
                    else _('Details %(percent)s%% in', percent=j.progress)
                )
            )
            row['joining'] = {
                'id': j.id,
                'state': j.state,
                'progress': j.progress,
                'opened': bool(j.opened_at),
                'checked': checked,
                'label': label,
            }
        return row

    @api.model
    def joining_draft(self, joining_id):
        j = self._checked_joining(joining_id)
        result = self.offer_draft(j.offer_id.id) if j.offer_id else {'ok': True, 'draft': {}}
        if not result.get('ok'):
            if (
                j.offer_id
                and j.offer_id.state == 'signed'
                and j.offer_id.join_status in ('pending', 'changed', False)
            ):
                return {
                    'ok': False,
                    'message': _(
                        'Ask an HR colleague who can open this signed offer in Hiring to add the employee.'
                    ),
                }
            return result
        d = result['draft']
        d.update(
            joining_id=j.id,
            name=j.name,
            date_start=str(j.first_day),
            payroll_country=j.payroll_country,
            items={
                r.key: ('joining' if r.state == 'accepted' else 'ask')
                for r in j.item_ids
                if r.available and r.state in ('accepted', 'later')
            },
        )
        if not j.offer_id:
            d.update(
                personal=j.email or j.phone or '',
                job_title=j.job_title,
                department_id=j.department_id.id,
                parent_id=j.manager_id.id,
                parent_name=j.manager_id.name or '',
            )
        result['first'] = j._first()
        return result

    @api.model
    def details_options(self, draft):
        if not isinstance(draft, dict) or not draft.get('joining_id'):
            return super().details_options(draft)
        j = self._checked_joining(draft['joining_id'])
        ctx = self.with_context(**{JOINING_CTX: j})
        return super(JoiningStudio, ctx).details_options(draft)

    def _detail_items(self, code, first):
        specs = super()._detail_items(code, first)
        j = self.env.context.get(JOINING_CTX)
        if not isinstance(j, models.BaseModel) or j._name != 'pb.joining' or j.payroll_country != code:
            return specs
        rows = {r.key: r for r in j.item_ids if r.available and r.state == 'accepted'}
        selected = self.env.context.get('pb_joining_selected') or ()
        resolving = self.env.context.get('pb_joining_resolved') is RESOLVED
        for spec in specs:
            r = rows.get(spec['key'])
            if not r:
                continue
            if resolving:
                if r.key in selected:
                    # The server checks and files these attachments separately in the vault leg.
                    spec['upload'] = False
                    spec['fields'] = [f for f in spec['fields'] if f['name'] not in (r.none_fields or [])]
                continue
            summary = self.env['pb.joining.board']._item_row(j, r, spec, True)
            spec.update(
                default='joining',
                tallyAs={'joining': 'have'},
                joining={
                    'by': r.decided_by_id.name,
                    'on': str(r.decided_on or ''),
                    'first': j._first(),
                    'label': _('From %s', j._first()),
                    'line': _(
                        'Sent by %(first)s on %(day)s · accepted by %(hr)s',
                        first=j._first(),
                        day=self._day_words(j.submitted_at.date()),
                        hr=r.decided_by_id.name,
                    ),
                    'fields': summary['fields'],
                    'files': [a.name for a in r.attachment_ids],
                },
            )
        return specs

    def _resolved(self, d, files):
        j = self._checked_joining(d.get('joining_id'))
        if _int(d.get('offer_id')) != j.offer_id.id or d.get('payroll_country') != j.payroll_country:
            raise UserError(_('The offer and country of work must match the checked joining.'))
        choices = dict(d.get('items') or {})
        have = dict(d.get('have') or {})
        selected = {key for key, value in choices.items() if value == 'joining'}
        records = {r.key: r for r in j.item_ids if r.available and r.state == 'accepted'}
        if selected - records.keys():
            raise UserError(_('Only accepted items can come across from Joining.'))
        specs = {s['key']: s for s in j._catalogue()}
        for key in selected:
            r = records[key]
            spec = specs[key]
            boxes = (
                spec['fields']
                if key != 'bank'
                else [b for group in spec['bank']['fields'].values() for b in group]
            )
            for box in boxes:
                have.pop(box['name'], None)
            have.update(r.values or {})
            choices[key] = 'have'
        clean = dict(d, items=choices, have=have)
        if 'id_number' in selected and records['id_number'].from_hiring:
            card = records['id_number']
            clean['hiring_valid_until'] = (
                str(card.expiry_date) if card.expiry_date and not card.no_expiry else False
            )
        browser_files = [f for f in (files or []) if isinstance(f, dict) and f.get('key') not in selected]
        ctx = self.with_context(
            **{JOINING_CTX: j, 'pb_joining_selected': sorted(selected), 'pb_joining_resolved': RESOLVED}
        )
        return ctx, clean, browser_files

    def _validate_docs(self, d, files=None):
        if not d.get('joining_id'):
            return super()._validate_docs(d, files)
        ctx, clean, local = self._resolved(d, files)
        refused = super(JoiningStudio, ctx)._validate_docs(clean, local)
        if refused:
            return refused

        joining = ctx.env.context[JOINING_CTX]
        selected = set(ctx.env.context['pb_joining_selected'])
        catalogue = {spec['key']: spec for spec in joining._catalogue()}
        total = 0
        for row in joining.item_ids.filtered(lambda item: item.key in selected):
            upload = catalogue[row.key].get('upload')
            if not upload:
                continue
            rule = dict(upload)
            if row.key == 'id_number' and row.no_expiry:
                rule['needs_expiry'] = self.env.ref('pb_joining.cat_permanent_id').requires_expiry
            files_to_check = [
                {
                    'data': a.datas,
                    'mime': a.mimetype,
                    'issue_date': str(row.issue_date or ''),
                    'expiry_date': str(row.expiry_date or ''),
                }
                for a in row.attachment_ids
            ]
            if not files_to_check and row.need != 'optional' and not row.none_fields:
                files_to_check.append({})
            for staged in files_to_check:
                raw, problem = self._file_problem({'upload': rule}, staged, total)
                if problem:
                    return self._refuse('docs', 'file-' + row.key, problem)
                total += len(raw)
        return None

    def _values_docs(self, d, vals, files=None):
        if not d.get('joining_id'):
            return super()._values_docs(d, vals, files)
        ctx, clean, local = self._resolved(d, files)
        result = super(JoiningStudio, ctx)._values_docs(clean, vals, local)
        result.update(
            pb_nh_joining_id=ctx.env.context[JOINING_CTX].id,
            pb_nh_joining_keys=ctx.env.context['pb_joining_selected'],
        )
        return result

    @api.model
    def send(self, draft, files=None):
        if not isinstance(draft, dict) or not draft.get('joining_id'):
            return super().send(draft, files)
        j = self._checked_joining(draft['joining_id'], lock=True)
        studio = self.with_context(**{JOINING_CTX: j})
        with self.env.cr.savepoint() as checkpoint:
            result = super(JoiningStudio, studio).send(draft, files)
            if not result.get('ok'):
                checkpoint.rollback()
            return result


class JoiningProposal(models.Model):
    _inherit = 'pb.newhire.proposal'

    @api.model_create_multi
    def create(self, vals_list):
        j = self.env.context.get(JOINING_CTX)
        rows = super().create(vals_list)
        for row in rows:
            vals = (row.payload() or {}).get('values') or {}
            jid = vals.get('pb_nh_joining_id')
            if jid:
                if (
                    not isinstance(j, models.BaseModel)
                    or j._name != 'pb.joining'
                    or j.id != jid
                    or j.company_id != row.company_id
                    or j.proposal_id
                ):
                    raise AccessError(_('Use Add as employee on the Joining board.'))
                j.proposal_id = row
        return rows

    def _apply_employee(self):
        if not (self.payload().get('values') or {}).get('pb_nh_joining_id'):
            return super()._apply_employee()
        with self.env.cr.savepoint():
            answer = super()._apply_employee()
            legs = answer.get('legs') or []
            if any(not leg['ok'] and leg['key'] == 'details' for leg in legs):
                raise UserError(_('The checked details could not be saved. Review the hire and try again.'))
            done = [leg['message'] for leg in legs if leg['ok'] and leg['key'] != 'joining_close']
            answer['legs_summary'] = _('Ready: %s.', ', '.join(done)) if done else ''
            return answer

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') in ('draft', 'cancelled', 'withdrawn', 'returned', 'rejected'):
            self.env['pb.joining'].sudo().search(
                [('proposal_id', 'in', self.ids), ('state', '=', 'to_check')]
            ).write({'proposal_id': False})
        return result


class JoiningLegs(models.AbstractModel):
    _inherit = 'pb.new.hire.legs'

    def _leg_order(self):
        order = list(super()._leg_order())
        index = order.index('papers') + 1
        order[index:index] = ['joining_files', 'joining_signs']
        return (*order, 'joining_close')

    def _failed(self, employee, key, reason):
        if key in ('joining_files', 'joining_signs', 'joining_close'):
            raise UserError(_('The papers could not be filed. Review the hire and try again.'))
        return super()._failed(employee, key, reason)

    def _leg_joining(self, employee, vals):
        if not vals.get('pb_nh_joining_id'):
            return self.env['pb.joining']
        j = self.env['pb.joining'].sudo().browse(_int(vals['pb_nh_joining_id'])).exists()
        if (
            not j
            or employee.company_id != j.company_id
            or not j.proposal_id
            or j.proposal_id.id != _int(self.env.context.get(PROPOSAL_CTX))
            or j.employee_id
            and j.employee_id != employee
        ):
            raise AccessError(_('The joining does not belong to this approved hire.'))
        return j

    def _vault_copy(self, employee, cat, attachments, label, issue=False, expiry=False):
        if not attachments:
            return
        self.env['pb.people'].vault_upload_batch(
            employee.id,
            cat.id,
            [
                {
                    'payload': {'name': a.name, 'title': label, 'mime': a.mimetype, 'data': a.datas.decode()},
                    'issue_date': str(issue) if issue else False,
                    'expiry_date': str(expiry) if expiry else False,
                }
                for a in attachments
            ],
        )

    def _leg_joining_files(self, employee, values, state):
        j = self._leg_joining(employee, values)
        if not j or j.employee_id:
            return
        specs = {s['key']: s for s in j._catalogue()}
        for r in j.item_ids.filtered(
            lambda r: r.key in values.get('pb_nh_joining_keys', []) and r.state == 'accepted'
        ):
            spec = specs[r.key]
            att = r.attachment_ids
            if r.key == 'id_number' and r.no_expiry and r.from_hiring and not att:
                held = next(
                    (
                        x
                        for x in self.env['pb.new.hire']._offer_items(j.offer_id)
                        if x['key'] == 'identity' and x['received']
                    ),
                    {},
                )
                att = held.get('attachment') or att
            if not att:
                continue
            upload = spec.get('upload') or spec.get('received_upload') or {}
            category = (
                self.env.ref('pb_joining.cat_permanent_id')
                if r.key == 'id_number' and r.no_expiry
                else self.env['pb.employee.document.category'].browse(
                    upload.get('category_id') or spec.get('category_id')
                )
            )
            self._vault_copy(employee, category, att, spec['label'], r.issue_date, r.expiry_date)
        state['joining_files'] = True

    def _leg_joining_signs(self, employee, values, state):
        j = self._leg_joining(employee, values)
        if not j or j.employee_id:
            return
        category = self.env.ref('pb_employee_vault.cat_labor_contract')
        for s in j.sign_ids:
            if not s.signed_attachment_id:
                raise UserError(_('A signed copy is missing.'))
            self._vault_copy(employee, category, s.signed_attachment_id, s.paper_name, s.signed_on.date())
        state['joining_signs'] = True

    def _leg_joining_close(self, employee, values, state):
        j = self._leg_joining(employee, values)
        if not j or j.employee_id:
            return
        if not state.get('joining_files') or not state.get('joining_signs'):
            raise UserError(_('The papers still need to be filed.'))
        j.write({'employee_id': employee.id, 'added_at': fields.Datetime.now(), 'state': 'added'})
        return _("%s's details, papers and signed papers came across from the Joining board.", j._first())

    def run(self, employee, contract, values):
        legs, summary = super().run(employee, contract, values)
        if values.get('pb_nh_joining_id') and self._leg_joining(employee, values).employee_id != employee:
            # The ordinary runner isolates each leg. For a joining, approval must be retryable
            # with every original still intact if the vault could not receive a copy.
            raise UserError(_('The papers could not be filed. Review the hire and try again.'))
        return legs, summary
