// Package only the verified standalone source build. No external service needed.
import {readFileSync, mkdirSync, copyFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash} from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=path.join(root,'dashboard/dist/index.html');
const html=readFileSync(source,'utf8');
const snapshot=readFileSync(path.join(root,'dashboard/src/data.json'));
const hash=createHash('sha256').update(snapshot).digest('hex');
if(!html.includes(hash)) throw new Error('Dashboard build is stale: rebuild from the current snapshot.');
if(/<meta[^>]+name=["']data-app-local-(thread|reference)["']/i.test(html)) throw new Error('Build includes local task metadata. Remove CODEX_SESSION_ID and CODEX_THREAD_ID from the build environment.');
for(const relative of ['dashboard/.data-app-offline/exports/retail-growth-lab.html','docs/demo/index.html']) {
 const target=path.join(root,relative);mkdirSync(path.dirname(target),{recursive:true});copyFileSync(source,target);
}
console.log('Packaged offline dashboard and docs/demo/index.html.');
