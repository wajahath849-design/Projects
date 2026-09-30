export const defaults = {budget:1000,cost:1,margin:.35,uplift:.03};

export function economics(rows, {cost,margin,uplift}) {
  if (![cost,margin,uplift].every(Number.isFinite) || cost<=0 || margin<0 || margin>1 || uplift<0 || uplift>1) throw new Error('Invalid campaign assumptions');
  let orders=0, gross=0;
  for (const row of rows) {
    const delta=Math.min(uplift,Math.max(0,1-row.purchase_probability));
    orders+=delta; gross+=delta*row.order_value*margin;
  }
  return {orders,gross,spend:rows.length*cost,contribution:gross-rows.length*cost};
}

export function breakEven(rows, options) {
  if (!rows.length) return null;
  if (economics(rows,{...options,uplift:1}).contribution<0) return null;
  let low=0,high=1;
  for(let i=0;i<50;i++) {
    const mid=(low+high)/2;
    if(economics(rows,{...options,uplift:mid}).contribution>=0) high=mid; else low=mid;
  }
  return high;
}

export function campaignCsv(rows, assumptions) {
  const keys=['customer_id','country','segment','purchase_probability','order_value','priority_score','currency',
    'scenario_budget','contact_cost','assumed_margin','assumed_absolute_uplift','assumed_incremental_contribution'];
  const cell=value=>'"'+String(value??'').replaceAll('"','""')+'"';
  return [keys.join(','),...rows.map(row=>{
    const values={...row,currency:'EUR',scenario_budget:assumptions.budget,contact_cost:assumptions.cost,
      assumed_margin:assumptions.margin,assumed_absolute_uplift:assumptions.uplift,
      assumed_incremental_contribution:economics([row],assumptions).contribution};
    return keys.map(key=>cell(values[key])).join(',');
  })].join('\r\n');
}
