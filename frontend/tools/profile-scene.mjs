import {chromium} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true,args:['--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
await page.addInitScript(()=>{
  window.__draws=0;window.__triangles=0;
  for(const Type of [window.WebGLRenderingContext,window.WebGL2RenderingContext]) {
    for(const name of ['drawElements','drawArrays','drawElementsInstanced','drawArraysInstanced']) {
      const original=Type?.prototype[name];if(!original)continue;
      Type.prototype[name]=function(...args) {
        window.__draws++;
        const count=(name.includes('Elements')?args[1]:args[2])/3*(name.includes('Instanced')?args.at(-1):1);
        if(args[0]===4&&Number.isFinite(count)) window.__triangles+=count;
        return original.apply(this,args);
      };
    }
  }
});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(process.env.PROFILE_URL || 'http://127.0.0.1:5173/');
await page.locator('canvas').first().waitFor({timeout:40000});
await page.waitForTimeout(6000);
const stats=await page.evaluate(()=>new Promise(resolve=>{
  const start=performance.now(),draws=window.__draws,triangles=window.__triangles;let frames=0;
  function frame(now) {frames++;if(now-start<4000)requestAnimationFrame(frame);else resolve({fps:Math.round(frames*1000/(now-start)),drawCallsPerFrame:Math.round((window.__draws-draws)/frames),trianglesPerFrame:Math.round((window.__triangles-triangles)/frames)});}
  requestAnimationFrame(frame);
}));
await page.screenshot({path:`e2e-artifacts/${process.env.PROFILE_NAME || 'scene-profile'}.png`});
await writeFile(`e2e-artifacts/${process.env.PROFILE_NAME || 'scene-profile'}.json`,JSON.stringify({...stats,errors},null,2));
console.log(JSON.stringify({...stats,errors}));
await browser.close();
