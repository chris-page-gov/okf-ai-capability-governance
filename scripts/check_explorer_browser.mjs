/** Verify both scope-specific guides against an exact, independently built Reader. */
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {mkdir,readFile,readdir,realpath,stat,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const consumer=process.env.OKF_EXPLORER_ROOT;
if(!consumer||!path.isAbsolute(consumer))throw Error('Set OKF_EXPLORER_ROOT to the exact pinned consumer checkout');
const pin=JSON.parse(await readFile(path.join(root,'source/explorer-consumer.json')));
if(execFileSync('git',['-C',consumer,'rev-parse','HEAD'],{encoding:'utf8'}).trim()!==pin.commit)throw Error('Consumer commit differs from the reviewed pin');
const req=createRequire(path.join(consumer,'apps/okf-explorer/package.json'));
const {chromium}=req('@playwright/test');const AxeBuilder=req('@axe-core/playwright');
const {staticBuildFile}=await import(pathToFileURL(path.join(consumer,'apps/okf-explorer/scripts/external_bundle_acceptance_contract.mjs')));
const build=path.join(consumer,'apps/okf-explorer/build');
const manifest=JSON.parse(await readFile(path.join(build,'okf-explorer-build-manifest.json')));
if(manifest.tree_sha256!==pin.tree_sha256)throw Error('Consumer build differs from the reviewed bytes');
const buildFiles=new Map(manifest.materials.map(row=>[row.path,row]));
const site=path.join(root,'_site');const output=path.resolve(process.argv[2]||path.join(root,'release-assurance/tmp/explorer-browser.json'));
await mkdir(path.dirname(output),{recursive:true});
const producerPublic='https://chris-page-gov.github.io/okf-ai-capability-governance/';
const readerPublic='https://chris-page-gov.github.io/okf-explorer/';
const sha=b=>createHash('sha256').update(b).digest('hex');
const check=(value,message)=>{if(!value)throw Error(message);};
const report={status:'failed',observed_at:new Date().toISOString(),consumer:pin,scope:'Exact local Pages candidate, two distinct bundles; public acceptance remains separate.',journeys:[],diagrams:[],assets:[]};
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.md':'text/plain','.txt':'text/plain','.png':'image/png','.jpg':'image/jpeg','.jsonld':'application/ld+json','.yamlld':'application/ld+yaml'};
const server=createServer(async(request,response)=>{
 try{
  const url=new URL(request.url,'http://localhost');let base,relative;
  if(url.pathname.startsWith('/producer/')){base=site;relative=url.pathname.slice('/producer/'.length);}
  else{base=build;relative=staticBuildFile(url.pathname.slice(1),buildFiles);if(relative==='404.html'&&url.pathname!=='/404.html')throw Error('Unknown app route');}
  relative=decodeURIComponent(relative);check(!relative.includes('\\')&&!relative.split('/').includes('..'),'Unsafe static path');
  const file=await realpath(path.resolve(base,relative));check(file.startsWith(await realpath(base)+path.sep),'Static path escaped');
  const bytes=await readFile(file);response.writeHead(200,{'content-type':mime[path.extname(file)]||'application/octet-stream','access-control-allow-origin':'*','cache-control':'no-store'});response.end(bytes);
 }catch{response.writeHead(404);response.end('Not found');}
});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
const local='http://127.0.0.1:'+server.address().port;
let browser,timer;
const deadline=Date.now()+240000;
const limits={files:2000,fileBytes:16*1024*1024,totalBytes:128*1024*1024};
const inventoryState={files:0,bytes:0};
function withinDeadline(){check(Date.now()<deadline,'Overall browser and asset deadline exceeded');}
async function inventory(directory,prefix=''){
 withinDeadline();
 const rows=[];
 for(const item of await readdir(directory,{withFileTypes:true})){
  check(!item.isSymbolicLink(),'Site symlink rejected');const relative=prefix+item.name;
  if(item.isDirectory())rows.push(...await inventory(path.join(directory,item.name),relative+'/'));
  else if(item.isFile()){
   const size=(await stat(path.join(directory,item.name))).size;
   inventoryState.files++;inventoryState.bytes+=size;
   check(inventoryState.files<=limits.files&&size<=limits.fileBytes&&inventoryState.bytes<=limits.totalBytes,'Site inventory exceeded reviewed bounds');
   rows.push(relative);
  }
 }
 return rows.sort();
}
try{
 browser=await chromium.launch({channel:'chrome',chromiumSandbox:true});timer=setTimeout(()=>browser.close(),240000);
 for(const scope of ['bundle','site-bundle']){
  const evidence=JSON.parse(await readFile(path.join(site,scope,'walkthrough-evidence.json')));
  check(evidence.reader_url&&evidence.primary_route&&evidence.primary_title&&evidence.primary_source_url,'Missing source-bound guide interface');
  for(const viewport of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844}]){
   const context=await browser.newContext({viewport,serviceWorkers:'block'}),page=await context.newPage();page.setDefaultTimeout(15000);const errors=[];
   report.current={scope,viewport:viewport.name,errors};
   page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('pageerror',e=>errors.push(String(e)));page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url());});
   await context.route(readerPublic+'**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/okf-explorer/explore/'&&url.searchParams.get('bundle')===producerPublic+scope+'/okf-explorer.json'){
     const target=new URL('/explore/',local);for(const[k,v]of url.searchParams)target.searchParams.set(k,v);target.searchParams.set('bundle',local+'/producer/'+scope+'/okf-explorer.json');target.hash=evidence.primary_route;await route.fulfill({status:302,headers:{location:target.href}});return;
    }
    const response=await route.fetch({url:local+'/'+url.pathname.slice('/okf-explorer/'.length)+url.search});await route.fulfill({response});
   });
   await context.route(producerPublic+'**',async route=>{const response=await route.fetch({url:local+'/producer/'+route.request().url().slice(producerPublic.length)});await route.fulfill({response});});
   const response=await page.goto(local+'/producer/'+scope+'/walkthrough.html',{waitUntil:'domcontentloaded'});check(response.ok(),'Guide unavailable');
   const icon=page.locator('head link[rel="icon"]');
   check(await icon.count()===1&&await icon.getAttribute('href')==='../favicon.png','Guide must declare the bundled icon without a root-domain fallback');
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Guide horizontal overflow');
   const guideAxe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();check(!guideAxe.violations.length,'Guide accessibility: '+guideAxe.violations.map(v=>v.id));
   const prefix=output.replace(/\.json$/,'')+'-'+scope+'-'+viewport.name;await page.screenshot({path:prefix+'-guide.png',fullPage:true});
   const link=page.locator('[data-reader-link="primary"]');check(await link.getAttribute('href')===evidence.reader_url,'Guide link differs from evidence');await link.click();
   const heading=page.locator('.right-panel h2').filter({hasText:evidence.primary_title}).first();
   async function details(){
    if(viewport.width<1100&&!await heading.isVisible()){
     const details=page.getByRole('button',{name:'Details',exact:true});if(await details.isVisible())await details.click();else await page.getByRole('button',{name:'Inspect',exact:true}).click();
    }else if(viewport.width>=1100){const toggle=page.getByRole('button',{name:'Toggle details'});if(await toggle.getAttribute('aria-expanded')==='false')await toggle.click();}
    await heading.waitFor({state:'visible'});
   }
   await details();check(decodeURIComponent(new URL(page.url()).hash.slice(1))===evidence.primary_route,'Wrong source record');
   async function showEvidence(){
    await page.locator('.right-panel').getByRole('tab',{name:'Evidence',exact:true}).click();
    const citations=await page.locator('.right-panel .small-node-links a').evaluateAll(links=>links.filter(link=>link.getClientRects().length).map(link=>link.href));
    check(citations.includes(evidence.primary_source_url),'Evidence panel hides the original source citation');
   }
   await showEvidence();
   check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Reader horizontal overflow');
   const readerAxe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();check(!readerAxe.violations.length,'Reader accessibility: '+readerAxe.violations.map(v=>v.id));
   await page.screenshot({path:prefix+'-reader.png',fullPage:true});await page.reload({waitUntil:'domcontentloaded'});await details();await showEvidence();check(decodeURIComponent(new URL(page.url()).hash.slice(1))===evidence.primary_route,'Reload lost source record');check(!errors.length,'Browser errors: '+errors.join('; '));
   report.journeys.push({scope,viewport:viewport.name,route:evidence.primary_route,source_url:evidence.primary_source_url,guide_axe:0,reader_axe:0,reload:true,errors});await context.close();
  }
  const diagram=await browser.newPage();
  await diagram.goto(local+'/producer/'+scope+'/walkthrough.svg',{waitUntil:'domcontentloaded'});
  const geometry=await diagram.evaluate(async()=>{
   await document.fonts.ready;
   const canvas=document.documentElement.viewBox.baseVal;
   const text=[...document.querySelectorAll('text')].map(element=>{
    const box=element.getBBox();
    return{text:element.textContent,x:box.x,y:box.y,width:box.width,height:box.height};
   });
   return{canvas:{x:canvas.x,y:canvas.y,width:canvas.width,height:canvas.height},text,clipped:text.filter(box=>box.x<canvas.x||box.y<canvas.y||box.x+box.width>canvas.x+canvas.width+1||box.y+box.height>canvas.y+canvas.height+1)};
  });
  report.diagrams.push({scope,...geometry});
  check(!geometry.clipped.length,'Diagram text outside its canvas: '+JSON.stringify(geometry.clipped));
  await diagram.close();
 }
 for(const relative of await inventory(site)){
  withinDeadline();
  const original=await readFile(path.join(site,relative));const response=await fetch(local+'/producer/'+relative.split('/').map(encodeURIComponent).join('/'),{signal:AbortSignal.timeout(15000)});const actual=Buffer.from(await response.arrayBuffer());check(response.ok&&sha(actual)===sha(original),'Site asset mismatch: '+relative);report.assets.push({path:relative,bytes:actual.length,sha256:sha(actual)});
 }
 report.status='passed';report.browser=browser.version();
}catch(error){report.failure=String(error.stack||error);process.exitCode=1;}
finally{clearTimeout(timer);await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await writeFile(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({status:report.status,journeys:report.journeys.length,assets:report.assets.length,failure:report.failure}));}
