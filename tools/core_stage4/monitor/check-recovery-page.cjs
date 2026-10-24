const fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const checks=[];
function check(name,ok){if(!ok)throw Error(name);checks.push(name);}
(async()=>{
  const {url}=JSON.parse(fs.readFileSync(path.join(__dirname,'service.json'),'utf8'));
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
  try{
    const page=await browser.newPage({viewport:{width:1360,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);await page.waitForFunction(()=>document.getElementById('connection').textContent.includes('采集正常'));
    await page.locator('#auto').uncheck();
    check('approved_9120_cap',(await page.locator('#update-limit').innerText()).includes('9,120'));
    check('historical_cost_disclosed',(await page.locator('#recovery-note').innerText()).includes('1,920'));
    check('three_inherited_LAST',await page.locator('.model').first().locator('.epochs .SEALED').count()===3);
    check('inherited_metrics_displayed',!(await page.locator('#metrics tr').first().locator('td').nth(3).innerText()).includes('—'));
    check('no_old_failure_alert',await page.locator('#failure').isHidden());
    check('no_runtime_errors',errors.length===0);
    await page.screenshot({path:path.join(__dirname,'recovery-desktop.png'),fullPage:true});
    fs.writeFileSync(path.join(__dirname,'recovery-page-checks.json'),JSON.stringify({status:'PASS',checks},null,2));console.log(JSON.stringify({status:'PASS',checks}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
