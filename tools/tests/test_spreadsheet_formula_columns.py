"""Isolated XLSX cell-type checks; fixtures contain no employee data."""
import importlib.util
import io
from pathlib import Path
import unittest
import openpyxl

path = Path(__file__).resolve().parents[2] / 'pb_formula_studio/models/spreadsheet_columns.py'
spec = importlib.util.spec_from_file_location('spreadsheet_columns', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FormulaColumnTypes(unittest.TestCase):
    def test_sections_blanks_mixed_values_and_later_formulas(self):
        book = openpyxl.Workbook()
        ws = book.active
        ws.title = 'People'
        ws.append(['HR section'])
        ws.append(['Code', 'Age', 'Salary', 'Entered text'])
        ws.append(['TEST1', None, 100, '=literal text'])
        ws['D3'].data_type = 's'
        ws.append(['TEST2', '=10+20', '=50*2', None])
        ws.append(['TEST3', '=10+30', 200, None])
        out = io.BytesIO()
        book.save(out)
        cols = tuple((f'People|{header}', 'People', header, letter, True)
                     for letter, header in [('A','Code'),('B','Age'),('C','Salary'),('D','Entered text')])
        types = module.classify_xlsx_columns(out.getvalue(), cols)
        self.assertEqual(types['People|Age']['kind'], 'formula')
        self.assertEqual(types['People|Age']['formula_cells'], 2)
        self.assertEqual(types['Age'], types['People|B'])
        self.assertEqual(types['People|Salary']['kind'], 'mixed')
        self.assertEqual(types['People|Entered text']['kind'], 'input')

    def test_sheet_qualified_aliases_do_not_confuse_equal_headings(self):
        book = openpyxl.Workbook()
        book.active.title = 'First'
        book.active.append(['ID', 'Age'])
        book.active.append(['TEST1', '=20+1'])
        second = book.create_sheet('Second')
        second.append(['ID', 'Age'])
        second.append(['TEST2', 30])
        out = io.BytesIO()
        book.save(out)
        cols = tuple((f'{sheet}|{header}', sheet, header, letter, True)
                     for sheet in ['First','Second'] for header,letter in [('ID','A'),('Age','B')])
        types = module.classify_xlsx_columns(out.getvalue(), cols)
        self.assertEqual(types['First|Age']['kind'], 'formula')
        self.assertEqual(types['Second|Age']['kind'], 'input')
        self.assertEqual(types['First|B']['kind'], 'formula')
        self.assertEqual(types['Second|B']['kind'], 'input')
        self.assertEqual(types['First|ID']['kind'], 'input')


if __name__ == '__main__':
    unittest.main()
