# -*- coding: utf-8 -*-
"""JOURNEY J1 — one mapping board, one home, and every door still open.

The mapping board had TWO shells: a scrim inside the Formula Studio and a
full-screen cockpit. They mounted the same component and called the same server
adapters, and neither was a superset of the other — so which half of the feature
a user met was decided by which door they walked through. J1 retires the overlay
and moves its payload into the full-screen host.

None of that is visible to a normal test: it is markup, wiring and prop-passing.
What IS assertable, and what would regress silently, is this:

  * the overlay is GONE — not disabled, not hidden behind a flag. A second shell
    that still exists in the source is a second shell somebody re-enables;
  * the payload actually ARRIVED. Each ported capability is named here by the
    RPC or prop that carries it, so "we merged the shells" cannot be true while
    half the toolkit was left behind;
  * the Formula Studio's button is a DOOR and it arrives pre-scoped. A deep link
    that lands on the studio's own defaults is this codebase's worst bug class
    (W76.3/W117) — it looks right and it is mapping the wrong scheme;
  * the six doors still name the surviving tag, and none of them — nor anything
    else a user reads on this surface — says "Mapping Studio", "Mapping canvas"
    or "Odoo".

These are source assertions, in the shape `pb_integrations/tests/test_one_door.py`
established: the thing being protected is a wiring decision, and a wiring
decision has no runtime handle to grab.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _src(module, *parts):
    return _read(os.path.join(get_module_path(module), *parts))


# A user-visible string is one inside a quoted attribute or between tags — not a
# comment. These strip the two comment syntaxes so the naming gate cannot be
# fooled (or tripped) by the history we deliberately keep in the prose.
def _strip_xml_comments(src):
    return re.sub(r'<!--.*?-->', '', src, flags=re.S)


def _strip_js_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^\s*//.*$', '', src, flags=re.M)


@tagged('post_install', '-at_install')
class TestOneMappingHome(TransactionCase):

    # ------------------------------------------------------------ the overlay
    def test_the_overlay_shell_is_gone_from_the_formula_studio(self):
        tpl = _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/studio.xml'))
        js = _src('pb_formula_studio', 'static/src/js/formula_studio.js')
        for marker in ('pbfs-map-scrim', 'pm-tabs', 'pm-lanes', 'pm-empadd',
                       'pm-empfield', 'pm-tmpl', 'rcn-row'):
            self.assertNotIn(
                marker, tpl,
                "%s is overlay chrome — the board has one shell now" % marker)
        # …and its state with it. `state.mapOpen` was the whole overlay's switch.
        for key in ('mapOpen', 'mapMode', 'mapEmpPayroll', 'rcnOpen', 'tmplMode'):
            self.assertNotIn(
                'state.%s' % key, js,
                "%s is overlay state; the full-screen host owns it now" % key)
        # the Formula Studio no longer mounts the board at all
        self.assertNotIn('MappingCanvas', _strip_js_comments(js),
                         "only the full-screen host mounts the mapping board")

    def test_the_overlay_styles_went_with_their_markup(self):
        """A stylesheet that outlives its DOM is how the next reader concludes a
        surface still exists (and how it gets rebuilt)."""
        scss = _src('pb_formula_studio', 'static/src/scss/mapping.scss')
        self.assertNotIn('.pbfs-map ', scss)
        self.assertNotIn('.pbfs-map-scrim', scss)
        # …but THE BOARD stays. This file is the canvas both hosts always shared.
        self.assertIn('.mapping-canvas', scss)

    # ------------------------------------------------------------ the payload
    def test_every_overlay_only_capability_arrived_in_the_host(self):
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        tpl = _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml')
        # (a) lane chips + filter, (g) the payroll reveal
        self.assertIn('empChips', js)
        self.assertIn('toggleEmpPayroll', js)
        self.assertIn('groupFilter="empLaneFilter"', tpl,
                      "the chips filter the board, or they are only badges")
        # (b) the autocomplete and (c) the two browse dropdowns
        self.assertIn('ec_search_fields', js)
        self.assertIn('ec_model_fields', js)
        # (d) remove an unwired right card, (e) the ⋮ verbs
        self.assertIn('onRemoveRight', tpl)
        self.assertIn('onLeftAction', tpl)
        self.assertIn('employee_mapping_make_component', js)
        self.assertIn('employee_mapping_detach_component', js)
        # (f) the unresolved footer and its dialog
        self.assertIn('employee_mapping_unresolved', js)
        self.assertIn('employee_mapping_resolve_remaining', js)
        # (h) templates, both directions — the host was apply-only before J1
        self.assertIn('mapping_template_save', js)
        self.assertIn('mapping_template_delete', js)
        self.assertIn('unmatched_targets', tpl,
                      "the per-line apply breakdown came across too — a bare "
                      "count says something went wrong without saying what")

    def test_the_payroll_lane_can_actually_be_revealed(self):
        """`employee_mapping_data`'s third argument is `include_payroll`.

        The host used to call it with two, so the reveal chip had nothing to
        reveal — the server never sent the pay columns. The RPC contract itself
        is unchanged (J1 changes no adapter); what changed is that the caller
        finally passes the argument the adapter always accepted.
        """
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        call = js.split('"employee_mapping_data",', 1)[1].split(');', 1)[0]
        self.assertIn('empPayroll', call)

    def test_the_tabs_read_as_the_sentence_not_as_the_adapter_names(self):
        """J-D2's nomenclature, pinned.

        These labels are the whole of the overlay's retirement that a user can
        see: it called them "Cycle carryover", "API fields", "Import columns" —
        the names of the CODE. They are asserted HERE rather than in the hoot
        suite because they are module-scope `_t()` objects: stringifying one
        before the translations load throws "Cannot translate string", and the
        import needed to reach them breaks five unrelated mount tests (MJ2).
        """
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        modes = js.split('export const MODES = [', 1)[1].split('\n];', 1)[0]
        for label in ('System fields → Scheme',
                      'Spreadsheet columns → Scheme',
                      # J3 S1 / J-D4 — the ⇆ is the label now.
                      'Employee & contract \u21c6',
                      'Scheme assignment',
                      'Mid ↔ End cycle',
                      # J4 — the sixth tab. A plain noun rather than an
                      # "X → Y" sentence because this board has THREE lanes:
                      # the arrow form would have to pick two of them and
                      # would name the wrong pair whichever two it picked.
                      'Transformations',
                      # J5 — the seventh tab, FIRST, and the cold-start
                      # default. A plain noun for the same reason
                      # "Transformations" is one: this board has five lanes and
                      # an "X → Y" label would have to pick two of them.
                      'Journey'):
            self.assertIn('_t("%s")' % label, modes,
                          "the tab labels are J-D2's, exactly")
        # the ids are the RPC prefixes and the deep-link vocabulary — untouched
        # except by ADDITION. J5 prepends `journey`; every id that was here
        # before is still here, still spelled the same, still in the same
        # relative order, which is what keeps every deep link landing where it
        # always did.
        self.assertEqual(re.findall(r'\{ id: "(\w+)"', modes),
                         ['journey', 'api', 'transform', 'import', 'employee',
                          'scheme', 'cycle'])
        # …and nothing a user reads on this surface says "Studio"
        for label in re.findall(r'label: _t\("([^"]+)"\)', modes):
            self.assertNotIn('Studio', label)

    def test_the_employee_toolkit_is_scoped_to_the_employee_board(self):
        """Four boards must not grow a fifth board's furniture.

        A lane filter left behind across a mode switch filters the next column
        list by a lane that board does not have — an empty column for no visible
        reason, which reads as a broken screen rather than as a stale filter.
        """
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        tpl = _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml')
        # the toolbar, the chips and the footer all render behind `isEmp`
        self.assertIn('get isEmp() { return this.state.mode === "employee"; }', js)
        self.assertIn('t-if="isEmp and state.data and state.data.ok"', tpl)
        self.assertIn('t-if="isEmp" class="pbms-foot"', tpl)
        # the filter answers "" off the employee board…
        self.assertIn('get empLaneFilter() { return this.isEmp ? '
                      '(this.state.empLane || "") : ""; }', js)
        # …and every mode switch and scheme change resets the toolkit outright
        self.assertIn('_resetEmpToolkit()', js)
        setmode = js.split('async setMode(id) {', 1)[1].split('\n    }', 1)[0]
        self.assertIn('_resetEmpToolkit', setmode)

    def test_one_implementation_of_each_moved_dialog(self):
        """MOVED, not copied. Two copies of the reconciliation dialog would drift
        the moment either was fixed."""
        studio = _src('pb_formula_studio', 'static/src/xml/studio.xml')
        host = _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml')
        for marker in ('Resolve the remaining columns', 'Leave all as reference'):
            self.assertNotIn(marker, studio)
            self.assertIn(marker, host)

    # --------------------------------------------------------------- the door
    def test_the_formula_studio_button_opens_the_full_screen_board_pre_scoped(self):
        js = _src('pb_formula_studio', 'static/src/js/formula_studio.js')
        door = js.split('openMapping(mode) {', 1)[1].split('\n    }', 1)[0]
        self.assertIn('pb_mapping_studio', door,
                      "the button opens the surviving surface, not a scrim")
        self.assertIn('pb_config', door,
                      "…on the scheme being edited. A board that opens on its "
                      "own defaults makes the user do the work twice, and "
                      "silently maps the wrong scheme if they do not notice")
        self.assertIn('pb_mode', door)
        # …and it comes back, onto the same scheme. A one-way door is not a door.
        self.assertIn('back:', door)
        self.assertIn('config_id', door)

    def test_the_people_signal_still_lands_on_the_people_board(self):
        """COLROLES P4's auto-open: an import that produced people columns opens
        the mapping board on `employee`. It used to raise the overlay; it now
        opens the full-screen surface, and it must still choose that board."""
        js = _src('pb_formula_studio', 'static/src/js/formula_studio.js')
        self.assertIn('pbfs_open_people_mapping', js)
        self.assertIn('this.openMapping("employee")', js)

    def test_the_action_record_kept_its_id_and_tag_and_changed_only_its_name(self):
        act = self.env.ref('pb_formula_studio.action_pb_mapping_studio',
                           raise_if_not_found=False)
        self.assertTrue(act, "four doors and two test suites name this record")
        self.assertEqual(act.tag, 'pb_mapping_studio')
        self.assertEqual(act.name, 'Mapping')

    def test_all_six_doors_still_name_the_surviving_tag(self):
        doors = [
            ('pb_settings', 'static/src/js/settings_hub.js'),
            ('pb_hub', 'static/src/js/hub_palette_entries.js'),
            ('pb_integrations', 'static/src/js/integrations.js'),
            ('pb_import_advanced', 'static/src/js/connector_cockpit.js'),
        ]
        for module, path in doors:
            self.assertIn('pb_mapping_studio', _src(module, path),
                          "%s lost its door onto the mapping board" % module)
        # the connector cockpit carries BOTH of its doors: the whole system, and
        # one feed of it
        cockpit = _src('pb_import_advanced', 'static/src/xml/connector_cockpit.xml')
        self.assertIn('this.openMapping(null)', cockpit)
        self.assertIn('this.openMapping(ep)', cockpit)
        # the board's mappings count is the sixth
        self.assertIn('openMappingStudio',
                      _src('pb_integrations', 'static/src/xml/integrations.xml'))

    # ------------------------------------------------------------- the naming
    def test_nothing_a_user_reads_still_calls_it_a_studio_or_a_canvas(self):
        offenders = []
        surfaces = [
            ('pb_formula_studio', 'static/src/xml/mapping_studio.xml'),
            ('pb_formula_studio', 'views/pb_mapping_studio_action.xml'),
            ('pb_import_advanced', 'static/src/xml/connector_cockpit.xml'),
            ('pb_integrations', 'static/src/xml/integrations.xml'),
        ]
        for module, path in surfaces:
            src = _strip_xml_comments(_src(module, path)).lower()
            for bad in ('mapping studio', 'mapping canvas'):
                if bad in src:
                    offenders.append('%s/%s: %s' % (module, path, bad))
        for module, path in (('pb_settings', 'static/src/js/settings_hub.js'),
                             ('pb_hub', 'static/src/js/hub_palette_entries.js')):
            src = _strip_js_comments(_src(module, path))
            for bad in ('Mapping Studio', 'Mapping canvas'):
                if bad in src:
                    offenders.append('%s/%s: %s' % (module, path, bad))
        self.assertFalse(
            offenders,
            "the surface is called Mapping. Technical ids keep their names; "
            "these are strings a person reads: %s" % offenders)

    def test_no_user_visible_odoo_on_this_surface(self):
        """The white-label absolute, checked where J1 wrote new strings."""
        tpl = _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml'))
        self.assertNotIn('Odoo', tpl)
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        # `_t("…")` strings only — `@odoo/owl` and `@web/…` imports are technical
        for literal in re.findall(r'_t\(\s*"((?:[^"\\]|\\.)*)"', js):
            self.assertNotIn('Odoo', literal,
                             "a user-visible string may never say Odoo")
