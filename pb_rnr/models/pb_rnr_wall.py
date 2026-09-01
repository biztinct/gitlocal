# -*- coding: utf-8 -*-
"""`pb.rnr.wall` — the recognition wall, and the only thing everybody can read.

A SECOND FACADE, ON PURPOSE. `pb.rnr` is the recognition team's board and it
refuses anybody who is not on the team, which is right: it carries stories that
were declined, amounts that were argued about, and a switch that spends money.
The WALL carries none of that. It is the praise that three people have already
agreed is public, and if it is not readable by everybody in the company then it
is not a wall.

So the two are separate objects with separate gates rather than one object with
a mode, because a facade that answers differently depending on who asked is one
edit away from answering the wrong way.

WHAT REACHES IT: `pb.rnr.nomination._public_domain()` and nothing else — the
single definition of "may be seen by everybody", shared with the portal page and
the monthly digest. A declined story cannot leak through a clause somebody
forgot to repeat here, because nothing is repeated here.

WHAT IT NEVER CARRIES: a date of birth, an amount, a decision note, a refusal,
or the name of anybody who was not recognised.
"""

import logging

from odoo import _, api, fields, models

from .rnr_common import excerpt, initials

_logger = logging.getLogger(__name__)

#: How many stories the wall holds. A wall is what you can take in standing up.
WALL_CAP = 30

#: How many celebrations the side strip shows. Four hundred names is a phone
#: book; eight is a strip somebody actually reads.
STRIP_CAP = 8


class PbRnrWall(models.AbstractModel):
    _name = 'pb.rnr.wall'
    _description = 'Recognition wall data'

    @api.model
    def _safe(self, fn, default=None):
        """Each piece of the wall fails alone. A birthday strip that cannot be
        built must not take the stories down with it."""
        try:
            return fn()
        except Exception as e:              # noqa: BLE001
            _logger.debug('recognition wall piece failed: %s', e)
            return default

    @api.model
    def get_wall(self, limit=WALL_CAP):
        """Everything on the wall, in one read.

        Signed in is the whole gate. Every read below is `sudo()` over a domain
        that already says "public", so there is nothing here a colleague may not
        see — and narrowing it per reader would mean two people standing at the
        same wall seeing different praise, which is the opposite of the point.
        """
        cap = max(1, min(int(limit or WALL_CAP), WALL_CAP))
        return {
            'stories': self._safe(lambda: self._stories(cap), []) or [],
            'celebrations': self._safe(lambda: self._strip(), []) or [],
            'winners': self._safe(lambda: self._winners(), {}) or {},
            'values': self._safe(lambda: self._values(), []) or [],
            'me': self._safe(lambda: self._me_summary(), {}) or {},
        }

    # ------------------------------------------------------------ the stories
    @api.model
    def _stories(self, cap):
        Nom = self.env['pb.rnr.nomination'].sudo()
        recs = Nom.search(Nom._public_domain(),
                          order='decided_at desc, id desc', limit=cap)
        out = []
        for rec in recs:
            nominee = Nom._person(rec.nominee_id)
            nominator = Nom._person(rec.nominator_id)
            val = rec.value_id.sudo()
            out.append({
                'id': rec.id,
                'nominee': nominee.name or '',
                'nominee_id': nominee.id,
                'initials': initials(nominee.name or ''),
                'avatar': ('/web/image/hr.employee/%s/image_128' % nominee.id
                           if nominee else ''),
                'department': (nominee.department_id.name
                               if nominee and nominee.department_id else ''),
                'nominator': nominator.name or '',
                'value': val.name or '',
                'motto': val.motto or '',
                'color': val.color or 'primary',
                'icon': val.icon or 'award',
                'story': excerpt(rec.story, 320),
                'winner': bool(rec.is_winner),
                'when': fields.Datetime.to_string(rec.decided_at) or '',
            })
        return out

    # ------------------------------------------------------- the celebrations
    @api.model
    def _strip(self):
        """Names and days. NEVER a year of birth — see the celebrations engine,
        which is the only place this is worked out."""
        rows = self.env['pb.rnr.celebration'].upcoming_celebrations(days=21)
        return rows[:STRIP_CAP]

    # ----------------------------------------------------------- the banner
    @api.model
    def _winners(self):
        cycle = self.env['pb.rnr.cycle'].fresh_winners()
        if not cycle:
            return {}
        Nom = self.env['pb.rnr.nomination'].sudo()
        rows = []
        for rec in cycle.top_ids:
            if rec.outcome not in ('recognised', 'awarded') or not rec.public:
                continue
            emp = Nom._person(rec.nominee_id)
            rows.append({
                'name': emp.name or '',
                'initials': initials(emp.name or ''),
                'avatar': '/web/image/hr.employee/%s/image_128' % emp.id,
                'value': rec.value_id.sudo().name or '',
                'color': rec.value_id.sudo().color or 'primary',
            })
        if not rows:
            return {}
        return {'name': cycle.name or '', 'rows': rows,
                'title': _("The people of %s", cycle.name or '')}

    @api.model
    def _values(self):
        """The values, with how often each has been reached for. The wall's own
        quiet argument that these are not a poster."""
        recs = self.env['pb.company.value'].sudo().search([
            ('active', '=', True),
            '|', ('company_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='sequence, id')
        return [{'id': v.id, 'name': v.name or '', 'motto': v.motto or '',
                 'icon': v.icon or 'award', 'color': v.color or 'primary',
                 'count': v.nomination_count} for v in recs]

    @api.model
    def _me_summary(self):
        """Two numbers about the person looking at it: what they have been
        thanked for, and how often they have thanked somebody else. The second
        is the one that changes behaviour."""
        Emp = self.env['hr.employee'].sudo()
        me = Emp.search([('user_id', '=', self.env.user.id)], limit=1)
        if not me:
            return {}
        Nom = self.env['pb.rnr.nomination'].sudo()
        received = Nom.search_count([
            ('nominee_id', '=', me.id), ('state', '=', 'done'),
            ('outcome', 'in', ('recognised', 'awarded'))])
        given = Nom.search_count([('nominator_id', '=', me.id)])
        return {'employee_id': me.id, 'name': me.name or '',
                'received': received, 'given': given}
