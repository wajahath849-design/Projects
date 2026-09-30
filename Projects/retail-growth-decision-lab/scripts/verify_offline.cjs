const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({offline:true});
 const page=await context.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const url=pathToFileURL(path.resolve(__dirname,'../dashboard/.data-app-offline/exports/retail-growth-lab.html'));
 await page.goto(`${url}?view=1&tab=campaign`);
 await page.getByText('Scenario assumptions',{exact:true}).waitFor();
 assert.equal(await page.locator('[data-component-id="scenario-contacts"] .metric-value').innerText(),'1,000');
 await page.getByRole('slider',{name:'Budget',exact:true}).fill('0');
 await page.waitForFunction(()=>document.querySelector('[data-component-id="scenario-contacts"] .metric-value')?.textContent==='0');
 assert.deepEqual(errors,[]);
 console.log('Offline single-file dashboard loads with network disabled; scenario interaction passed.');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
