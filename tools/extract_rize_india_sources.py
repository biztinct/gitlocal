"""Read the two India client sources into a private JSON analysis file.

Requires xlrd and openpyxl for extraction only. Does not author a spreadsheet,
modify a source file, or extract employee data from the unrelated Singapore tab.
"""
import argparse,collections,datetime,hashlib,json,pathlib,struct
import xlrd,openpyxl
from xlrd.formula import decompile_formula,FMLA_TYPE_CELL,FMLA_TYPE_SHARED

# xlrd's decompiler drops equal-precedence RHS parentheses for subtraction.
# Fully parenthesize decompiled operations so source arithmetic is preserved.
import inspect
ns=dict(vars(xlrd.formula))
src=inspect.getsource(decompile_formula).replace("aop.rank < rank","aop.rank <= rank").replace("bop.rank < rank","bop.rank <= rank")
exec(src,ns)
decompile_formula=ns['decompile_formula']

parser=argparse.ArgumentParser()
parser.add_argument('--private-dir',type=pathlib.Path,required=True)
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]/'RIZE/INDIA'
work=args.private_dir
work.mkdir(mode=0o700,parents=True,exist_ok=True)
p=root/'Final-Rize_Payroll_August 2026.xls'
wb=xlrd.open_workbook(p,formatting_info=True,on_demand=True)
out={'payroll':{},'master':{},'sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()}}
for sh in wb.sheets():
 rows=[]
 for row in range(sh.nrows):
  cells=[]
  for col in range(sh.ncols):
   c=sh.cell(row,col)
   if c.ctype in (0,6): value=None
   elif c.ctype==3: value=xlrd.xldate_as_datetime(c.value,wb.datemode).isoformat()
   elif c.ctype==5: value=xlrd.error_text_from_code.get(c.value,str(c.value))
   else: value=c.value
   cells.append(value)
  rows.append(cells)
 formulas={};raw_formulas={};shared=[]
 pos=wb._sh_abs_posn[wb.sheet_names().index(sh.name)]
 while pos+4<len(wb.mem):
  opcode,size=struct.unpack_from('<HH',wb.mem,pos); payload=wb.mem[pos+4:pos+4+size];pos+=4+size
  if opcode==0x000A: break
  if opcode==0x0006:
   row,col=struct.unpack_from('<HH',payload,0)
   length=struct.unpack_from('<H',payload,20)[0]
   raw_formulas[(row,col)]=payload[22:22+length]
   try: formula=decompile_formula(wb,payload[22:22+length],length,FMLA_TYPE_CELL,browx=row,bcolx=col)
   except Exception as exc: formula='UNRESOLVED: '+str(exc)
   formulas[xlrd.formula.cellname(row,col)]=formula
  elif opcode==0x04BC:
   r1,r2,c1,c2,count,length=struct.unpack_from('<HHBBxBH',payload)
   shared.append((r1,r2,c1,c2,payload[10:10+length]))
 for (row,col),tokens in raw_formulas.items():
  if tokens[0]!=1:continue
  for r1,r2,c1,c2,st in shared:
   if r1<=row<=r2 and c1<=col<=c2:
    formulas[xlrd.formula.cellname(row,col)]=decompile_formula(wb,st,len(st),FMLA_TYPE_SHARED,browx=row,bcolx=col)
    break
 out['payroll'][sh.name]={'rows':rows,'formulas':formulas,'merged_cells':sh.merged_cells}
 print('PAYROLL',sh.name,sh.nrows,sh.ncols,'formulas',len(formulas))
p=root/'India Employee Details -rize.farm.xlsx'
out['sources'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
wf=openpyxl.load_workbook(p,data_only=False);wv=openpyxl.load_workbook(p,data_only=True)
for sh in [wf['India']]:
 rows=list(wv[sh.title].values)
 formulas={c.coordinate:c.value for row in sh for c in row if c.data_type=='f'}
 out['master'][sh.title]={'rows':rows,'formulas':formulas}
 print('MASTER',sh.title,sh.max_row,sh.max_column,'formulas',len(formulas))
(work/'source-data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
