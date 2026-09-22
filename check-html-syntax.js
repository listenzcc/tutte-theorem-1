/* 语法检查：把 HTML 里每个 <script> 块抽出来交给 node 编译（只编译、不执行），
   用来在没有浏览器的环境里抓住改动引入的语法错误。
   用法：node check-html-syntax.js <a.html> [b.html ...] */
const fs = require('fs');
const vm = require('vm');

let bad = 0;
for (const file of process.argv.slice(2)) {
  const html = fs.readFileSync(file, 'utf8');
  const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)];
  if (!blocks.length) { console.log(`${file}: 没找到内联 script`); continue; }
  let ok = 0, errs = [];
  blocks.forEach((b, i) => {
    const tag = `${file}#script${i + 1}`;
    try {
      new vm.Script(b[1], { filename: tag });   // 仅编译，不运行
      ok++;
    } catch (e) {
      errs.push(`${tag}: ${e.message}`);
    }
  });
  console.log(`${file}: ${ok}/${blocks.length} 个 script 块语法通过` +
    (errs.length ? '\n   ' + errs.join('\n   ') : ''));
  bad += errs.length;
}
process.exit(bad ? 1 : 0);
