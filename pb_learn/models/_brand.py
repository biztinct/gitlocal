# -*- coding: utf-8 -*-
"""WHITELABEL 2026-10-31 — the product's name as THIS tenant knows it.

Learn content is authored once, in the master product's words ("do this in
Payobook"), and served to the browser from Python as plain JSON. None of the
white-label seams (the `_()` patch, the QWeb walker, the JS `_t()` patch) ever
sees it, so a white-label tenant read the master's name in every lesson and
every Coach answer.

The rewrite lives in biz_debrand (`rebrand_payload`) and is imported SOFTLY:
pb_learn does not depend on biz_debrand, and a build without it must keep
working with the text unchanged.
"""
try:
    from odoo.addons.biz_debrand.models.brand import rebrand_payload
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def rebrand_payload(env, value):
        return value

__all__ = ['rebrand_payload']
