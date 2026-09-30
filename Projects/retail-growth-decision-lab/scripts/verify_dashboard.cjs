// Optional UI checks: install Playwright and Microsoft Edge, start the local server.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const base=process.env.DASHBOARD_URL || 'http://127.0.0.1:4173/';

(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true,locale:'en-GB'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const checks=[];
 const metric=(id)=>page.locator(`[data-component-id="${id}"] .metric-value`);
 async function equalMetric(id,text){await page.waitForFunction(({id,text})=>document.querySelector(`[data-component-id="${id}"] .metric-value`)?.textContent===text,{id,text});}
 const tabs={performance:'Net merchandise revenue',retention:'Weighted month-1 retention',model:'Average precision',campaign:'Scenario assumptions'};
 for(const [tab,title] of Object.entries(tabs)){
  await page.goto(`${base}?view=1&tab=${tab}`);
  await page.getByText(title,{exact:true}).first().waitFor();
  assert.ok(!(await page.locator('body').innerText()).includes('ChatGPT'));
  assert.equal(await page.getByRole('button',{name:'Publish',exact:true}).count(),0);
  await page.screenshot({path:path.join(root,`reports/${tab}-preview.png`),fullPage:true});
  assert.ok(await page.locator('[data-component-id]').count()>2);
  checks.push(`Desktop ${tab}: rendered`);
 }
 await page.getByRole('button',{name:'More',exact:true}).click();
 await page.getByRole('menuitem',{name:'Print / save PDF',exact:true}).waitFor();
 await page.getByRole('menuitem',{name:'Switch theme',exact:true}).waitFor();
 assert.ok(!(await page.locator('body').innerText()).includes('ChatGPT'));
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Edit text and layout',exact:true}).click();
 await page.getByRole('button',{name:'Save',exact:true}).waitFor();
 await page.getByRole('button',{name:'Cancel',exact:true}).click();
 checks.push('Standalone menu and edit/cancel: no assistant actions; local controls preserved');
 await equalMetric('scenario-contacts','1,000');
 await equalMetric('scenario-economics','€6,955');
 await page.getByRole('slider',{name:'Budget',exact:true}).fill('0');
 await equalMetric('scenario-contacts','0');
 assert.equal(await page.getByRole('button',{name:'Export selected CSV'}).isDisabled(),true);
 await page.getByRole('button',{name:'Reset scenario',exact:true}).click();
 await page.getByRole('slider',{name:'Assumed absolute uplift',exact:true}).fill('0');
 await equalMetric('scenario-economics','-€1,000');
 await page.getByRole('button',{name:'Reset scenario',exact:true}).click();
 await page.getByRole('slider',{name:'Cost per contact',exact:true}).fill('0.5');
 await equalMetric('scenario-contacts','2,000');
 assert.equal(await page.getByRole('slider',{name:'Cost per contact',exact:true}).getAttribute('aria-valuetext'),'€0.50');
 await page.reload();await equalMetric('scenario-contacts','2,000');
 await page.getByRole('button',{name:'Reset scenario',exact:true}).click();
 await equalMetric('scenario-contacts','1,000');
 checks.push('Scenario: zero budget, zero uplift, cost changes, reload persistence, reset');
 await page.locator('button[aria-label="Country"]').click();
 await page.getByRole('menuitemradio',{name:'Spain',exact:true}).click();
 const expected=JSON.parse(fs.readFileSync(path.join(root,'dashboard/src/data.json'),'utf8')).queries.candidates.rows.filter(r=>r.country==='Spain');
 await equalMetric('scenario-contacts',String(expected.length));
 await page.reload();await equalMetric('scenario-contacts',String(expected.length));
 const downloading=page.waitForEvent('download');
 await page.getByRole('button',{name:'Export selected CSV'}).click();
 const download=await downloading;const csv=fs.readFileSync(await download.path(),'utf8');
 assert.equal(csv.split('\r\n').length,expected.length+1);
 assert.ok(csv.includes('assumed_absolute_uplift'));
 assert.ok(csv.split('\r\n').slice(1).every(line=>line.includes('"EUR"')));
 assert.ok(csv.split('\r\n').slice(1).every(line=>line.includes('"Spain"')));
 checks.push(`Country filter + reload + CSV: ${expected.length} Spain customers, assumptions included`);
 await page.getByRole('button',{name:'Reset scenario',exact:true}).click();
 const card=page.locator('[data-component-id="scenario-economics"]');
 await card.locator('button.menu-trigger').click();
 await page.getByRole('menuitem',{name:'View data source',exact:true}).click();
 await page.getByText('models/candidates_eur.csv',{exact:true}).waitFor();
 await page.getByText('Open reviewed source',{exact:true}).waitFor();
 await page.screenshot({path:path.join(root,'reports/source-preview.png'),fullPage:true});
 checks.push('Source inspection opens with provenance');
 await page.setViewportSize({width:390,height:844});
 for(const [tab,title] of Object.entries(tabs)){
  await page.goto(`${base}?view=1&tab=${tab}`);
  await page.getByText(title,{exact:true}).first().waitFor();
  assert.ok(!(await page.locator('body').innerText()).includes('ChatGPT'));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),`Page overflow on ${tab}`);
  await page.screenshot({path:path.join(root,`reports/${tab}-mobile.png`),fullPage:true});
  checks.push(`Mobile ${tab}: no page-wide overflow`);
 }
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(root,'reports/browser-checks.json'),JSON.stringify({checkedAt:new Date().toISOString(),checks,consoleErrors:errors},null,2));
 console.log(checks.join('\n'));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
