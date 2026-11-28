"""Two portal pages must never be able to steal each other's helpers.

THE BUG THIS EXISTS FOR. Every ``CustomerPortal`` subclass on the server is
merged into a SINGLE class at routing time — ``odoo/http.py`` builds
``type(name, tuple(reversed(leaf_controllers)), {})`` over every leaf
subclass. A method defined on one module's portal controller is therefore not
private to that module: it lands in one shared namespace, the module
registered last wins, and everything it shadowed is silently gone. No error,
no log line.

On 2026-09-11 that took three staff pages down on all six databases at once.
``pb_onboarding`` and ``pb_rnr`` had each written a helper called ``_card``.
pb_rnr registers later, so its version — which reads ``rec.nominee_id`` off a
nomination — was the one ``/my/journey``, ``/my/buddy`` and ``/my/orgchart``
called with an employee, and every one of them answered
``'hr.employee' object has no attribute 'nominee_id'``. The owner met it as a
raw 500 page with the vendor's own file paths printed down it.

THE RULE THIS ENFORCES. A method our portal controllers define must be one of:

  * already on the stock ``CustomerPortal``/``Controller`` — a deliberate
    cooperative override that calls ``super()`` (``home``,
    ``_prepare_home_portal_values`` …);
  * defined by exactly ONE of our modules — in practice, prefixed with that
    module's short name (``_ob_card``, ``_rnr_card``, ``_pay_ess_employee``);
  * or defined by two modules where one DEPENDS on the other. That pins the
    order: ``pb_me_portal`` depends on ``om_hr_payroll`` and deliberately
    replaces its ``portal_my_payslips`` page, and the module graph guarantees
    pb_me_portal registers last. pb_onboarding and pb_rnr had no such edge
    between them, which is precisely why their clash was a coin toss nobody
    had thrown.

Anything else is two unrelated modules sharing one name, which is the bug.

The test reads the live class tree and the live module graph, not the source,
so it sees exactly what the router will see — including a module added years
from now.
"""
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import Controller
from odoo.tests.common import TransactionCase, tagged

#: Our own code. Anything outside these prefixes is a stock or third-party
#: addon we do not own and must not fail the build over.
OURS = ('odoo.addons.pb_', 'odoo.addons.biz_', 'odoo.addons.om_')


def _leaf_subclasses(cls):
    """Mirror of ``http._generate_routing_rules.get_leaf_classes``.

    Deduplicated while keeping registration order: a class reachable down two
    branches of the tree appears twice otherwise, and ``type()`` refuses a
    duplicate base.
    """
    found = []
    for sub in cls.__subclasses__():
        for leaf in (_leaf_subclasses(sub) or [sub]):
            if leaf not in found:
                found.append(leaf)
    return found


def _inherited_names():
    """Every attribute the stock portal/controller base already defines.

    Overriding one of these is the supported extension point — Odoo's own
    merged MRO makes ``super()`` walk every module's version in turn — so they
    are exempt from the one-module rule.
    """
    names = set()
    for base in (CustomerPortal, Controller, object):
        for klass in base.__mro__:
            if klass.__module__.startswith(OURS):
                continue
            names.update(vars(klass))
    return names


@tagged('post_install', '-at_install')
class TestPortalHelperNames(TransactionCase):

    def _ancestry(self):
        """module -> every module it depends on, transitively.

        Read from ``ir.module.module`` rather than the manifests so it is the
        graph the server actually loaded.
        """
        rows = self.env['ir.module.module'].sudo().search_read(
            [('state', '=', 'installed')], ['name', 'dependencies_id'])
        direct = {r['name']: r['dependencies_id'] for r in rows}
        names = self.env['ir.module.module.dependency'].sudo().browse(
            [d for deps in direct.values() for d in deps])
        by_id = {d.id: d.name for d in names}
        direct = {m: {by_id.get(i) for i in deps} for m, deps in direct.items()}

        resolved = {}

        def walk(module, seen):
            if module in resolved:
                return resolved[module]
            if module in seen:
                return set()                      # cycles cannot happen, but
            seen = seen | {module}
            out = set()
            for dep in direct.get(module) or ():
                if dep:
                    out.add(dep)
                    out |= walk(dep, seen)
            resolved[module] = out
            return out

        for module in list(direct):
            walk(module, set())
        return resolved

    def test_no_two_portal_controllers_share_a_helper_name(self):
        inherited = _inherited_names()
        ancestry = self._ancestry()
        owners = {}
        clashes = {}
        for klass in _leaf_subclasses(CustomerPortal):
            module = klass.__module__
            if not module.startswith(OURS):
                continue
            short = module.split('.')[2]          # odoo.addons.<module>.…
            for name, attr in vars(klass).items():
                if name.startswith('__') or not callable(attr):
                    continue
                if name in inherited:
                    continue                      # deliberate core override
                first = owners.setdefault(name, short)
                if first == short:
                    continue
                related = (first in ancestry.get(short, ())
                           or short in ancestry.get(first, ()))
                if related:
                    continue                      # ordered, deliberate replacement
                clashes.setdefault(name, {first}).add(short)

        self.assertFalse(
            clashes,
            "These portal helpers are defined by more than one of our modules. "
            "All CustomerPortal subclasses share ONE namespace, so the module "
            "registered last silently replaces the others and their pages "
            "break at runtime. Prefix each helper with its own module "
            "(_ob_card, _rnr_card, _pay_ess_employee): "
            + '; '.join('%s -> %s' % (n, sorted(m)) for n, m in sorted(clashes.items())))

    def test_the_onboarding_cards_are_the_onboarding_ones(self):
        """The specific regression: the three onboarding pages draw PEOPLE.

        Asked of the merged class the router actually builds, so it fails if
        any future module shadows ``_ob_card`` however it does it.
        """
        merged = type('Merged', tuple(reversed(_leaf_subclasses(CustomerPortal))), {})
        card = getattr(merged, '_ob_card', None)
        self.assertIsNotNone(card, "pb_onboarding's card helper has gone missing")
        self.assertTrue(
            card.__module__.endswith('pb_onboarding.controllers.portal'),
            "%s owns _ob_card — pb_onboarding's portal pages will 500"
            % card.__module__)
