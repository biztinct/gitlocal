"""Exercise the real helper without requiring a local Odoo installation."""
import ast
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

source = Path(__file__).resolve().parents[1] / 'pb_people/models/pb_people.py'
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == '_join_date')
namespace = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), namespace)
join_date = namespace['_join_date']


class JoiningDateTests(unittest.TestCase):
    def test_imported_profile_without_contract(self):
        employee = SimpleNamespace(date_of_joining=date(2026, 10, 12), first_contract_date=False,
                                   contract_ids=[], create_date=datetime(2026, 11, 24))
        self.assertEqual(join_date(employee), date(2026, 10, 12))

    def test_joining_precedes_renewal_contract(self):
        employee = SimpleNamespace(date_of_joining=date(2024, 1, 1), first_contract_date=date(2026, 1, 1))
        self.assertEqual(join_date(employee), date(2024, 1, 1))

    def test_without_optional_joining_field(self):
        employee = SimpleNamespace(first_contract_date=date(2025, 2, 3))
        self.assertEqual(join_date(employee), date(2025, 2, 3))

    def test_oldest_available_contract(self):
        employee = SimpleNamespace(contract_ids=[SimpleNamespace(date_start=date(2025, 1, 1)),
                                                SimpleNamespace(date_start=date(2024, 1, 1))])
        self.assertEqual(join_date(employee), date(2024, 1, 1))

    def test_final_creation_fallback_is_preserved(self):
        employee = SimpleNamespace(contract_ids=[], create_date=datetime(2026, 11, 24))
        self.assertEqual(join_date(employee), date(2026, 11, 24))


if __name__ == '__main__':
    unittest.main()
