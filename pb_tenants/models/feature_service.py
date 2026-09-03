# -*- coding: utf-8 -*-
"""FLEET P4 — the cockpit's half of the feature switches.

Everything a person can press on the Features screen arrives here. Four rules
run through all of it and they are the phase's rails:

  R1  NOTHING ON A TIMER EVER WRITES TO A CUSTOMER. Every push below happens
      because somebody flipped a switch, created a customer, saved the
      catalogue or pressed "Push again". There is no cron in this file, and
      there is deliberately no "reconcile the fleet nightly" job: a customer's
      screen changing overnight with nobody's name against it is exactly the
      thing the platform must never do.
  R2  The never-list stands. Every write goes through `push_tenancy`, which
      re-asks it against the literal database name.
  R5  Cross-database writes go through the ORM, never SQL — again, because they
      go through `push_tenancy`.
  R6  The decision is pure and lives in `feature_rules.py`; this file only
      reads records, calls it, and writes the answer down.

AND THE SENTENCE THE SCREEN HAS TO CARRY: a switch hides doors, it is not a
security control. Turning something off takes it off the rail, out of the hubs
and out of the search. What a person may read on their own database is still
their roles' business.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .feature_rules import (
    MODES, T_FEATURES, custom_count, effective_features, features_sentence,
)

_logger = logging.getLogger(__name__)

#: What a Catalogue form may change. Everything else about a `pb.feature` —
#: above all its `key` — is fixed once customers have been pushed, because the
#: key is what their settings are written in terms of.
CATALOGUE_WRITABLE = ('name', 'blurb', 'area', 'default_on', 'mode',
                      'lock_text', 'sequence', 'active')


class PbTenantsFeatures(models.AbstractModel):
    """Added to the same facade every other cockpit call lives on."""
    _inherit = 'pb.tenants'

    # ==================================================== reading the matrix
    @api.model
    def features_data(self):
        """Everything the Features screen draws, in one call.

        One read of our own two tables and one read of our own rail. It touches
        NO customer database: what each customer is shown is worked out here
        from the catalogue and their own rows, which is the same calculation
        that produced what was pushed to them.
        """
        self._require_admin()
        Feature = self.env['pb.feature'].sudo()
        catalogue = Feature.catalogue()
        tenants = self.env['pb.tenant'].sudo().search(
            [('state', '!=', 'decommissioned')])
        rows = [self._feature_row(t, catalogue) for t in tenants]
        return {
            'catalogue': catalogue,
            'tenants': rows,
            # The golden template is NOT a customer and gets no switches of its
            # own: it is the shape a new customer is cut from, so what it shows
            # is the catalogue's defaults and nothing else. It is on the screen
            # as a read-only row because leaving it off invites the question
            # "and what does a new customer get?" with no answer anywhere.
            'defaults': {
                'label': _("Defaults for new customers"),
                'on': {r['key']: bool(r['default_on']) for r in catalogue},
            },
            # The platform's own database. Never switched, never pushed a
            # different answer: the owner has to be able to see the whole
            # product to sell it.
            'master': {
                'label': _("This platform (master)"),
                'note': _("Every part of the product stays switched on here."),
            },
            'rail': self._rail_preview(),
            'custom_tenants': sum(1 for r in rows if r['custom']),
            'modes': list(MODES),
        }

    def _feature_row(self, tenant, catalogue):
        """One customer, as the matrix reads them."""
        overrides = self.env['pb.tenant.feature'].sudo().overrides_for(tenant)
        eff = effective_features(catalogue, overrides)
        pushed = tenant.features_pushed_at
        return {
            'id': tenant.id, 'name': tenant.name, 'slug': tenant.slug,
            'state': tenant.state,
            'on': {k: v['on'] for k, v in eff.items()},
            'source': {k: (overrides[k]['source'] if k in overrides else 'default')
                       for k in eff},
            'reason': {k: overrides[k]['reason'] for k in overrides},
            'who': {k: overrides[k]['changed_by'] for k in overrides},
            'when': {k: overrides[k]['changed_at'] for k in overrides},
            'custom': custom_count(catalogue, overrides),
            'sentence': features_sentence(eff),
            'pushed_at': (pushed.isoformat(sep=' ', timespec='minutes')
                          if pushed else ''),
            'never_pushed': not pushed,
            'linked': self._tenancy_installed(tenant.slug) if tenant.slug else False,
        }

    def _rail_preview(self):
        """The left menu, as this platform's own records describe it.

        THE PREVIEW IS READ OFF REAL RECORDS, not drawn from a list in the
        browser. Every customer runs the same modules as the master (that is
        what "in step" means), so the master's own rail rows ARE the customer's
        rail rows — same names, same icons, same feature against each entry.
        A hand-written mock would be a picture that goes out of date the first
        time somebody adds a mission, and the owner would be approving a screen
        nobody has.

        Top-level, active entries only, in the order they are drawn.
        """
        Item = self.env['pb.sidebar.item'].sudo()
        if 'feature_key' not in Item._fields:
            # The master has the cockpit but not yet the Platform Link that
            # adds the column. Say nothing rather than half of it.
            return []
        items = Item.search([('active', '=', True), ('parent_id', '=', False)],
                            order='section_id, sequence, id')
        out = []
        for item in items:
            if not item.section_id.active:
                continue
            out.append({
                'id': item.id,
                'name': item.name or '',
                'icon': item.icon or 'circle',
                'feature': item.feature_key or '',
                'section': item.section_id.technical_key or '',
            })
        return out

    @api.model
    def features_for(self, tenant_id):
        """One customer's row, for the screen that only wants one."""
        self._require_admin()
        tenant = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(_("There is no such customer."))
        catalogue = self.env['pb.feature'].sudo().catalogue()
        return self._feature_row(tenant, catalogue)

    # ==================================================== what gets pushed
    def _features_payload(self, tenant):
        """The JSON one customer's database is given. PURE decision, R6."""
        catalogue = self.env['pb.feature'].sudo().catalogue()
        overrides = self.env['pb.tenant.feature'].sudo().overrides_for(tenant)
        return json.dumps(effective_features(catalogue, overrides))

    def _push_features(self, tenant, why=''):
        """Write one customer's switches onto their database.

        Never raises for a customer who cannot be reached. A platform owner
        turning one feature on for eleven customers must not have the whole
        thing fail because the twelfth has not been brought in step — the row
        says so on the screen instead, with the button that fixes it.
        """
        try:
            res = self.push_tenancy(tenant.id, {T_FEATURES: self._features_payload(tenant)})
        except UserError as e:
            return {'ok': False, 'label': tenant.name, 'reason': str(e)}
        except Exception:                               # noqa: BLE001
            _logger.warning("pb_tenants: could not push the switches to %s",
                            tenant.slug, exc_info=True)
            return {'ok': False, 'label': tenant.name,
                    'reason': _("Their database could not be reached just now.")}
        if res.get('ok'):
            tenant.sudo().write({'features_pushed_at': fields.Datetime.now()})
            self._log_line(tenant, 'features',
                           why or _("Feature switches updated."))
        return res

    @api.model
    def features_push(self, tenant_id):
        """"Push again" — the way out of a row that says "never pushed"."""
        self._require_admin()
        tenant = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(_("There is no such customer."))
        res = self._push_features(tenant, _("Switches sent again by hand."))
        return {'push': res, 'data': self.features_data()}

    # ==================================================== flipping switches
    def _feature_by_key(self, key):
        feature = self.env['pb.feature'].sudo().search(
            [('key', '=', (key or '').strip())], limit=1)
        if not feature:
            raise UserError(_('There is no feature called "%s".') % key)
        return feature

    def _write_switch(self, tenant, feature, on, reason):
        """One customer's answer to one feature, written down. No push here."""
        Row = self.env['pb.tenant.feature'].sudo()
        row = Row.search([('tenant_id', '=', tenant.id),
                          ('feature_id', '=', feature.id)], limit=1)
        vals = {'on': bool(on), 'source': 'manual', 'reason': (reason or '')[:200],
                'changed_by': self.env.user.id,
                'changed_at': fields.Datetime.now()}
        if row:
            row.write(vals)
        else:
            row = Row.create(dict(vals, tenant_id=tenant.id,
                                  feature_id=feature.id))
        return row

    @api.model
    def features_set(self, tenant_id, key, on, reason=''):
        """Flip ONE switch for ONE customer, and tell them straight away."""
        self._require_admin()
        tenant = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(_("There is no such customer."))
        if tenant.state == 'decommissioned':
            raise UserError(_(
                "%s has been decommissioned — there is no database left to "
                "switch anything on for.") % tenant.name)
        feature = self._feature_by_key(key)
        self._write_switch(tenant, feature, on, reason)
        res = self._push_features(tenant, _(
            "%(name)s switched %(word)s.",
            name=feature.name,
            word=_("on") if on else _("off")))
        return {'push': res, 'data': self.features_data()}

    @api.model
    def features_reset(self, tenant_id, key):
        """Put one switch back to whatever the catalogue says."""
        self._require_admin()
        tenant = self.env['pb.tenant'].sudo().browse(int(tenant_id)).exists()
        if not tenant:
            raise UserError(_("There is no such customer."))
        feature = self._feature_by_key(key)
        self.env['pb.tenant.feature'].sudo().search(
            [('tenant_id', '=', tenant.id),
             ('feature_id', '=', feature.id)]).unlink()
        res = self._push_features(tenant, _(
            "%s put back to the standard setting.") % feature.name)
        return {'push': res, 'data': self.features_data()}

    @api.model
    def features_bulk(self, key, on, tenant_ids, reason=''):
        """One feature, many customers, one confirmation.

        Every customer is written down first and pushed afterwards, one at a
        time, and a customer who cannot be reached is REPORTED rather than
        rolled back: the decision has been made and recorded, and the delivery
        catches up when their database can be reached (the row keeps its "never
        pushed" mark and its own button until it does).
        """
        self._require_admin()
        feature = self._feature_by_key(key)
        ids = [int(i) for i in (tenant_ids or [])]
        tenants = self.env['pb.tenant'].sudo().browse(ids).exists().filtered(
            lambda t: t.state != 'decommissioned')
        if not tenants:
            raise UserError(_("Pick at least one customer first."))
        sent, failed = [], []
        for tenant in tenants:
            self._write_switch(tenant, feature, on, reason)
            res = self._push_features(tenant, _(
                "%(name)s switched %(word)s for everybody in one go.",
                name=feature.name, word=_("on") if on else _("off")))
            (sent if res.get('ok') else failed).append(
                res.get('label') or tenant.name)
        return {
            'sent': sent, 'failed': failed,
            'message': self._bulk_sentence(feature, on, sent, failed),
            'data': self.features_data(),
        }

    @staticmethod
    def _bulk_sentence(feature, on, sent, failed):
        word = _("on") if on else _("off")
        if not failed:
            return _("%(name)s is now %(word)s for %(n)s customer(s).",
                     name=feature.name, word=word, n=len(sent))
        return _("%(name)s is now %(word)s for %(n)s customer(s). "
                 "%(m)s could not be reached: %(who)s.",
                 name=feature.name, word=word, n=len(sent), m=len(failed),
                 who=', '.join(failed))

    # ==================================================== the catalogue tab
    @api.model
    def feature_save(self, feature_id, vals):
        """Edit one line of the catalogue, then tell everybody it affects.

        A catalogue change moves what customers see — a default flipped, a mode
        changed from hidden to locked, a sentence corrected — so it is followed
        by a push to every live customer. That is still rail R1: somebody
        pressed Save.
        """
        self._require_admin()
        feature = self.env['pb.feature'].sudo().browse(int(feature_id)).exists()
        if not feature:
            raise UserError(_("There is no such feature."))
        clean = {k: v for k, v in (vals or {}).items() if k in CATALOGUE_WRITABLE}
        if 'mode' in clean and clean['mode'] not in MODES:
            raise UserError(_("A feature is either hidden or shown locked."))
        if 'name' in clean and not (clean['name'] or '').strip():
            raise UserError(_("A feature needs a name people can read."))
        feature.write(clean)
        for tenant in self.env['pb.tenant'].sudo().search([('state', '=', 'live')]):
            self._push_features(tenant, _("%s was edited in the catalogue.")
                                % feature.name)
        self._push_features_here()
        return self.features_data()

    # ==================================================== the master itself
    #
    # `@api.model` IS LOAD-BEARING AND IT IS NOT ABOUT `self`. The catalogue's
    # data file ends with `<function model="pb.tenants"
    # name="_push_features_here"/>` and no arguments, and this framework reads
    # the FIRST argument of a `<function>` as the ids to call it on
    # (`odoo/tools/convert.py:193`, `record_ids, *args = args`). With no
    # arguments and no `@api.model`, that unpack fails and takes the whole
    # upgrade with it — "not enough values to unpack (expected at least 1,
    # got 0)", pointing at the XML rather than at the method it could not call.
    # A method invoked from a data file with no arguments must carry this.
    @api.model
    def _push_features_here(self):
        """The platform's own database, written straight rather than pushed.

        `push_tenancy` refuses the master by design, and correctly: messages go
        OUT from here. But the master runs the same reader as everybody else,
        and the owner has to see every part of the product to be able to sell
        it — so its own settings row is written here, with EVERY feature on,
        whatever the catalogue's defaults happen to say.

        That "whatever the defaults say" is deliberate and is the rail: a
        default switched off for new customers must never take a door off the
        owner's own screen.
        """
        catalogue = self.env['pb.feature'].sudo().catalogue()
        payload = {r['key']: {'on': True,
                              'mode': r['mode'],
                              'lock_text': r['lock_text']}
                   for r in catalogue}
        self.env['ir.config_parameter'].sudo().set_param(
            T_FEATURES, json.dumps(payload))
        return payload
