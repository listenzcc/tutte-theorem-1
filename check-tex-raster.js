/* 把 HTML 里真实的贴图生成代码光栅化成 PPM，用于和 render-bunny-figs.py 的
   uv_checker() 做逐像素比对。最小 canvas stub，只实现 fillRect + source-over。

   两种模式自动识别：
     function makeChecker() { ... }        → bunny-tutte.html / uv-texture-mapping.html
     const texCanvas = (function () {...}) → tutte-embedding-theorem.html（纹理范围 [-4,4]）

   用法：node check-tex-raster.js <in.html> <out.ppm> */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(process.argv[2], 'utf8');
const texnM = html.match(/const TEXN\s*=\s*(\d+)/);
if (!texnM) { console.error('没找到 TEXN'); process.exit(1); }
const TEXN = +texnM[1];

let body, name;
const fn = html.match(/function makeChecker\(\)[\s\S]*?\n\}/);
const iife = html.match(/const texCanvas = \(function \(\) \{[\s\S]*?\}\)\(\);/);
if (fn) { body = fn[0]; name = 'makeChecker'; }
else if (iife) { body = iife[0]; name = 'texCanvas'; }
else { console.error('没找到贴图生成代码'); process.exit(1); }

function parseColor(s) {
  let r = s.match(/^hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)$/);
  if (r) {
    const h = +r[1] / 360, sat = +r[2] / 100, l = +r[3] / 100;
    const q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat, p = 2 * l - q;
    const f = t => { t = t < 0 ? t + 1 : t > 1 ? t - 1 : t;
      return t < 1/6 ? p + (q - p) * 6 * t : t < 1/2 ? q : t < 2/3 ? p + (q - p) * (2/3 - t) * 6 : p; };
    return [f(h + 1/3) * 255, f(h) * 255, f(h - 1/3) * 255, 1];
  }
  r = s.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/);
  if (r) return [+r[1], +r[2], +r[3], r[4] === undefined ? 1 : +r[4]];
  throw new Error('未支持的颜色: ' + s);
}

function makeCanvas() {
  const buf = new Float64Array(TEXN * TEXN * 3);
  const ctx = {
    fillStyle: '#fff', strokeStyle: '#000', lineWidth: 1, font: '', textAlign: '', textBaseline: '',
    fillRect(x, y, w, h) {
      const [r, g, b, a] = parseColor(this.fillStyle);
      const x0 = Math.max(0, Math.round(x)), y0 = Math.max(0, Math.round(y));
      const x1 = Math.min(TEXN, Math.round(x + w)), y1 = Math.min(TEXN, Math.round(y + h));
      for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx < x1; xx++) {
        const i = (yy * TEXN + xx) * 3;
        buf[i] = buf[i] * (1 - a) + r * a;
        buf[i + 1] = buf[i + 1] * (1 - a) + g * a;
        buf[i + 2] = buf[i + 2] * (1 - a) + b * a;
      }
    },
    fillText() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, strokeRect() {},
    arc() {}, fill() {}, save() {}, restore() {}, clip() {}, transform() {}, drawImage() {},
  };
  return { width: TEXN, height: TEXN, getContext: () => ctx, __buf: buf };
}

const sandbox = { document: { createElement: () => makeCanvas() }, __out: null };
vm.createContext(sandbox);
vm.runInContext(`const TEXN = ${TEXN};\n` + body +
                (name === 'makeChecker' ? '\n;__out = makeChecker();' : '\n;__out = texCanvas;'),
                sandbox);
const buf = sandbox.__out.__buf;

const px = Buffer.alloc(TEXN * TEXN * 3);
for (let i = 0; i < px.length; i++) px[i] = Math.max(0, Math.min(255, Math.round(buf[i])));
fs.writeFileSync(process.argv[3],
  Buffer.concat([Buffer.from(`P6\n${TEXN} ${TEXN}\n255\n`, 'ascii'), px]));
console.log(`已写出 ${path.basename(process.argv[3])} ← ${path.basename(process.argv[2])} 的 ${name}()，${TEXN}×${TEXN}`);
