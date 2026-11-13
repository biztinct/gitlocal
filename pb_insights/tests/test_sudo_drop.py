# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA Cycle 7 — the board reads with the caller's rights, and says where it does not.

The owner's ruling was "Insights' sudo can now be dropped since real access
rules exist" (W105 → W111's mirrors). Dropping it mechanically would have been
a regression rather than a cleanup: the gate group set is a SUPERSET of the
payslip ACL union (C18.75), so this file pins BOTH halves of the actual change.

* **Parity** (test_01): every MONEY section of the board — hero, trend,
  department leaderboard, statutory split — is byte-identical for each gate
  persona to what the same board returns under `sudo()`. If a rule or an ACL
  ever narrows one of those personas, this fails with the number that moved.
* **The residue is enumerated** (test_02): `.sudo()` may appear only inside the
  functions listed here. A structural (AST) gate rather than a text search,
  because the paragraphs that EXPLAIN each surviving sudo necessarily contain
  the word (W101/W114 — prose must not be able to satisfy or break a gate).
"""
import ast
import os

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every function allowed to hold a `.sudo()`, and the reason. Adding one means
# adding a row here — which is the conversation this table exists to force.
SUDO_SITES = {
    'get_insights':       "the workforce pulse row (hr_attendance ladder ACLs)",
    '_hero':              "headcount — hr.employee grants no ACL to the gate groups",
    '_departments':       "department NAME labels; the money beside them is SQL-scoped",
    '_statutory_legacy':  "the only ORM money read left; analytics_user would be "
                          "narrowed to their own lines by the ESS rule (W111)",
    'get_people_ledger':  "employee/attendance ledgers — no money, no gate-group ACL",
    'get_people_detail':  "reads the drawer AFTER emp.check_access('read')",
}


@tagged('post_install', '-at_install')
class TestInsightsSudoDrop(TransactionCase):
    """The structural half. The PARITY half lives in `test_insights.py`
    (`test_11_the_sudo_drop_moved_no_money`), where the fixture world with real
    payslips already stands.
    """

    # ------------------------------------------------------------------ 2
    def test_02_every_surviving_sudo_is_on_the_list(self):
        path = os.path.join(HERE, 'models', 'pb_insights.py')
        with open(path, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())

        found = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(node):
                # a CALL of an attribute named `sudo` — a docstring saying the
                # word cannot match, and neither can a comment
                if (isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == 'sudo'):
                    found.setdefault(node.name, 0)
                    found[node.name] += 1

        unexpected = sorted(set(found) - set(SUDO_SITES))
        self.assertFalse(
            unexpected,
            "pb_insights gained a sudo() in %s. Every sudo on this facade has "
            "to be justified at its site and listed in SUDO_SITES — see the "
            "module docstring." % ', '.join(unexpected))

        # …and the ones we kept must still be there: a sudo that quietly
        # disappears is a section that quietly went blank (W105's shape).
        missing = sorted(set(SUDO_SITES) - set(found))
        self.assertFalse(
            missing,
            "SUDO_SITES lists %s but the source no longer sudoes there. If the "
            "ACLs now cover it, delete the row and its comment." % missing)

    def test_03_the_board_no_longer_collects_under_one_sudo(self):
        """The specific regression: `su = self.sudo()` feeding every section.

        Syntactic, not textual — the docstring explains the old shape in
        prose and must not be able to fail this (W114).
        """
        path = os.path.join(HERE, 'models', 'pb_insights.py')
        with open(path, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        board = next(n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == 'get_insights')
        sudoed_calls = []
        for sub in ast.walk(board):
            # `su._hero(...)` etc. — a section collected through the sudo alias
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id == 'su'):
                sudoed_calls.append(sub.func.attr)
        self.assertEqual(
            sorted(sudoed_calls), ['_pulse'],
            "only the workforce pulse may still be collected through the sudo "
            "alias; found %s" % sorted(sudoed_calls))
