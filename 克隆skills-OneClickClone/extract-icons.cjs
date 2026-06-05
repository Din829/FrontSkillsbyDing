#!/usr/bin/env node
/**
 * extract-icons.cjs — 从真站全抽图标 + 识别来源。
 * 覆盖三种真实形态：① 内联 <svg> 直拔 ② svg 当 <img> 下载文件
 * ③ 字体图标（Material/FontAwesome/MDI…）识别是哪套库 + 收集用了哪些名。
 *
 * 用法: node extract-icons.cjs <url> [--outdir DIR] [--download] [--locale ja-JP]
 *   --download  下载 svg-as-img 的真实文件到 assets/icons/
 * 产出:
 *   artifacts/icons.json   —— 全部图标清单（含字体图标库识别）
 *   assets/icons/*.svg     —— 内联 svg 存文件 + (--download) 下载的 svg-img
 *
 * 识别特征来源（查证，非记忆）：
 *   Material Icons: class~="material-icons"；Material Symbols: "material-symbols-*"
 *   Font Awesome: "fa|fas|far|fab" + "fa-*"；MDI: "mdi mdi-*"；Bootstrap: "bi bi-*"
 *   Lucide/Feather 通常是内联 svg（走 svg 路径）。
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

function parseArgs(a){ const url=a[0]; const o={}; for(let i=1;i<a.length;i++){const x=a[i];if(x.startsWith('--')){const k=x.slice(2);const n=a[i+1];if(n===undefined||n.startsWith('--'))o[k]=true;else{o[k]=n;i++;}}} return {url,o}; }

(async () => {
  const { url, o } = parseArgs(process.argv.slice(2));
  if (!url) { console.error('需要 url'); process.exit(1); }
  let host='site'; try{host=new URL(url).hostname.replace(/^www\./,'');}catch{}
  const root = path.resolve(process.cwd(), o.outdir || `_clone-${host}`);
  const art = path.join(root, 'artifacts'); const iconsDir = path.join(root, 'assets', 'icons');
  fs.mkdirSync(art, { recursive: true });

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: o.locale||'ja-JP' });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  const cb = await page.$('#onetrust-accept-btn-handler'); if (cb) { await cb.click(); await page.waitForTimeout(500); }
  await page.evaluate(async()=>{const h=document.body.scrollHeight;for(let y=0;y<h;y+=window.innerHeight/2){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,200));}window.scrollTo(0,0);await new Promise(r=>setTimeout(r,300));});

  const result = await page.evaluate(() => {
    // 字体图标库识别表（查证特征）。返回判定函数。
    const FONT_ICON_RULES = [
      { lib: 'Material Symbols', test: c => /\bmaterial-symbols(-\w+)?\b/.test(c) },
      { lib: 'Material Icons',   test: c => /\bmaterial-icons(-\w+)?\b/.test(c) },
      { lib: 'Font Awesome',     test: c => /\bfa[srlbd]?\b/.test(c) && /\bfa-[\w-]+/.test(c) },
      { lib: 'MDI',              test: c => /\bmdi\b/.test(c) && /\bmdi-[\w-]+/.test(c) },
      { lib: 'Bootstrap Icons',  test: c => /\bbi\b/.test(c) && /\bbi-[\w-]+/.test(c) },
      { lib: 'IcoMoon/iconfont', test: c => /\bicon-[\w-]+/.test(c) },
    ];
    const detectLib = c => { for (const r of FONT_ICON_RULES) if (r.test(c)) return r.lib; return null; };

    // ① 内联 svg
    const inlineSvgs = [...document.querySelectorAll('svg')].map((s, i) => {
      const r = s.getBoundingClientRect();
      return {
        index: i, viewBox: s.getAttribute('viewBox'), ariaLabel: s.getAttribute('aria-label') || s.querySelector('title')?.textContent || null,
        cls: s.getAttribute('class') || null, w: Math.round(r.width), h: Math.round(r.height),
        pathCount: s.querySelectorAll('path,circle,rect,line,polygon,polyline').length,
        outerHTML: s.outerHTML,
      };
    });

    // ② svg 当 <img>
    const svgImgs = [...document.querySelectorAll('img')].filter(im => /\.svg(\?|$)/i.test(im.currentSrc || im.src || ''))
      .map(im => ({ src: im.currentSrc || im.src, alt: im.alt || null, w: im.naturalWidth, h: im.naturalHeight }));

    // ③ 字体图标：扫所有元素的 class，命中库规则的收集
    const fontIcons = {}; // lib → { count, names:Set→array, sample }
    document.querySelectorAll('*').forEach(el => {
      const c = (el.className && el.className.toString) ? el.className.toString() : '';
      if (!c) return;
      const lib = detectLib(c);
      if (!lib) return;
      if (!fontIcons[lib]) fontIcons[lib] = { count: 0, names: {}, sample: c.slice(0, 60) };
      fontIcons[lib].count++;
      // 图标名：Material 系是 textContent（ligature），其它系在 class 里（fa-home / mdi-home / bi-home）
      let name = null;
      if (/material/i.test(lib)) name = (el.textContent || '').trim().slice(0, 30) || null;
      else { const m = c.match(/\b(?:fa|mdi|bi|icon)-([\w-]+)/); name = m ? m[1] : null; }
      if (name) fontIcons[lib].names[name] = (fontIcons[lib].names[name] || 0) + 1;
    });
    const fontIconSummary = Object.entries(fontIcons).map(([lib, d]) => ({
      lib, count: d.count, sampleClass: d.sample,
      iconNames: Object.entries(d.names).sort((a,b)=>b[1]-a[1]).map(([n])=>n).slice(0, 60),
    }));

    // 交叉验证：<head> 加载的字体/css 里是否有对应库（更稳）
    const headLinks = [...document.querySelectorAll('link[rel="stylesheet"],link[href]')].map(l => l.href)
      .filter(h => /material|fontawesome|font-awesome|materialdesignicons|mdi|bootstrap-icons|icomoon|iconfont/i.test(h));

    return { inlineSvgs, svgImgs, fontIconSummary, headLinks };
  });

  // 存内联 svg 文件（去重：按 outerHTML）
  let savedSvg = 0;
  if (result.inlineSvgs.length) {
    fs.mkdirSync(iconsDir, { recursive: true });
    const seen = new Set();
    result.inlineSvgs.forEach((s, i) => {
      // 跳过明显非图标的大 svg（如背景插画）——viewBox 大且无 aria 的先不存文件，仍留在 json
      if (seen.has(s.outerHTML)) return; seen.add(s.outerHTML);
      const nm = (s.ariaLabel || s.cls || `svg-${i}`).replace(/[^\w-]+/g, '-').slice(0, 30) || `svg-${i}`;
      try { fs.writeFileSync(path.join(iconsDir, `inline-${i}-${nm}.svg`), s.outerHTML); savedSvg++; } catch {}
    });
  }

  // 下载 svg-as-img（仅 --download，边界 IO 做防御）
  let dl = [];
  if (o.download && result.svgImgs.length) {
    fs.mkdirSync(iconsDir, { recursive: true });
    for (const im of result.svgImgs) {
      try {
        const res = await fetch(im.src, { headers: { Referer: url, 'User-Agent': 'Mozilla/5.0' } });
        if (!res.ok) { dl.push(`✗ ${im.src}: HTTP ${res.status}`); continue; }
        const buf = Buffer.from(await res.arrayBuffer());
        const nm = (im.alt || path.basename(new URL(im.src).pathname)).replace(/[^\w.-]+/g, '-').slice(0, 40) || 'icon';
        const fname = nm.endsWith('.svg') ? nm : nm + '.svg';
        fs.writeFileSync(path.join(iconsDir, `img-${fname}`), buf);
        dl.push(`✓ img-${fname}: ${(buf.length/1024).toFixed(1)} KB`);
      } catch (e) { dl.push(`✗ ${im.src}: ${e.message}`); }
    }
  }

  const out = {
    _meta: { url, host, note: '图标全抽：内联svg存文件、svg-img(--download可下)、字体图标识别库+用了哪些名。'
      + ' 字体图标无法当svg复用——产出时用同款库（如装 material-symbols）或换内联svg替代。' },
    inlineSvgCount: result.inlineSvgs.length, inlineSvgSaved: savedSvg,
    svgImgCount: result.svgImgs.length,
    fontIconLibraries: result.fontIconSummary,
    headIconStylesheets: result.headLinks,
    svgImgs: result.svgImgs,
    inlineSvgs: result.inlineSvgs.map(s => ({ index: s.index, viewBox: s.viewBox, ariaLabel: s.ariaLabel, cls: s.cls, w: s.w, h: s.h, pathCount: s.pathCount })),
  };
  fs.writeFileSync(path.join(art, 'icons.json'), JSON.stringify(out, null, 2));

  console.log(`[icons] → ${path.join(art, 'icons.json')}`);
  console.log(`  内联svg: ${out.inlineSvgCount}（存文件 ${savedSvg}） | svg-img: ${out.svgImgCount}${o.download?`（下载 ${dl.filter(x=>x.startsWith('✓')).length}）`:'（未下，加 --download）'}`);
  if (out.fontIconLibraries.length) out.fontIconLibraries.forEach(f => console.log(`  字体图标: ${f.lib} ×${f.count}，用了 ${f.iconNames.length} 个（${f.iconNames.slice(0,6).join(', ')}…）`));
  else console.log('  字体图标: 无');
  if (dl.length) console.log(dl.join('\n'));
  await browser.close();
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
