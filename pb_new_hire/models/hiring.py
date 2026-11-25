# -*- coding: utf-8 -*-
"""NEWHIRE P4 Part A — From Hiring, Many at once, and "Confirm they joined".

STEP 1's TILES. "From Hiring" lists the signed offers waiting to join
(FACTS_ONBOARD §K2: `state == 'signed'`, join status pending / changed / not
set), in the user's OWN rights (no sudo on the search), company-scoped. Each
row says what the candidate already sent through Hiring's document request
(green) and what is still missing (grey), in the studio's own item words, and
the background check's sentence when it is not ready (a warning, as in
Hiring). "Bring across" turns an offer into a draft.

WHAT "RECEIVED" MEANS without touching `pb_hiring`'s tables (D10). A request
item carries no category (§B4), so it is matched by NAME to the six seeded
request lines (`pb_hiring.doc_*`), in every active language:

    doc_id      identity   → step 5's ID row (file only — the number is
                             still asked or typed)
    doc_degree  degree     → the certificate paper row
    doc_tax     tax        → the tax-card row (file only)
    doc_bank    bank       → the bank row: a bank request a second person
                             approves (FACTS_ONBOARD §D6)
    doc_photo   photo      → the person's photo
    doc_payslip payslip    → "Other papers" (comes across, satisfies nothing)
    anything else          → "Other papers"

THE APPLY — two welcome legs (welcome_legs.py LEG_ORDER):

    hiring        right after `papers`: every received file becomes an
                  unverified `pb.employee.document` (a COPY; the original
                  stays on the Hiring request), the photo becomes the
                  picture, the bank paper is read and sent for a second
                  approval only when it reads as a valid account
    hiring_close  after the joining checklist, buddy and equipment legs:
                  the offer is linked to the studio's employee and contract
                  the way Hiring links them (`offer.employee_id`,
                  `offer.contract_id`) and Hiring's OWN `action_confirm_joined`
                  runs, so its remaining legs run too (applicant hired, pay
                  package, benefits, signed papers filed, buddy and laptop
                  hand-over, requisition filled, hire date, "tell them").
                  The two legs that would DUPLICATE or contradict the studio
                  (`_ensure_login`, `_ensure_case`) only link what the studio
                  made, for that one call (`NH_JOIN_CTX`).

Never an edit in `pb_hiring`: everything is an inherited override here.
"""
import logging
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .studio_docs import ID_CATEGORY, TAX_CATEGORY
from .docs_legs import PROPOSAL_CTX
from .welcome_legs import LegFailed

_logger = logging.getLogger(__name__)

#: "Hiring is closing this offer for the studio's employee <id>": its login
#: and checklist legs link what the studio made instead of making their own.
NH_JOIN_CTX = 'pb_nh_joining_employee_id'

#: Step 5's received items for this draft (`{item key: {on, label}}`), read
#: by the `_detail_items` override for the length of one call.
RECEIVED_CTX = 'pb_nh_received'

#: P5a: HR chose the buddy in step 6, so Hiring's own buddy hand-over stands
#: aside at the close (HR's choice wins; Hiring's applies only when step 6
#: left the buddy empty).
NH_BUDDY_CTX = 'pb_nh_buddy_chosen'

#: The seeded request lines and what they are in the studio's words.
TEMPLATES = (
    ('pb_hiring.doc_id', 'identity'),
    ('pb_hiring.doc_degree', 'degree'),
    ('pb_hiring.doc_payslip', 'payslip'),
    ('pb_hiring.doc_bank', 'bank'),
    ('pb_hiring.doc_photo', 'photo'),
    ('pb_hiring.doc_tax', 'tax'),
)
CERT_CATEGORY = 'pb_employee_vault.cat_certificate'
OTHER_CATEGORY = 'pb_employee_vault.cat_other'
MAX_OFFERS = 200


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _norm(text):
    text = unicodedata.normalize('NFKD', str(text or ''))
    return ' '.join(text.split()).casefold()


class PbNewHireHiring(models.AbstractModel):
    _inherit = 'pb.new.hire'

    # ============================================================ features
    @api.model
    def _hiring_on(self):
        """The "From Hiring" tile exists only where Hiring's offers exist and
        this user may read them (H8)."""
        if 'pb.hiring.offer' not in self.env:
            return False
        try:
            return bool(self.env['pb.hiring.offer'].has_access('read'))
        except Exception:                       # noqa: BLE001 — a probe
            return False

    @api.model
    def _bank_reader_on(self):
        """Is a document reader set up for this company — the very setting
        the bank screens read (`payroll.ai.config.get_config_for_purpose(
        'doc_ocr')`, `pb_bank_ocr` `_provider_info`)? Feature-checked: no
        reader model, no reader."""
        if 'payroll.ai.config' not in self.env:
            return False
        try:
            Cfg = self.env['payroll.ai.config'].sudo().with_company(self._company())
            return bool(Cfg.get_config_for_purpose('doc_ocr'))
        except Exception:                       # noqa: BLE001 — a probe
            return False

    @api.model
    def _features(self):
        out = super()._features()
        out['hiring'] = self._hiring_on()
        out['many'] = 'pb.updates.desk' in self.env
        return out

    @api.model
    def load(self, prefill=None):
        out = super().load(prefill)
        hiring = {'on': self._hiring_on(), 'count': 0}
        if hiring['on']:
            try:
                hiring['count'] = self.env['pb.hiring.offer'].search_count(
                    self._offer_domain(), limit=MAX_OFFERS)
            except AccessError:
                hiring['on'] = False
        out['hiring'] = hiring
        return out

    # ============================================================ the offers
    @api.model
    def _offer_domain(self):
        return [('state', '=', 'signed'),
                ('join_status', 'in', ('pending', 'changed', False)),
                ('company_id', '=', self._company().id)]

    @api.model
    def _offer(self, offer_id):
        """One waiting offer the user may read, else an empty recordset."""
        if not self._hiring_on() or not _int(offer_id):
            return self.env['pb.hiring.offer'] if 'pb.hiring.offer' in self.env else None
        return self.env['pb.hiring.offer'].search(
            self._offer_domain() + [('id', '=', _int(offer_id))], limit=1)

    @api.model
    def _template_names(self):
        """`{normalised name: key}` of the six seeded request lines, in the
        English text and in every active language."""
        out = {}
        langs = [code for code, _name in self.env['res.lang'].sudo().get_installed()]
        for xmlid, key in TEMPLATES:
            tmpl = self.env.ref(xmlid, raise_if_not_found=False)
            if not tmpl:
                continue
            for lang in set(langs) | {'en_US'}:
                name = tmpl.sudo().with_context(lang=lang).name
                if name:
                    out.setdefault(_norm(name), key)
        return out

    @api.model
    def _offer_items(self, offer):
        """The offer's requested papers: `[{key, item, received, on,
        attachment}]` — `key` one of the template keys or `other`."""
        names = self._template_names()
        rows = []
        for req in offer.sudo().docreq_ids:
            for item in req.item_ids.sorted(lambda i: (i.sequence, i.id)):
                att = item.attachment_id
                received = bool(att and item.received_at)
                rows.append({'key': names.get(_norm(item.name), 'other'), 'item': item,
                             'received': received,
                             'on': fields.Datetime.to_datetime(item.received_at).date()
                             if received else False,
                             'attachment': att if received else self.env['ir.attachment']})
        return rows

    @api.model
    def _key_words(self, key, item_name=''):
        """A request line in the studio's own words."""
        return {
            'identity': _("Identity card"),
            'degree': _("Highest certificate"),
            'tax': _("Tax card"),
            'bank': _("Bank account"),
            'photo': _("Photo"),
            'payslip': _("Last payslip"),
        }.get(key) or (item_name or _("Other paper"))

    @api.model
    def _offer_manager(self, offer):
        boss = offer.reporting_manager_id or offer.requisition_id.reporting_manager_id
        return self._person(boss.id) if boss else self.env['hr.employee']

    @api.model
    def _offer_wage(self, offer):
        """The offer's basic pay (Hiring's own `_basic_line`, the line its
        contract leg writes the wage from) and its money."""
        line = offer.sudo()._basic_line() if hasattr(offer, '_basic_line') else None
        cur = offer.sudo().currency_id
        return (float(line.amount or 0.0) if line else 0.0), cur

    @api.model
    def _offer_row(self, offer):
        o = offer.sudo()
        req = o.requisition_id
        team = self._team(req.department_id.id) if req.department_id else self.env['hr.department']
        job = self._job(req.job_id.id) if req.job_id else self.env['hr.job']
        boss = self._offer_manager(o)
        wage, cur = self._offer_wage(o)
        received, missing = [], []
        for row in self._offer_items(o):
            chip = {'key': row['key'], 'label': self._key_words(row['key'], row['item'].name)}
            (received if row['received'] else missing).append(chip)
        bgv = {'ok': True, 'sentence': ''}
        if o.bgv_id:
            try:
                ok, sentence = o.bgv_id.check_ready()
                bgv = {'ok': bool(ok), 'sentence': sentence or ''}
            except Exception:                   # noqa: BLE001 — a warning, never a gate
                _logger.warning('new hire: background check of offer %s unreadable', o.id,
                                exc_info=True)
        first_day = o.expected_join_date or o.start_date
        return {
            'offer_id': o.id, 'name': o.candidate_name or '', 'job': o.job_title or job.name or '',
            'team': team.name or '', 'team_id': team.id or False, 'job_id': job.id or False,
            'manager_id': boss.id or False, 'manager_name': boss.name or '',
            'first_day': fields.Date.to_string(first_day) if first_day else False,
            'wage': wage, 'wage_currency': {'name': cur.name or '', 'symbol': cur.symbol or cur.name or '',
                                            'position': cur.position or 'after',
                                            'decimals': cur.decimal_places if cur else 2},
            'signed_on': fields.Date.to_string(o.signed_on) if o.signed_on else False,
            'received': received, 'missing': missing, 'bgv': bgv,
        }

    @api.model
    def hiring_offers(self):
        """Step 1's "From Hiring" list (A.1)."""
        self._gate()
        if not self._hiring_on():
            return {'on': False, 'rows': []}
        try:
            offers = self.env['pb.hiring.offer'].search(self._offer_domain(),
                                                        order='id desc', limit=MAX_OFFERS)
        except AccessError:
            return {'on': False, 'rows': []}
        rows = [self._offer_row(o) for o in offers]
        rows.sort(key=lambda r: (r['first_day'] or '9999', r['name'].casefold()))
        return {'on': True, 'rows': rows}

    @api.model
    def offer_draft(self, offer_id):
        """"Bring across": the draft values an offer gives (A.1). The wage
        comes only when the offer's money is the money of the team's country
        of work; otherwise the screen says so and asks for it."""
        self._gate()
        offer = self._offer(offer_id)
        if not offer:
            return {'ok': False, 'message': _(
                "That offer is no longer waiting to join. It may have been confirmed or "
                "dropped in Hiring.")}
        row = self._offer_row(offer)
        o = offer.sudo()
        app = o.applicant_id
        draft = {'name': row['name'], 'offer_id': o.id}
        personal = (app.email_from or '').strip() or (getattr(app, 'partner_phone', '') or '').strip()
        if personal:
            draft['personal'] = personal
        if row['first_day']:
            draft['date_start'] = row['first_day']
        if row['team_id']:
            draft['department_id'] = row['team_id']
        if row['job_id']:
            draft['job_id'] = row['job_id']
        elif o.job_title:
            draft['job_title'] = o.job_title
        if row['manager_id']:
            draft['parent_id'] = row['manager_id']
            draft['parent_name'] = row['manager_name']
        buddy = o.buddy_employee_ids[:1] if 'buddy_employee_ids' in o._fields else None
        if buddy and self._person(buddy.id):
            draft['buddy_id'] = buddy.id
            draft['buddy_name'] = buddy.name or ''
        note = ''
        if row['wage'] > 0:
            decided = self.decides(row['team_id'], False) if row['team_id'] else {}
            code = (decided.get('scheme') or {}).get('country_code') or ''
            mine = self._currency_for(code) if code else self._company_currency()
            if row['wage_currency']['name'] and row['wage_currency']['name'] != mine.get('name'):
                note = _("The offer's pay is in %(theirs)s. Type the monthly wage in %(mine)s.",
                         theirs=row['wage_currency']['name'], mine=mine.get('name') or '')
            else:
                draft['wage'] = row['wage']
        return {'ok': True, 'draft': draft, 'offer': row, 'wage_note': note}

    # ============================================================ step 5: received
    @api.model
    def _received_for(self, d):
        """`{step 5 item key: {on, label}}` for the draft's offer, worked out
        again from Hiring every time (never from the screen)."""
        offer_id = _int((d or {}).get('offer_id'))
        if not offer_id or not self._hiring_on():
            return {}
        offer = self.env['pb.hiring.offer'].sudo().browse(offer_id).exists()
        if not offer or offer.company_id != self._company() or offer.state != 'signed':
            return {}
        out = {}
        for row in self._offer_items(offer):
            if row['received'] and row['key'] in ('identity', 'degree', 'tax', 'bank'):
                out.setdefault(row['key'], {'on': fields.Date.to_string(row['on']),
                                            'label': row['item'].name or ''})
        return out

    @api.model
    def _detail_items(self, code, first):
        items = super()._detail_items(code, first)
        received = self.env.context.get(RECEIVED_CTX) or {}
        if not received:
            return items
        cert = self.env.ref(CERT_CATEGORY, raise_if_not_found=False)
        for item in items:
            hit = None
            if item['key'] == 'id_number' and item.get('merged'):
                hit = received.get('identity')
            elif item['key'] == 'tax_number' and item.get('merged'):
                hit = received.get('tax')
            elif item['key'] == 'bank':
                hit = received.get('bank')
            elif cert and item.get('category_id') == cert.id and item['key'].startswith('paper-'):
                hit = received.get('degree')
            if not hit:
                continue
            day = fields.Date.to_date(hit['on'])
            item['received'] = {'on': hit['on'],
                                'line': _("Received in Hiring · %s",
                                          self._day_words(day))}
            if item['key'] == 'bank':
                if self._bank_reader_on():
                    # the paper becomes a bank request (read, then approved by
                    # a second person); typing or asking stay possible
                    item['can_hiring'] = True
                    item['default'] = 'hiring'
                else:
                    # P5a: nothing here can read the paper, so it is filed on
                    # the record and the account details are asked for
                    item['default'] = 'ask' if item['can_ask'] else 'have'
                    item['received']['note'] = _(
                        "%s's bank paper will be on their record. The account details are "
                        "asked for in the welcome link.", first)
            elif item.get('merged'):
                # the card came across: only the number is still open
                item['received_upload'] = item['upload']
                item['upload'] = False
                item['can_number'] = False
                item['ask_label'] = item['fields'][0]['label'] if item['fields'] else item['label']
                if item['key'] == 'id_number' and (item['received_upload'] or {}).get('needs_expiry'):
                    # P5a: the card is filed with its own kind of paper once
                    # HR gives the date it is valid until (Hiring never asks)
                    item['received_until'] = True
            else:
                item['received_upload'] = item['upload']
                item['upload'] = False
                item['can_ask'] = False
                item['ask_why_not'] = _("It came across from Hiring.")
                item['default'] = 'have'
        return items

    @api.model
    def _day_words(self, day):
        from odoo.tools.misc import format_date
        return format_date(self.env, day, date_format='d MMM') if day else ''

    def _with_received(self, d):
        return self.with_context(**{RECEIVED_CTX: self._received_for(d)})

    @api.model
    def details_options(self, draft):
        d = self._clean(draft) if isinstance(draft, dict) else {}
        return super(PbNewHireHiring, self._with_received(d)).details_options(draft)

    @api.model
    def _validate_docs(self, d, files=None):
        me = self._with_received(d)
        refused = super(PbNewHireHiring, me)._validate_docs(d, files)
        if refused:
            return refused
        raw = str(d.get('hiring_valid_until') or '').strip()
        if not raw or not (me.env.context.get(RECEIVED_CTX) or {}).get('identity'):
            return None
        day = self._day(raw)
        if not day:
            return self._refuse('docs', 'hiring_valid_until', _("That date does not look right."))
        if day < fields.Date.context_today(self):
            return self._refuse('docs', 'hiring_valid_until', _(
                "That date has passed, so the card is no longer valid. Leave the date empty to file "
                "it later, or ask %s for a card that is still valid.", self._first_of(d.get('name'))))
        return None

    @api.model
    def _values_docs(self, d, vals, files=None):
        me = self._with_received(d)
        vals = super(PbNewHireHiring, me)._values_docs(d, vals, files)
        received = me.env.context.get(RECEIVED_CTX) or {}
        if not received:
            return vals
        items = {i['key']: i for i in me._detail_items(vals.get('payroll_country'),
                                                       me._first_of(vals.get('name')))}
        for ask in vals.get('pb_nh_asks') or []:
            item = items.get(ask['key']) or {}
            if item.get('received') and item.get('ask_label'):
                ask['label'] = item['ask_label']            # only the number is asked
                ask['kind'] = 'number'
        choices = me._doc_choices(list(items.values()), d)
        until = self._day(str(d.get('hiring_valid_until') or '').strip())
        if until and received.get('identity') and until >= fields.Date.context_today(self):
            vals['pb_nh_hiring_id_until'] = fields.Date.to_string(until)
        if choices.get('bank') == 'hiring':
            vals['pb_nh_hiring_bank'] = True
            vals.setdefault('pb_nh_names', {}).setdefault('details', []).append(
                [_("Bank"), _("From the paper sent in Hiring")])
        return vals

    # ============================================================ send
    @api.model
    def _validate(self, d):
        refused = super()._validate(d)
        if refused or not _int(d.get('offer_id')):
            return refused
        if not self._offer(d.get('offer_id')):
            return self._refuse('who', 'offer_id', _(
                "The offer brought across from Hiring is no longer waiting to join. "
                "Start again, or carry on without it."))
        return None

    @api.model
    def _values(self, d):
        vals, decided = super()._values(d)
        offer = self._offer(d.get('offer_id')) if _int(d.get('offer_id')) else None
        if offer:
            vals['pb_nh_offer_id'] = offer.id
            vals.setdefault('pb_nh_names', {})['offer'] = offer.sudo().name or ''
        return vals, decided

    # ============================================================ many at once
    @api.model
    def many_at_once(self):
        """"Many at once" opens the Updates desk on its new-employee sheet,
        or says why it cannot (H9)."""
        self._gate()
        if 'pb.updates.desk' not in self.env:
            return {'ok': False, 'message': _("The joiners sheet is not available on this site.")}
        Desk = self.env['pb.updates.desk']
        try:
            Desk._gate()
        except AccessError:
            return {'ok': False, 'message': _(
                "Updates is not open to you. Ask an administrator for the Updates "
                "permission in Access.")}
        refusal = Desk._joiner_refusal(1) if hasattr(Desk, '_joiner_refusal') else ''
        if refusal:
            return {'ok': False, 'message': refusal}
        return {'ok': True, 'action': 'pb_updates.action_pb_updates_desk',
                'context': {'pb_nh_joiners_sheet': True}}


class PbNewHireProposalHiring(models.Model):
    _inherit = 'pb.newhire.proposal'

    def _pb_nh_welcome_rows(self, values, names):
        rows = super()._pb_nh_welcome_rows(values, names)
        if values.get('pb_nh_offer_id'):
            rows.insert(0, (_('From Hiring'), '', names.get('offer') or _('A signed offer')))
        return rows


class PbNewHireLegsHiring(models.AbstractModel):
    _inherit = 'pb.new.hire.legs'

    # ================================================================ helpers
    @api.model
    def _hiring_offer(self, employee, values):
        """The offer of this hire, re-validated now (NH8). None when there is
        none; a LegFailed when it can no longer be closed (H7)."""
        offer_id = _int(values.get('pb_nh_offer_id'))
        if not offer_id or 'pb.hiring.offer' not in self.env:
            return None
        offer = self.env['pb.hiring.offer'].sudo().browse(offer_id).exists()
        if not offer:
            raise LegFailed(_("the offer was removed from Hiring before approval."))
        if offer.company_id and offer.company_id != employee.company_id:
            raise LegFailed(_("the offer belongs to another company."))
        if offer.state == 'joined' and offer.employee_id == employee:
            return offer
        if offer.state != 'signed':
            word = dict(offer._fields['state']._description_selection(self.env)).get(
                offer.state, offer.state)
            raise LegFailed(_("the offer %(ref)s is no longer signed (it is now “%(state)s”), "
                              "so nothing was taken from it.", ref=offer.name or '', state=word))
        if offer.employee_id and offer.employee_id != employee:
            raise LegFailed(_("the offer %(ref)s already belongs to %(name)s.",
                              ref=offer.name or '', name=offer.employee_id.name or ''))
        return offer

    @api.model
    def _hiring_category(self, key, code):
        """The vault category a received paper is filed in."""
        Studio = self.env['pb.new.hire']
        if key == 'identity':
            id_cat = self.env.ref(ID_CATEGORY, raise_if_not_found=False)
            paper = next((p for p in Studio._papers_for(code) if id_cat and p['category'] == id_cat), None)
            return paper['category'] if paper else id_cat
        if key == 'degree':
            return self.env.ref(CERT_CATEGORY, raise_if_not_found=False)
        if key == 'tax':
            return self.env.ref(TAX_CATEGORY, raise_if_not_found=False) \
                or self.env.ref(OTHER_CATEGORY, raise_if_not_found=False)
        return self.env.ref(OTHER_CATEGORY, raise_if_not_found=False)

    @api.model
    def _file_copy(self, employee, att, category, title, expiry=False):
        """A COPY of a Hiring file as an unverified document of the person —
        the shape Hiring's own `_file_signed_copy` makes. `expiry`: the date
        HR typed in step 5 (P5a, the identity card)."""
        Doc = self.env['pb.employee.document'].sudo()
        copy = att.sudo().copy({'res_model': 'pb.employee.document', 'res_id': 0,
                                'name': att.name or title})
        vals = {'employee_id': employee.id, 'category_id': category.id,
                'name': title, 'attachment_id': copy.id,
                'issue_date': fields.Date.context_today(self),
                'company_id': employee.company_id.id}
        if expiry:
            vals['expiry_date'] = expiry
        doc = Doc.create(vals)
        copy.write({'res_id': doc.id})
        return doc

    @api.model
    def _hiring_bank(self, employee, att):
        """The bank paper → a bank request. Sent for the second approval
        only when the reading is a valid account; never invented."""
        # Made AS the person who sent the hire, the way FS-16 makes the typed
        # bank details (`_pb_hold_new_hire`): the approval engine counts the
        # request's creator as one who prepared it, so the second approval is
        # truly someone else's. sudo for the documented role gap (NH6): HR
        # approving a hire need not hold the bank screen's own roles.
        proposal = self.env['pb.newhire.proposal'].sudo().browse(
            _int(self.env.context.get(PROPOSAL_CTX))).exists()
        proposer = proposal.user_id or self.env.user
        Bank = self.env['pb.bank.ocr'].with_user(proposer).sudo()
        rid = Bank.create_from_upload({'name': att.name or 'bank-paper', 'mime': att.mimetype,
                                       'data': att.datas, 'employee_id': employee.id})
        try:
            with self.env.cr.savepoint():
                Bank.run_ocr(rid)
        except Exception:                       # noqa: BLE001 — unread is a state, not a crash
            _logger.info('new hire: the Hiring bank paper of %s could not be read', employee.id,
                         exc_info=True)
        req = self.env['pb.bank.change.request'].sudo().browse(rid)
        Wizard = self.env['pb.people.onboard.wizard']
        entered = Wizard._pb_bank_entered({'bank_name': req.x_bank_name or '',
                                           'account_number': req.x_account_number or '',
                                           'account_holder': req.x_account_name or ''})
        if req.x_account_number and entered and not Wizard._pb_bank_problem(entered):
            try:
                with self.env.cr.savepoint():
                    Bank.do_action(rid, 'submit')
                return True, req
            except Exception:                   # noqa: BLE001 — stays a draft to finish
                _logger.info('new hire: the Hiring bank request %s was not sent', rid, exc_info=True)
        return False, req

    # ================================================================ the files
    @api.model
    def _leg_hiring(self, employee, values, state):
        offer = self._hiring_offer(employee, values)
        if not offer:
            return False
        code = values.get('payroll_country') or ''
        Studio = self.env['pb.new.hire']
        filed, photo, bank_text, amber, held = 0, False, '', '', []
        for row in Studio._offer_items(offer):
            if not row['received']:
                continue
            att = row['attachment']
            key = row['key']
            title = Studio._key_words(key, row['item'].name)
            if key == 'photo':
                if not employee.image_1920 and (att.mimetype or '').startswith('image/'):
                    employee.with_context(tracking_disable=True).write({'image_1920': att.datas})
                    photo = True
                continue
            if key == 'bank' and values.get('pb_nh_hiring_bank') and 'pb.bank.ocr' in self.env:
                sent, _req = self._hiring_bank(employee, att)
                if sent:
                    bank_text = _("bank account from the Hiring paper, waiting for a second approval")
                else:
                    amber = _("The bank paper came across but could not be read. Open it in Bank "
                              "requests to finish.")
                continue
            if key == 'bank':
                # no reading asked for (or nothing here reads papers): the
                # paper itself is filed on the record (P5a)
                title = _("Bank paper")
            category = self._hiring_category(key, code)
            if not category:
                continue
            expiry = values.get('pb_nh_hiring_id_until') if key == 'identity' else False
            if category.requires_expiry and not expiry:
                # Hiring keeps no valid-until date, and none is invented
                held.append(title)
                continue
            try:
                with self.env.cr.savepoint():
                    self._file_copy(employee, att, category, title, expiry=expiry)
                filed += 1
            except Exception:                   # noqa: BLE001 — one paper never stops the others
                _logger.info('new hire: Hiring paper %s not filed for %s', title, employee.id,
                             exc_info=True)
                held.append(title)
        bits = []
        if filed:
            bits.append(_("1 paper from Hiring") if filed == 1 else _("%s papers from Hiring", filed))
        if photo:
            bits.append(_("the photo from Hiring"))
        if bank_text:
            bits.append(bank_text)
        if held:
            amber = ' '.join(filter(None, [amber, _(
                "%s needs a valid-until date, so it was not filed. Add it from the employee's side "
                "panel, Documents; the file is still on the offer in Hiring.", ', '.join(held))]))
        if amber:
            return {'amber': True, 'message': amber, 'done': ', '.join(bits)}
        return ', '.join(bits) or False

    # ================================================================ the close
    @api.model
    def _leg_hiring_close(self, employee, values, state):
        offer = self._hiring_offer(employee, values)
        if not offer:
            return False
        if offer.state == 'joined':
            return _("Hiring shows %s as joined", employee.name or '')
        link = {'employee_id': employee.id}
        contract = state.get('contract')
        if contract and not offer.contract_id:
            link['contract_id'] = contract.id
        offer.write(link)                       # how Hiring itself links them
        day = values.get('date_start') or fields.Date.context_today(self)
        ctx = {NH_JOIN_CTX: employee.id, NH_BUDDY_CTX: bool(_int(values.get('buddy_id')))}
        offer.with_context(**ctx).action_confirm_joined(joined_on=day)
        offer.invalidate_recordset(['state'])
        if offer.state != 'joined':
            raise LegFailed(_("Hiring did not mark the offer as joined."))
        return _("Hiring shows %s as joined", employee.name or '')

    @api.model
    def _failed(self, employee, key, reason):
        sentences = {
            'hiring': _("The papers from Hiring could not be brought across: %s They are still "
                        "on the offer in Hiring."),
            'hiring_close': _("Hiring could not be told that they joined: %s Confirm it in "
                              "Hiring with Confirm without the form."),
        }
        if key not in sentences:
            return super()._failed(employee, key, reason)
        message = sentences[key] % reason
        try:
            employee.message_post(body=message)
        except Exception:                       # noqa: BLE001 — the note is a courtesy
            _logger.warning('new hire: could not note a failed leg on %s', employee.id,
                            exc_info=True)
        return {'key': key, 'ok': False, 'message': message}


class PbHiringOfferNewHire(models.Model):
    """Hiring's own close, run by the studio for an employee it already made:
    the legs that would make a SECOND sign-in or a SECOND joining checklist
    (or one HR chose not to have) only link what exists — for that one call."""
    _inherit = 'pb.hiring.offer'

    def _pb_nh_joining(self):
        wanted = self.env.context.get(NH_JOIN_CTX)
        return bool(wanted) and self.employee_id.id == wanted

    def _ensure_login(self):
        if not self._pb_nh_joining():
            return super()._ensure_login()
        user = self.employee_id.sudo().pb_portal_user_id or self.employee_id.sudo().user_id
        if user:
            self.sudo().write({'login_user_id': user.id})
        return False

    def _ensure_case(self):
        if not self._pb_nh_joining():
            return super()._ensure_case()
        case = self.env['pb.journey.case'].sudo().search([
            ('employee_id', '=', self.employee_id.id), ('case_type', '=', 'onboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold'))], order='id desc', limit=1)
        if case:
            self.sudo().write({'case_id': case.id})
        return case

    def _hand_over_buddy(self):
        """P5a ruling: when HR chose the buddy in step 6, HR's choice stands
        (the studio's buddy leg made it); Hiring's hand-over runs only when
        step 6 left the buddy empty."""
        if self._pb_nh_joining() and self.env.context.get(NH_BUDDY_CTX):
            return 'studio'
        return super()._hand_over_buddy()

    def _ensure_contract(self):
        if not self._pb_nh_joining() or self.contract_id:
            return super()._ensure_contract()
        contract = self.env['hr.contract'].sudo().search(
            [('employee_id', '=', self.employee_id.id)], order='date_start desc, id desc', limit=1)
        if contract:
            self.sudo().write({'contract_id': contract.id})
        return contract
