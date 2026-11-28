/* WORKFLOW-2 P5c §2.4: P2b's three checks never looked at in a browser —
   U3 joining checklist for a Hiring joiner ("Chosen in Hiring by …"),
   U5 the employee claim page with and without a strip, U7 the dock sentence.
   LOCAL DISPOSABLE DATABASES ONLY; logins from the P5c fixture file.
     WORKFLOW_UI_URL=http://127.0.0.1:8097 P5C_FIXTURE=… SHOTS=/dir CASE_ID=… WITH_CLAIM=… PLAIN_CLAIM=… node … */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const {chromium} = require(process.env.PLAYWRIGHT_PATH || '/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.WORKFLOW_UI_URL || 'http://127.0.0.1:8097';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base)) throw Error('Local databases only: ' + base);
const fx = JSON.parse(fs.readFileSync(process.env.P5C_FIXTURE, 'utf8'));
const shots = process.env.SHOTS || '/tmp';
const errors = [];
async function session(browser, login) {
  const context = await browser.newContext({viewport: {width: 1400, height: 900}});
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(login + ': ' + e.message));
  const auth = await (await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', method: 'call', params: {db: fx.database, login, password: fx.password}}})).json();
  assert.ok(auth.result?.uid, 'login ' + login);
  return page;
}
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  const out = {};
  try {
    // U3: the joining checklist the Hiring joiner got
    const d = await session(browser, fx.designer);
    await d.goto(base + `/odoo/pb.journey.case/${process.env.CASE_ID}`);
    await d.waitForTimeout(3500);
    await d.screenshot({path: path.join(shots, 'U3_joining_checklist.png'), fullPage: true});
    // The checklist's own drawer in Journeys lists finished steps with their note.
    await d.goto(base + '/odoo/action-pb_lifecycle.action_pb_journeys');
    await d.waitForTimeout(4000);
    await d.getByText('DEMO A3 Candidate', {exact: false}).first().click();
    await d.waitForTimeout(2500);
    const body = await d.locator('body').innerText();
    out.U3 = /Chosen in Hiring by/.test(body) ? body.match(/Chosen in Hiring by[^\n]*/)[0] : '(text not in the Journeys drawer)';
    await d.screenshot({path: path.join(shots, 'U3_buddy_step.png'), fullPage: false});
    // U7: the dock for a manager with workflow tasks and no approvals
    const c = await session(browser, fx.checker);
    await c.goto(base + '/odoo/action-pb_mission.action_pb_workforce');
    await c.waitForTimeout(5000);
    const dock = await c.locator('.pbms-dock').innerText().catch(() => '(no dock)');
    out.U7 = dock.slice(0, 400);
    await c.screenshot({path: path.join(shots, 'U7_dock.png')});
    // U5: the employee claim page, with a workflow (strip) and without
    const h = await session(browser, fx.home);
    for (const [key, id] of [['with', process.env.WITH_CLAIM], ['without', process.env.PLAIN_CLAIM]]) {
      await h.goto(base + `/my/expenses/${id}`);
      await h.waitForTimeout(1500);
      out['U5_' + key] = {strip: await h.locator('.pbwfs-host, .pbwfs').count(), text: (await h.locator('main').innerText()).slice(0, 300)};
      await h.screenshot({path: path.join(shots, `U5_claim_${key}_strip.png`), fullPage: true});
    }
  } finally {
    await browser.close();
  }
  out.errors = errors;
  console.log(JSON.stringify(out, null, 1));
})();
