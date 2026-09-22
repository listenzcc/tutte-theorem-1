// 交叉验算：在 node 里用 DOM stub 跑 bunny-tutte.html 的脚本，比对区域拓扑、翻面数与面积畸变。
// 用法： C:/Users/liste/.workbuddy/binaries/node/versions/22.22.2-3/node.exe check-bunny-page.js
// 期望： ear/h10 → 231/663/433 面 χ=1 环 27 翻面 0 面积 397.3%
//        ear/h26 → 1496/4394/2899 环 91 翻面 0 面积 58.0%
//        star    → 翻面 14； nose h30 禁回退 → 非圆盘
// 同一组数字应与 render-bunny-figs.py 的输出一致。
const fs=require('fs'),vm=require('vm');
const code=fs.readFileSync('bunny-tutte.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const noop=()=>{};
function stubCtx(){const o={};['clearRect','beginPath','moveTo','lineTo','closePath','clip','fill','stroke','save','restore','transform','setTransform','drawImage','fillRect','fillText','strokeRect','setLineDash','arc','rect','scale'].forEach(k=>o[k]=noop);o.measureText=()=>({width:10});return o;}
const els={};const D={seed:'ear',hop:'10',shape:'circle',weight:'mvc',view:'tex',fallback:'on'};
function fakeEl(id){if(els[id])return els[id];const e={id,textContent:'',innerHTML:'',className:'',style:{},value:D[id]||'',checked:D[id]==='on',_h:{},
  addEventListener:(t,f)=>{(e._h[t]=e._h[t]||[]).push(f);},setPointerCapture:noop,removeAttribute:noop,
  clientWidth:560,clientHeight:460,width:560,height:460,getContext:stubCtx};els[id]=e;return e;}
let pending=[];
const sb={console,Math,Date,Promise,Float64Array,Int32Array,Array,Set,Map,Object,JSON,isNaN,parseFloat,Infinity,
  fetch:()=>Promise.resolve({ok:true,text:()=>Promise.resolve(fs.readFileSync('model/bunny_small.obj','utf8'))}),
  window:{devicePixelRatio:1},location:{search:''},URLSearchParams,
  document:{getElementById:fakeEl,createElement:()=>({width:0,height:0,getContext:stubCtx,toDataURL:()=>'data:,'})},
  requestAnimationFrame:cb=>{pending.push(cb);}};
sb.globalThis=sb;vm.createContext(sb);
vm.runInContext(code,sb,{filename:'bunny.js'});
function drain(n){for(let i=0;i<n;i++){const cb=pending.shift();if(!cb)return i;cb();}return n;}
function fire(id,t,v){const e=fakeEl(id);if(v!==undefined){e.value=String(v); if(v==='off')e.checked=false; if(v==='on')e.checked=true;}(e._h[t]||[]).forEach(f=>f({target:e,preventDefault:noop}));}
function rep(tag){const g=id=>String(els[id]?els[id].textContent:'-');
  console.log(tag.padEnd(24),'| χ:',g('sChi').padEnd(12),'| 环:',g('sLoop').padEnd(9),'| 面:',g('sSub').padEnd(16),'| 翻面:',g('sFlip').padEnd(11),'| 面积:',g('sArea').padEnd(8),'|',g('sVerdict'));}
(async()=>{
  await new Promise(r=>setImmediate(r));
  await new Promise(r=>setImmediate(r));
  if(!pending.length){console.error('!! 主循环没启动');console.error('msg:',els['msg']?els['msg'].innerHTML:'(no msg el)');process.exit(1);}
  drain(600);rep('默认 ear/h10');
  console.log('   msg:',els['msg'].innerHTML.replace(/<[^>]+>/g,'').trim());
  for(const s of ['nose','tail','back','belly']){ fire('seed','change',s); drain(600); rep('seed='+s);
    console.log('   msg:',els['msg'].innerHTML.replace(/<[^>]+>/g,'').trim().slice(0,80)); }
  fire('seed','change','ear');
  for(const h of [6,14,20,26,32]){ fire('hop','input',h); drain(600); rep('hop='+h); }
  fire('hop','input',32); drain(4000); rep('hop=32 多跑');
  fire('hop','input',10); drain(400);
  fire('shape','change','star'); drain(600); rep('star');
  fire('shape','change','ell'); drain(600); rep('L 形');
  fire('shape','change','circle');
  fire('weight','change','cotan'); drain(600); rep('cotan');
  fire('weight','change','uniform'); drain(600); rep('uniform');
  fire('weight','change','mvc'); drain(600);
  fire('view','change','dist'); drain(20); rep('view=dist');
  fire('view','change','wire'); drain(20); rep('view=wire');
  fire('view','change','chart'); drain(20); rep('view=chart');
  fire('seed','change','nose'); fire('fallback','change','off'); fire('hop','input',30); drain(300); rep('禁回退 nose h30');
  console.log('   msg:',els['msg'].innerHTML.replace(/<[^>]+>/g,'').trim().slice(0,120));
  console.log('OK, pending =',pending.length);
})();
