// Isolated headless rendering of this local page only; GPU use is disabled.
const fs=require('fs');
const path=require('path');
const {chromium}=require('playwright');
const checks=[],errors=[];
function check(name,value){if(!value)throw Error(name);checks.push(name);}
(async()=>{
  const {url}=JSON.parse(fs.readFileSync(path.join(__dirname,'service.json'),'utf8'));
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:1000}});
    page.on('pageerror',e=>errors.push(e.message));
    let responses=0;
    page.on('response',r=>{if(r.url().includes('/api/snapshot')&&r.status()===200)responses++;});
    await page.goto(url);
    await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('采集正常'));
    check('two_models',await page.locator('.model').count()===2);
    check('eighteen_epochs',await page.locator('.epochs li').count()===18);
    check('live_update_count',Number((await page.locator('#updates').innerText()).replaceAll(',',''))>=480);
    check('no_unsealed_metric_fabrication',(await page.locator('#paired').innerText()).includes('尚未齐备'));
    await page.locator('#model-filter').selectOption('B4');
    check('model_filter',await page.locator('#metrics tr').count()===9);
    check('filter_in_url',new URL(page.url()).searchParams.get('model')==='B4');
    await page.locator('#model-filter').selectOption('all');
    const before=responses;
    await page.waitForResponse(r=>r.url().includes('/api/snapshot')&&r.status()===200,{timeout:18000});
    check('fifteen_second_auto_refresh',responses>before);
    await page.locator('#auto').uncheck();
    const updates=await page.locator('#updates').innerText();
    await page.route('**/api/snapshot',route=>route.abort());
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>!document.getElementById('error').hidden);
    check('disconnect_retains_last_snapshot',updates===await page.locator('#updates').innerText());
    check('disconnect_not_training_failure',await page.locator('#failure').isHidden());
    await page.unroute('**/api/snapshot');
    await page.locator('#refresh').click();
    await page.waitForFunction(()=>document.getElementById('error').hidden);
    check('reconnect',await page.locator('#error').isHidden());
    await page.screenshot({path:path.join(__dirname,'desktop.png'),fullPage:true});
    for(const width of [680,360,320]){
      await page.setViewportSize({width,height:1000});
      check('no_page_overflow_'+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    await page.screenshot({path:path.join(__dirname,'mobile.png'),fullPage:true});
    check('no_javascript_errors',errors.length===0);
  }finally{await browser.close();}
  const result={status:'PASS',checks,errors};fs.writeFileSync(path.join(__dirname,'page-checks.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{fs.writeFileSync(path.join(__dirname,'page-check-failure.json'),JSON.stringify({status:'FAIL',checks,error:e.stack},null,2));console.error(e);process.exitCode=1;});
