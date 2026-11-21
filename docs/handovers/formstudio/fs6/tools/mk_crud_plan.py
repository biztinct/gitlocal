"""Build plan_crud.json: create / edit / save / discard on both forms through the screen."""
import json
import os

S = os.path.dirname(os.path.abspath(__file__))
H = r"""
const sleep = ms => new Promise(r => setTimeout(r, ms));
const q = s => document.querySelector('.o_action_manager .o_form_view ' + s);
async function setField(name, value) {
  const w = q(`.o_field_widget[name="${name}"]`);
  if (!w) return 'nofield ' + name;
  const i = w.querySelector('input, textarea');
  i.focus(); i.value = value;
  i.dispatchEvent(new Event('input', {bubbles: true}));
  i.dispatchEvent(new Event('change', {bubbles: true}));
  i.blur(); await sleep(300); return 'ok';
}
async function pickM2o(name, text) {
  const w = q(`.o_field_widget[name="${name}"]`);
  if (!w) return 'nofield ' + name;
  const i = w.querySelector('input');
  i.focus(); i.value = text; i.dispatchEvent(new Event('input', {bubbles: true}));
  for (let k = 0; k < 20; k++) { await sleep(200); const it = document.querySelector('.o-autocomplete--dropdown-item a, .o-autocomplete--dropdown-item'); if (it) { it.click(); await sleep(400); return 'ok'; } }
  return 'nodrop';
}
async function save() { const b = q('.o_form_button_save') || document.querySelector('.o_form_button_save'); if (!b) return 'nosave'; b.click(); await sleep(1500); return 'ok'; }
async function discard() { const b = document.querySelector('.o_form_button_cancel'); if (!b) return 'nodiscard'; b.click(); await sleep(1000); return 'ok'; }
async function rpcRead(model, id, fields) {
  const r = await fetch('/web/dataset/call_kw', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {model, method: 'read', args: [[id], fields], kwargs: {}}})});
  const j = await r.json(); return j.result ? j.result[0] : j.error;
}
const invalid = () => [...document.querySelectorAll('.o_field_invalid')].map(e => e.getAttribute('name'));
const vu = () => !!document.querySelector('.o_form_renderer.vu-form');
"""

def ev(name, model, rid, cid, body):
    return {"name": name, "user": "admin", "model": model, "id": rid, "cid": cid,
            "js": "(async()=>{" + H + body + "})()"}

evals = [
    ev("emp_edit_save", "hr.employee", 5124, 257, """
      const a = await setField('job_title', 'DEMO FS6 title'); const s = await save();
      const r = await rpcRead('hr.employee', 5124, ['job_title']);
      return {vu: vu(), a, s, server: r.job_title, dirty: !!q('.o_form_dirty'), invalid: invalid()};"""),
    ev("emp_discard", "hr.employee", 5124, 257, """
      const a = await setField('job_title', 'DISCARD ME'); const d = await discard();
      const shown = q('.o_field_widget[name="job_title"] input').value;
      const r = await rpcRead('hr.employee', 5124, ['job_title']);
      return {vu: vu(), a, d, shown, server: r.job_title};"""),
    ev("emp_create", "hr.employee", "new", 257, """
      const a = await setField('name', 'DEMO FS6 Created Person'); const s = await save();
      return {vu: vu(), a, s, path: location.pathname, invalid: invalid(), title: (q('.oe_title h1 input')||{}).value};"""),
    ev("con_edit_save", "hr.contract", 2656, 257, """
      const a = await setField('wage', '23456'); const s = await save();
      const r = await rpcRead('hr.contract', 2656, ['wage']);
      return {vu: vu(), a, s, server: r.wage, invalid: invalid()};"""),
    ev("con_discard", "hr.contract", 2656, 257, """
      const a = await setField('wage', '99999'); const d = await discard();
      const r = await rpcRead('hr.contract', 2656, ['wage']);
      return {vu: vu(), a, d, shown: q('.o_field_widget[name="wage"] input').value, server: r.wage};"""),
    ev("con_create", "hr.contract", "new", 257, """
      const a = await setField('name', 'DEMO FS6 Created contract');
      const b = await pickM2o('employee_id', 'DEMO Vietnam');
      const c = await setField('wage', '11111');
      const s = await save();
      return {vu: vu(), a, b, c, s, path: location.pathname, invalid: invalid()};"""),
]
plan = {"base": "http://fs6.localhost:8616", "db": "fs_6_t",
        "users": [{"key": "admin", "login": "admin", "env": "FS6_PW_ADMIN"}], "evals": evals}
json.dump(plan, open(os.path.join(S, 'plan_crud.json'), 'w'), indent=1)
print('ok', len(evals))
