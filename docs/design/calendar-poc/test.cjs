// Pure prototype logic checks, independent of the browser. Chrome covers UI flows.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
const context = vm.createContext({Intl, Date, Set, console, document: {
  getElementById(id) { if (!elements.has(id)) elements.set(id, {innerHTML:''}); return elements.get(id); },
  addEventListener() {},
}});
vm.runInContext(fs.readFileSync(__dirname + '/app.js', 'utf8'), context);
const run = code => vm.runInContext(code, context);
let passed = 0;
function test(name, code, expected) {assert.equal(run(code), expected, name); passed++; console.log('PASS', name);}
test('A full six-row month includes its final Sunday', "monthCellCount('2026-11-01')", 42);
test('October calendar has five rows', "monthCellCount('2026-10-01')", 35);
test('Week crosses year boundary correctly', "weekStart('2027-01-01')", '2026-12-28');
test('Sydney and Vietnam show the same instant four hours apart', "localParts('2026-10-28T00:00:00Z','Asia/Ho_Chi_Minh').time", '07:00');
test('Sydney winter uses UTC+10', "localToISO('2026-07-15','09:00')", '2026-07-14T23:00:00.000Z');
test('Sydney summer uses UTC+11', "localToISO('2026-10-28','09:00')", '2026-10-27T22:00:00.000Z');
test('Nonexistent daylight-saving time is rejected', "localToISO('2026-10-04','02:30')", null);
test('Employee cannot see candidate interviews', "state.persona='employee'; accessible().some(e=>e.type==='interview')", false);
test('Interviewer only sees assigned interviews', "state.persona='interviewer'; accessible().some(e=>e.type==='interview'&&!e.panel)", false);
test('Interviewer cannot reschedule a recruiter-owned event', "canEdit(events.find(e=>e.id===6))", false);
test('Busy-only event cannot be edited even by admin', "state.persona='admin'; canEdit(events.find(e=>e.id===7))", false);
test('Read-only connection disables edits', "state.persona='recruiter';state.googleEdit=false;canEdit(events.find(e=>e.id===6))", false);
test('Writable connection allows authorised organiser', "state.googleEdit=true;canEdit(events.find(e=>e.id===6))", true);
test('Default panel has one valid buffered slot', "slots().filter(s=>!s.reason).length", 1);
test('Hiding meetings does not bypass conflict checks', "state.sources.delete('meeting');slots().filter(s=>!s.reason).length", 1);
test('Longer duration removes the formerly valid slot', "state.duration=60;slots().filter(s=>!s.reason).length", 0);
test('At-capacity extra interviewer blocks automatic booking', "state.duration=45;state.panelExtra=true;slots().every(s=>!!s.reason)", true);
test('Expired Microsoft access is unknown, not free', "state.panelExtra=false;state.expired.microsoft=true;slots().every(s=>s.reason.includes('Microsoft'))", true);
test('Disconnected external metadata disappears but Hiring record remains', "state.google=false;!accessible().some(e=>e.id===5)&&accessible().some(e=>e.id===6)", true);
test('Unselected team calendar is not rendered', "state.google=true;state.connectedCalendars.google=['primary'];!accessible().some(e=>e.id===2)", true);
test('User input is HTML-escaped', "esc('<script>\"&')", '&lt;script&gt;&quot;&amp;');
console.log(`${passed} prototype logic checks passed.`);
