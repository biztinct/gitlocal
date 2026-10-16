/** @odoo-module **/
import { describe, expect, test } from '@odoo/hoot';
import { columnLetter, reviewValue } from '@pb_payroll_templates/monthly_review';

describe.current.tags('headless');
test('spreadsheet coordinates continue after Z',()=>{
    expect([0,25,26,51,52,701,702].map(columnLetter)).toEqual(['A','Z','AA','AZ','BA','ZZ','AAA']);
});
test('editing keeps explicit zero and rejects invalid payroll amounts',()=>{
    expect(reviewValue('0','money')).toEqual({value:0,error:''});
    expect(reviewValue('-23.5','money')).toEqual({value:-23.5,error:''});
    expect(reviewValue('','quantity')).toEqual({value:null,error:''});
    for(const value of ['=1+1','@SUM(A1)','NaN','Infinity','not a number'])expect(!!reviewValue(value,'money').error).toBe(true);
    expect(!!reviewValue('1.5','integer').error).toBe(true);
});
test('record context preserves text and explicit false',()=>{
    expect(reviewValue('Payroll specialist','text')).toEqual({value:'Payroll specialist',error:''});
    expect(reviewValue('No','boolean')).toEqual({value:false,error:''});
    expect(reviewValue('Yes','boolean')).toEqual({value:true,error:''});
    expect(reviewValue('2026-10-01','date')).toEqual({value:'2026-10-01',error:''});
    expect(!!reviewValue('31/99/2026','date').error).toBe(true);
});
