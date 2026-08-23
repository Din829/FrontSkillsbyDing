#!/usr/bin/env node
/**
 * extract-from-code.cjs — 从「代码」提取设计 token 候选（不起浏览器，纯静态解析）。
 * extract-tokens.cjs 的姊妹：那个吃 live URL（computed 值），这个吃源码（声明值）。
 *
 * 吃 HTML / CSS / JSX / Tailwind class 的文件或目录，正则扒出 color/font-size/
 * spacing/radius/shadow 声明 + 频次，输出与 extract-tokens 同格式的 tokens.source.json，
 * 后续归类步骤（AI 指令模板）两条输入路径共用。
 *
 * 用法:
 *   node extract-from-code.cjs <file-or-dir> [--outdir DIR] [--name NAME]
 * 例:
 *   node extract-from-code.cjs ./src/components --outdir _ds-test/myapp --name myapp
 *
 * 局限（诚实标注）：拿到的是源码声明值，不是浏览器最终 computed 值。
 *   - CSS 变量/继承/媒体查询不解析（var(--x) 原样记录，由 AI 判断）
 *   - 准确性不如 URL 路径；适合「有组件代码、想抽 token」的场景
 */
const fs = require('fs');
const path = require('path');

function parseArgs(a){ const target=a[0]; const o={}; for(let i=1;i<a.length;i++){const x=a[i];if(x.startsWith('--')){const k=x.slice(2);const n=a[i+1];if(n===undefined||n.startsWith('--'))o[k]=true;else{o[k]=n;i++;}}} return {target,o}; }

// 递归收集源码文件
const EXT = new Set(['.css','.scss','.less','.html','.htm','.jsx','.tsx','.js','.ts','.vue','.svelte']);
function collectFiles(p) {
  const st = fs.statSync(p);
  if (st.isFile()) return EXT.has(path.extname(p).toLowerCase()) ? [p] : [];
  let out = [];
  for (const name of fs.readdirSync(p)) {
    if (name === 'node_modules' || name.startsWith('.')) continue;
    out = out.concat(collectFiles(path.join(p, name)));
  }
  return out;
}

const bump = (m, k) => { if (k) m[k] = (m[k]||0) + 1; };
const topN = (m, n) => Object.entries(m).sort((a,b)=>b[1]-a[1]).slice(0,n).map(([value,count])=>({value,count}));

// 颜色：hex / rgb / hsl / oklch / 具名（具名只收常见的）
const RE_HEX = /#[0-9a-fA-F]{3,8}\b/g;
const RE_FUNC_COLOR = /\b(?:rgba?|hsla?|oklch|oklab|color-mix)\([^)]*\)/g;
// 字号 / 间距 / 圆角：带单位的数值（紧跟在相关属性后，尽量减噪）
const RE_FONTSIZE = /font-size\s*:\s*([0-9.]+(?:px|rem|em))/g;
const RE_RADIUS = /border-radius\s*:\s*([0-9.]+(?:px|rem|em|%)|9999px)/g;
const RE_SPACE = /(?:padding|margin|gap)(?:-(?:top|right|bottom|left))?\s*:\s*([0-9.]+(?:px|rem))/g;
const RE_SHADOW = /box-shadow\s*:\s*([^;}\n]+)/g;
const RE_FONTFAMILY = /font-family\s*:\s*([^;}\n]+)/g;
// Tailwind 常见 token class
const RE_TW = /\b(?:bg|text|border|rounded|p|px|py|m|mx|my|gap|shadow|font|leading|tracking)-[a-z0-9.\[\]#/-]+/g;

function extractAll(re, text, capture) {
  const out = []; let m;
  while ((m = re.exec(text)) !== null) out.push(capture ? m[1] : m[0]);
  return out;
}

(async () => {
  const { target, o } = parseArgs(process.argv.slice(2));
  if (!target) { console.error('需要 file 或 dir'); process.exit(1); }
  const abs = path.resolve(process.cwd(), target);
  if (!fs.existsSync(abs)) { console.error('路径不存在:', abs); process.exit(1); }

  const files = collectFiles(abs);
  if (!files.length) { console.error('没找到可解析的源码文件'); process.exit(1); }

  const colors={}, fontSizes={}, radii={}, spaces={}, shadows={}, fontFamilies={}, twClasses={};
  for (const f of files) {
    let text; try { text = fs.readFileSync(f, 'utf8'); } catch { continue; }
    [...extractAll(RE_HEX, text), ...extractAll(RE_FUNC_COLOR, text)].forEach(c => bump(colors, c.toLowerCase().replace(/\s+/g,' ')));
    extractAll(RE_FONTSIZE, text, true).forEach(v => bump(fontSizes, v));
    extractAll(RE_RADIUS, text, true).forEach(v => bump(radii, v));
    extractAll(RE_SPACE, text, true).forEach(v => bump(spaces, v));
    extractAll(RE_SHADOW, text, true).forEach(v => bump(shadows, v.trim().slice(0,80)));
    extractAll(RE_FONTFAMILY, text, true).forEach(v => bump(fontFamilies, v.trim().slice(0,80)));
    extractAll(RE_TW, text).forEach(v => bump(twClasses, v));
    // Tailwind 任意值（text-[18px] / bg-[#hex] / rounded-[3px]）顺手归并进对应桶；
    // preset class（rounded-lg 等）不解析尺度，留给 AI 读 tailwindClasses 判断。
    extractAll(/\btext-\[([0-9.]+(?:px|rem|em))\]/g, text, true).forEach(v => bump(fontSizes, v));
    extractAll(/\brounded(?:-[a-z]+)?-\[([0-9.]+(?:px|rem|%))\]/g, text, true).forEach(v => bump(radii, v));
    extractAll(/\b(?:bg|text|border)-\[(#[0-9a-fA-F]{3,8})\]/g, text, true).forEach(v => bump(colors, v.toLowerCase()));
    extractAll(/\b(?:p|px|py|m|mx|my|gap)-\[([0-9.]+(?:px|rem))\]/g, text, true).forEach(v => bump(spaces, v));
  }

  const data = {
    // 颜色无 computed 面积信息 → 只能给频次，accent/surface 判断更依赖 AI
    colorsByFreq: topN(colors, 16),
    fontFamilies: topN(fontFamilies, 6),
    fontSizes: topN(fontSizes, 12),
    spacing: topN(spaces, 12),
    radii: topN(radii, 8),
    shadows: topN(shadows, 6),
    tailwindClasses: topN(twClasses, 30),
    _meta: {
      source: 'code', inputPath: abs, filesScanned: files.length,
      note: '源码声明值（非浏览器 computed）。颜色无面积信息——accent/surface 角色需 AI 从用途+频次判断。'
        + ' var(--x) 原样保留。Tailwind class 已收集，可反推用了哪些设计 token。'
        + ' 归类到 token schema 见 extract-design-system.md。',
    },
  };

  const name = o.name || path.basename(abs).replace(/[^a-z0-9-]/gi,'-').toLowerCase() || 'app';
  const outdir = path.resolve(process.cwd(), o.outdir || `_clone-${name}/artifacts`);
  fs.mkdirSync(outdir, { recursive: true });
  fs.writeFileSync(path.join(outdir, 'tokens.source.json'), JSON.stringify(data, null, 2));

  console.log(`[code] 扫描 ${files.length} 文件 → ${path.join(outdir,'tokens.source.json')}`);
  console.log(`  颜色: ${data.colorsByFreq.slice(0,4).map(x=>x.value).join(', ')}`);
  console.log(`  字号: ${data.fontSizes.slice(0,5).map(x=>x.value).join(', ')} | 圆角: ${data.radii.slice(0,4).map(x=>x.value).join(', ')}`);
  console.log(`  字体: ${data.fontFamilies[0]?.value || '-'}`);
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
