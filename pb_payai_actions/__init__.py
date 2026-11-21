# -*- coding: utf-8 -*-
from . import payai
from . import models


def post_init_hook(env):
    """Tenants start with PayAI's hands OFF; the master database starts on.

    Owner decision 2026-10-12: Green + Amber + Red are allowed on `payobook`;
    every other database (tenants, the template, clones) starts with every
    switch off until somebody asks for it. The field defaults say the same
    thing for companies created later; this makes it explicit for the ones
    that already exist when the module is installed.
    """
    on = env.cr.dbname == 'payobook'
    env['res.company'].sudo().with_context(active_test=False).search([]).write({
        'payai_tier_look': on,
        'payai_tier_prepare': on,
        'payai_tier_decide': on,
        'payai_voice_go_ahead': False,
    })
