/* WORKFLOW-2 P6a browser checks — LOCAL DISPOSABLE DATABASES ONLY.
     WORKFLOW_UI_URL=http://127.0.0.1:8097 P6A_FIXTURE=/path/to/fixture.json SHOTS=/dir \
     node tools/workflow_studio/chrome_test_p6a.cjs
   After `ui_fixture_p6a.py` (the fixture file holds the local logins; nothing
   secret is in this file). Shoots: the Approvals inbox Tasks group with one
   task per day of a time-off request ("day 1 of 5"), the workbench with the
   "For each day" frame and its live sample, and the two "sent back" emails as
   queued (business trip in Vietnamese, equipment in Indonesian). Fails on
   console errors, banned words and English left in the translated emails. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const {chromium} = require(process.env.PLAYWRIGHT_PATH || '/Users/adity/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base = process.env.WORKFLOW_UI_URL || 'http://127.0.0.1:8097';
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(base)) throw Error('Local databases only: ' + base);
const fx = JSON.parse(fs.readFileSync(process.env.P6A_FIXTURE, 'utf8'));
const shots = process.env.SHOTS || '/tmp';
const WB = '/pb_lifecycle/static/workflow/index.html?v=wf2-p5c';
const errors = [];
const ok = (k, v) => console.log('CHECK', k, JSON.stringify(v).slice(0, 400));
const banned = (t) => /\bodoo\b|odoobot|\bloop\b|iteration|\bindex\b/i.test(t);

async function session(browser, loginName, width = 1400, height = 900) {
  const context = await browser.newContext({viewport: {width, height}});
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(loginName + ': ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon|\/web\/image\/|Failed to load resource|web_tour/.test(m.text() + (m.location()?.url || ''))) errors.push(loginName + ': ' + m.text());
  });
  if (loginName) {
    const auth = await (await context.request.post(base + '/web/session/authenticate', {data: {jsonrpc: '2.0', method: 'call', params: {db: fx.database, login: loginName, password: fx.password}}})).json();
    assert.ok(auth.result?.uid, 'Login failed for ' + loginName);
  }
  return {context, page};
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    // 1. the checker's Approvals inbox: one task per day of the request
    const c = await session(browser, fx.checker);
    await c.page.goto(base + '/odoo/action-pb_approval_config.action_pb_approval_inbox');
    await c.page.locator('.pbwfi-group').waitFor({timeout: 30000});
    await c.page.waitForTimeout(800);
    const group = await c.page.locator('.pbwfi-group').innerText();
    ok('1 inbox tasks group', group);
    assert.match(group, /Find cover for the day/);
    assert.match(group, /day 1 of 5/);
    assert.ok(!banned(group));
    await c.page.screenshot({path: path.join(shots, 'p6a_1_inbox_days.png')});

    // 2. the workbench: the frame on Journey and the live sample
    const d = await session(browser, fx.designer);
    await d.page.goto(base + WB);
    await d.page.locator('.topbar').waitFor();
    await d.page.evaluate(async (id) => { await openWorkflow(id); S.view = 'journey'; S.selected = 'rep'; render(); }, fx.workflow_id);
    await d.page.locator('.repeat-frame .repeat-chip').waitFor({timeout: 15000});
    const chip = await d.page.locator('.repeat-frame .repeat-chip').first().innerText();
    ok('2 frame chip', chip);
    assert.match(chip, /For each day/);
    await d.page.locator('#rep-sample .rep-sample-row').waitFor({timeout: 15000});
    const sample = await d.page.locator('#rep-sample').innerText();
    ok('2 live sample', sample);
    assert.match(sample, /has 5 days/);
    await d.page.screenshot({path: path.join(shots, 'p6a_2_workbench_each_day.png')});

    // 3. the two "sent back" emails as queued, in the employee's language
    const m = await session(browser, null, 760, 900);
    const expect = {
      'pb.business.trip': {tag: 'vi', must: [/đã bị trả lại/, /Lý do được nêu/, /Mở chuyến công tác của bạn/, /Vui lòng thêm chi phí khách sạn/],
                           not: [/was sent back/, /The reason given/, /Open your trip/]},
      'pb.asset.request': {tag: 'id', must: [/dikembalikan/, /Alasan yang diberikan/, /Buka permintaan Anda/, /laptop cadangan/],
                           not: [/was sent back/, /The reason given/, /Open your requests/]},
    };
    for (const [model, want] of Object.entries(expect)) {
      const mail = fx.mail[model];
      await m.page.setContent(`<html><body style="margin:0;background:#fff"><div style="font:13px sans-serif;color:#6b6f80;padding:12px 24px;border-bottom:1px solid #eee">Subject: ${mail.subject}</div>${mail.body}</body></html>`);
      const text = await m.page.locator('body').innerText();
      ok('3 email ' + want.tag, text.slice(0, 300));
      for (const re of want.must) assert.match(text, re);
      for (const re of want.not) assert.ok(!re.test(text), `${want.tag}: English left ${re}`);
      assert.ok(!banned(text));
      await m.page.screenshot({path: path.join(shots, `p6a_3_${want.tag}_sent_back_email.png`), fullPage: true});
    }
    ok('console errors', errors);
    assert.deepEqual(errors, []);
    console.log('P6A_BROWSER_OK');
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exit(1); });
