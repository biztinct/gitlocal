/* End-to-end checks against an isolated Google Chrome context. No customer sessions. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const target=process.env.WORKFLOW_TEST_URL||'http://127.0.0.1:8842/workflow-studio-poc.html';
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({viewport:{width:1512,height:1100},acceptDownloads:true});
 const page=await context.newPage(),errors=[],results=[];
 page.on('pageerror',e=>errors.push(String(e)));
 const check=(name)=>{results.push(name);console.log('PASS',name)};
 const click=a=>page.locator(`[data-action="${a}"]`).filter({visible:true}).first().click();
 const close=()=>page.locator('#modal [data-action=close]').click();
 const trace=()=>page.locator('#trace').innerText();
 try{
  const response=await page.goto(target);assert.equal(response.status(),200);await page.locator('[data-node=manager]').waitFor();check('Deployed HTML loads and initial workflow renders');
  await page.locator('[data-node=manager]').click();await page.locator('[data-edit=title]').fill('Regional manager approval');await page.locator('[data-edit=title]').press('Tab');assert.match(await page.locator('[data-node=manager]').innerText(),/Regional manager approval/);check('Editing a step updates the journey');
  await page.locator('[data-view=blueprint]').click();assert.match(await page.locator('.lane-board').innerText(),/Regional manager approval/);check('Blueprint shares the edited definition');
  await page.locator('[data-view=canvas]').click();assert.match(await page.locator('[data-node=manager]').innerText(),/Regional manager approval/);assert.equal(await page.locator('.canvas-svg path[marker-end]').count(),6);check('Canvas renders shared nodes and both decision paths');
  const node=page.locator('[data-node=manager]'),before=await node.boundingBox();await page.mouse.move(before.x+50,before.y+20);await page.mouse.down();await page.mouse.move(before.x+105,before.y+50,{steps:12});await page.mouse.up();const after=await node.boundingBox();assert(after.x>before.x+35);check('Canvas node moves with a real pointer drag');
  await page.locator('[data-view=journey]').click();await page.locator('[data-block=task]').dragTo(page.locator('[data-drop-stage="0"] .drop-add'));assert.equal(await page.locator('.step.type-task').count(),1);check('Dragging a building block creates a configured step');
  await click('undo');assert.equal(await page.locator('.step.type-task').count(),0);check('Undo removes the added step');
  await page.locator('[data-view=blueprint]').click();await page.locator('[data-node=manager]').dragTo(page.locator('.lane-cell[data-drop-stage="1"][data-owner="Finance approver"]'));await page.locator('[data-node=manager]').click();assert.equal(await page.locator('[data-edit=owner]').inputValue(),'Finance approver');check('Blueprint drag changes the responsible role');await click('undo');
  await click('simulate');assert.match(await trace(),/Example complete/);assert.match(await trace(),/Jordan Taylor/);check('High-value scenario reaches Finance and completion');
  await page.locator('[data-sim=amount]').fill('500');await page.locator('[data-sim=amount]').press('Tab');assert.match(await page.locator('.trace-row.skip').innerText(),/Finance approval/);check('Low-value condition skips Finance and rejoins');
  await page.locator('[data-sim=manager]').selectOption('away');assert.match(await trace(),/Alex Lee covers Maya Chen/);check('Valid delegation resolves a substitute');
  await page.locator('[data-sim=manager]').selectOption('expired');assert.match(await trace(),/cover has expired/);assert(!/Email preview/.test(await trace()));check('Expired delegation blocks downstream actions');
  await page.locator('[data-sim=manager]').selectOption('available');await page.locator('[data-sim=access]').selectOption('denied');assert.match(await trace(),/cannot read or act/);check('Access denial stops the run');
  await page.locator('[data-sim=access]').selectOption('allowed');await page.locator('[data-sim=actor]').selectOption('self');assert.match(await trace(),/also the requester/);check('Separation of duties blocks self-approval');
  await page.locator('[data-sim=actor]').selectOption('other');await page.locator('[data-sim=decision]').selectOption('reject');assert.match(await trace(),/Request rejected/);assert(!/Email preview/.test(await trace()));check('Rejection prevents completion and email');
  await page.locator('[data-sim=decision]').selectOption('approve');await close();
  await click('scope');await click('add-rule');await click('save-scope');await click('simulate');await page.locator('[data-sim=department]').selectOption('Finance');assert.match(await trace(),/Record excluded/);await page.locator('[data-sim=department]').selectOption('Operations');assert.match(await trace(),/Example complete/);check('Eligibility filters include and exclude records');await close();
  await page.locator('[data-view=journey]').click();await page.locator('[data-node=rule]').click();await page.locator('[data-edit=value]').fill('300');await page.locator('[data-edit=value]').press('Tab');await click('simulate');assert.match(await trace(),/Jordan Taylor/);check('Edited threshold changes the simulated execution path');await close();
  await click('publish');await click('confirm-version');assert.match(await page.locator('#save-status').innerText(),/v1 saved locally/);check('Validated version snapshot saves locally');
  await page.locator('[data-node=email]').click();await page.locator('[data-edit=body]').fill('');await page.locator('[data-edit=body]').press('Tab');await click('publish');assert(await page.locator('[data-action=confirm-version]').isDisabled());assert.match(await page.locator('#modal-body').innerText(),/write the email message/);check('Incomplete action blocks version save');await close();
  await click('history');await page.locator('[data-restore]').click();await page.locator('[data-node=email]').click();assert.match(await page.locator('[data-edit=body]').inputValue(),/Your request/);check('Restoring a version recovers its immutable snapshot');
  await page.reload();await page.locator('[data-view=journey]').click();assert.match(await page.locator('[data-node=manager]').innerText(),/Regional manager approval/);check('Browser-local draft survives a reload');
  const downloading=page.waitForEvent('download');await click('export');const download=await downloading;const file=await download.path();const exported=JSON.parse(fs.readFileSync(file,'utf8'));assert.equal(exported.prototype_only,true);assert.equal(exported.nodes.length,6);assert.equal(exported.edges.length,6);check('JSON export contains the edited graph and POC compatibility label');
  await click('compare');for(const a of ['architecture','capabilities','roadmap','sources','compare']){await page.locator(`#modal [data-action="${a}"]`).click();assert((await page.locator('#modal-body').innerText()).length>500)}check('Recommendation, architecture, gaps, roadmap and research panels work');await close();
  for(const key of ['leave','onboarding','hiring','offboarding','payroll','expense']){await click('templates');await page.locator(`[data-template="${key}"]`).click();await click('simulate');assert.match(await trace(),/Example complete/);await close()}check('All six process templates simulate successfully');
  await click('recipe');await click('apply-recipe');assert.equal(await page.locator('.step').count(),9);await click('simulate');assert.match(await trace(),/Example complete/);check('Guided recipe creates an executable example route');await close();await click('undo');
  await page.locator('[data-action=stage][data-index="1"]').click();await click('add-stage');await page.locator('[name=stage-name]').fill('Quality check');await click('save-stage');assert.equal(await page.locator('.stage').count(),4);await page.locator('[data-view=blueprint]').click();assert.match(await page.locator('.lane-headers').innerText(),/Quality check/);await page.locator('[data-view=canvas]').click();assert.equal(await page.locator('.graph-node').count(),6);await click('undo');await click('undo');check('Adding a phase updates all three views and can be undone');
  const screenshots=process.env.WORKFLOW_SCREENSHOT_DIR;if(screenshots){fs.mkdirSync(screenshots,{recursive:true});for(const view of ['journey','canvas','blueprint']){await page.locator(`[data-view="${view}"]`).click();await page.screenshot({path:`${screenshots}/${view}.jpg`,fullPage:true})}}
  await page.setViewportSize({width:390,height:844});await page.locator('[data-view=journey]').click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.locator('[data-node=trigger]').click();await click('simulate');assert.match(await trace(),/Example complete/);await close();if(screenshots)await page.screenshot({path:`${screenshots}/mobile.jpg`,fullPage:true});check('Mobile viewport keeps page bounded and editor controls usable');
  assert.deepEqual(errors,[]);check('No uncaught browser JavaScript errors');
  console.log(JSON.stringify({url:target,browser:'Google Chrome',checks:results.length,results,errors},null,2));
 }finally{await context.close();await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
