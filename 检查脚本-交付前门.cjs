#!/usr/bin/env node
/**
 * 交付前门的机械兜底（配 frontend-design-pro.md 第 4.2 节）。
 * 读代码答不了的三条门要真渲染：横向滚动（门 15）、对比度（门 14）、reduced-motion（门 10）。
 * 顺手机械查几条能 grep 的：transition: all、紫蓝渐变、emoji 当图标、focus-visible 有无、通用字体。
 *
 * 用法：node 检查脚本-交付前门.cjs <本地 html 路径 或 http(s) URL> [--widths 320,768,1440]
 * 依赖：npm i playwright（浏览器没下过再 npx playwright install chromium）
 *
 * 过了脚本 ≠ 过了门（对比度是近似算法：往上找第一个不透明背景；渐变/图片背景算不准会标 "?"）。
 * 没过脚本 = 一定没过门。
 */
const path = require('path');
const fs = require('fs');
let chromium;
try { ({ chromium } = require('playwright')); } catch { console.error('先 npm i playwright'); process.exit(1); }

const target = process.argv[2];
if (!target) { console.error('用法：node 检查脚本-交付前门.cjs <html 或 URL> [--widths 320,768,1440]'); process.exit(1); }
const wi = process.argv.indexOf('--widths');
const widths = wi > -1 ? process.argv[wi + 1].split(',').map(Number) : [320, 768, 1440];
const url = /^https?:/.test(target) ? target : 'file:///' + path.resolve(target).replace(/\\/g, '/');

// ---- 静态 grep 门 ----
function staticGates(html) {
  return {
    '门7 transition:all': /transition\s*:\s*all\b/i.test(html),
    '门2 紫蓝渐变': /gradient\([^)]*\)/i.test(html) && /(#7c3aed|#8b5cf6|#a855f7|#6366f1|#6d28d9|violet|purple|indigo)/i.test(html) && /(#3b82f6|#2563eb|#06b6d4|blue|cyan|#0ea5e9)/i.test(html),
    '门19 emoji 当图标': /[✨⚡\u{1F680}\u{1F525}\u{1F3AF}✅\u{1F4A1}\u{1F4C8}\u{1F512}]/u.test(html),
    '门1 通用字体': /font-family[^;"}]*\b(Inter|Roboto|Poppins|Open Sans|Lato)\b/i.test(html),
    '门9 动画布局属性': /transition\s*:[^;"}]*\b(width|height|top|left|margin|padding)\b/i.test(html),
    '门11 无 focus-visible': !/focus-visible/.test(html),
    '门10 无 reduced-motion': !/prefers-reduced-motion/.test(html),
  };
}

// ---- 对比度近似 ----
const inPage = () => {
  // 任意颜色语法（oklch / lab / color() …）都经 canvas 转成 rgb；Chromium 的 computed color 会原样保留 oklch
  const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', { willReadFrequently: true });
  const toRGB = (s) => {
    if (!s || s === 'transparent') return null;
    const m = s.match(/^rgba?\(([^)]+)\)$/);
    if (m) { const p = m[1].split(/[\s,\/]+/).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s; if (cx.fillStyle === '#000000' && !/black|#000/.test(s)) { /* 解析失败仍可能是黑 */ }
    cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
  };
  const lum = ({ r, g, b }) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
  const bgOf = (el) => { let e = el; while (e && e !== document.documentElement) { const cs = getComputedStyle(e); if (cs.backgroundImage !== 'none') return { unknown: true }; const c = toRGB(cs.backgroundColor); if (c && c.a > 0.9) return c; e = e.parentElement; } const c = toRGB(getComputedStyle(document.body).backgroundColor); return c && c.a > 0.9 ? c : { r: 255, g: 255, b: 255, a: 1 }; };
  const fails = []; let checked = 0, unknown = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!el || seen.has(el)) continue; seen.add(el);
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect(); if (r.width === 0 || r.height === 0) continue;
    const fg = toRGB(cs.color); if (!fg) continue;
    const bg = bgOf(el); if (bg.unknown) { unknown++; continue; }
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700;
    const large = size >= 24 || (size >= 18.66 && bold);
    const need = large ? 3 : 4.5; const got = ratio(fg, bg); checked++;
    if (got < need) fails.push({ text: t.textContent.trim().slice(0, 30), ratio: +got.toFixed(2), need, fg: cs.color, bg: `rgb(${bg.r},${bg.g},${bg.b})`, size });
  }
  return { checked, unknown, fails: fails.slice(0, 15), failCount: fails.length };
};

(async () => {
  const browser = await chromium.launch();
  if (!/^https?:/.test(target)) {
    const html = fs.readFileSync(target, 'utf8');
    console.log('== 静态 grep 门（true = 踩了）');
    for (const [k, v] of Object.entries(staticGates(html))) console.log(`  ${v ? '✗' : '·'} ${k}: ${v}`);
  }
  console.log('== 渲染门');
  for (const w of widths) {
    const page = await browser.newPage({ viewport: { width: w, height: 900 } });
    await page.goto(url, { waitUntil: 'load' });
    await page.waitForTimeout(800);
    const hs = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    console.log(`  ${w}px  门15 横向滚动: ${hs ? '✗ 有' : '· 无'}`);
    if (w === widths[widths.length - 1]) {
      const c = await page.evaluate(inPage);
      console.log(`  门14 对比度（近似）：查了 ${c.checked} 处文字，${c.unknown} 处背景是渐变/图片算不了；不达标 ${c.failCount} 处`);
      for (const f of c.fails) console.log(`     ✗ "${f.text}"  ${f.ratio}:1 (要 ${f.need}:1)  ${f.fg} on ${f.bg}  ${f.size}px`);
    }
    // 门10：reduced-motion 下还有没有在跑的动画
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.waitForTimeout(300);
    const running = await page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running').length);
    console.log(`  ${w}px  门10 reduced-motion 下仍在跑的动画: ${running === 0 ? '· 0' : '✗ ' + running}`);
    await page.close();
  }
  await browser.close();
  console.log('\n过了脚本 ≠ 过了门；没过脚本 = 一定没过门。其余 20 条门人工过。');
})();
