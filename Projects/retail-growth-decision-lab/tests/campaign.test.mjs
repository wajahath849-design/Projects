import test from 'node:test';
import assert from 'node:assert/strict';
import {economics, breakEven, campaignCsv, defaults} from '../dashboard/src/content/dashboard/campaign.js';

const row={customer_id:'12345',country:'Example, country',segment:'Active',purchase_probability:.2,order_value:100,priority_score:80};
test('zero uplift loses contact cost; no selected customers costs zero',()=>{
  assert.equal(economics([row],{...defaults,uplift:0}).contribution,-1);
  assert.equal(economics([],defaults).contribution,0);
  assert.equal(breakEven([],defaults),null);
});
test('incremental purchases cannot exceed probability headroom',()=>{
  const out=economics([{...row,purchase_probability:.99}],{cost:1,margin:1,uplift:.5});
  assert.ok(Math.abs(out.orders-.01)<1e-10);
});
test('break-even uplift solves economics and handles impossible margin',()=>{
  const threshold=breakEven([row],defaults);
  assert.ok(Math.abs(threshold-1/35)<1e-10);
  assert.ok(Math.abs(economics([row],{...defaults,uplift:threshold}).contribution)<1e-10);
  assert.equal(breakEven([row],{...defaults,margin:0}),null);
});
test('CSV preserves identifiers, quoted text, and scenario assumptions',()=>{
  const csv=campaignCsv([{...row,country:'A, "B"'}],defaults);
  assert.ok(csv.includes('"12345","A, ""B"""'));
  assert.ok(csv.includes('assumed_absolute_uplift'));
  assert.ok(csv.includes('"EUR"'));
  assert.ok(csv.includes('"1000","1","0.35","0.03"'));
});
