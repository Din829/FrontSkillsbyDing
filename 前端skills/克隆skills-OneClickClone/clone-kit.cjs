#!/usr/bin/env node
/**
 * clone-kit.cjs — site-clone 通用提取工具（无 MCP，纯 Playwright）
 *
 * 定位：脚本只管「提取真相」，判断（区块怎么拆、组件怎么写、哪张图叫什么名）留给人/AI。
 * 跨平台：只依赖 node + playwright。路径全相对 cwd 推导，零写死。Windows 中文路径坑内置规避。
 *
 * 用法：
 *   node clone-kit.cjs <command> <url> [options]
 *
 * 命令：
 *   probe   <url>                 进站+cookie+滚动懒加载+顶层结构+首屏/全页截图
 *   dump    <url> [--selector S]  区块 DOM树+computed CSS 深抽（不传 selector 用内置猜测）
 *   assets  <url>                 全量资产发现 → asset-manifest.json（候选表，待人确认）
 *   fetch   <url> --manifest F    按 manifest 下载资产（Node fetch + Referer）
 *   measure <url> (--selector S | --text T)   实测单元素真实样式（回查用）
 *   shot    <url> [--out F]       截任意 URL（克隆站对比用）
 *
 * 通用选项：
 *   --vw <n>        视口宽，默认 1440（多视口：--vw 768 / --vw 390）
 *   --vh <n>        视口高，默认 900
 *   --out <dir|file> 覆盖默认输出位置
 *   --outdir <dir>  覆盖输出根目录（默认 _clone-<hostname>/）
 *   --locale <s>    语言，默认 ja-JP
 *   --headed        有头模式（调试时看浏览器）
 *   --no-consent    不自动点 cookie 同意
 *   --wait <ms>     进站后额外等待，默认 2500
 *   --timeout <ms>  导航超时，默认 60000
 *   --depth <n>     dump 的 DOM 递归深度，默认 5
 */

const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

// ---------- 参数解析（极简，不引依赖） ----------
function parseArgs(argv) {
  const [command, url] = [argv[0], argv[1]];
  const opts = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) { opts[key] = true; }      // 布尔旗标
      else { opts[key] = next; i++; }
    }
  }
  return { command, url, opts };
}

// ---------- 通用：输出根目录按 hostname 分（多站并存不打架） ----------
function outRoot(url, opts) {
  if (opts.outdir) return path.resolve(process.cwd(), opts.outdir);
  let host = 'site';
  try { host = new URL(url).hostname.replace(/^www\./, ''); } catch {}
  return path.resolve(process.cwd(), `_clone-${host}`);
}
function ensureDir(d) { fs.mkdirSync(d, { recursive: true }); return d; }

// ---------- Windows 中文路径坑：截图先写系统临时目录，再搬到目标 ----------
// 实测：Chrome headless 直接写 png 到中文目录会权限拒(0x5)。先写英文临时名再 copy 绕开。
async function safeScreenshot(page, destPath, screenshotOpts) {
  ensureDir(path.dirname(destPath));
  const tmp = path.join(os.tmpdir(), `ck-shot-${process.pid}-${Math.abs(hashStr(destPath))}.png`);
  await page.screenshot({ ...screenshotOpts, path: tmp });
  fs.copyFileSync(tmp, destPath);
  fs.unlinkSync(tmp);
  return destPath;
}
// 用路径串生成稳定后缀，避免依赖 Date.now/random（不同调用不撞名即可）
function hashStr(s) { let h = 0; for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) | 0; } return h; }

// ---------- 通用：起浏览器、进站、点 cookie、滚动触发懒加载 ----------
async function openPage(url, opts) {
  const vw = parseInt(opts.vw) || 1440;
  const vh = parseInt(opts.vh) || 900;
  const browser = await chromium.launch({ headless: !opts.headed });
  const ctx = await browser.newContext({ viewport: { width: vw, height: vh }, locale: opts.locale || 'ja-JP' });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: parseInt(opts.timeout) || 60000 });
  await page.waitForTimeout(parseInt(opts.wait) || 2500);

  if (!opts['no-consent']) await dismissConsent(page);
  await scrollToLazyLoad(page);
  return { browser, ctx, page, vw, vh };
}

// 常见 cookie 同意（OneTrust / TrustArc / 通用 Accept），命中即点
async function dismissConsent(page) {
  const sels = [
    '#onetrust-accept-btn-handler',
    'button#truste-consent-button',
    '#truste-consent-button',
    'button[aria-label*="Accept" i]',
    'button[title*="Accept" i]',
    '[id*="cookie"] button[class*="accept" i]',
  ];
  for (const sel of sels) {
    try {
      const btn = await page.$(sel);
      if (btn && await btn.isVisible()) { await btn.click(); await page.waitForTimeout(500); return sel; }
    } catch {}
  }
  return null;
}

async function scrollToLazyLoad(page) {
  await page.evaluate(async () => {
    const h = document.body.scrollHeight;
    const step = window.innerHeight / 2;
    for (let y = 0; y < h; y += step) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); }
    window.scrollTo(0, 0);
    await new Promise(r => setTimeout(r, 400));
  });
}

// ---------- computed CSS 提取：PROPS 清单 + grab/walk（注入浏览器） ----------
const PROPS = [
  'fontSize','fontWeight','fontFamily','lineHeight','letterSpacing','color','textTransform','textAlign','textDecoration',
  'backgroundColor','background','backgroundImage','backgroundSize','backgroundPosition',
  'padding','paddingTop','paddingRight','paddingBottom','paddingLeft','margin','marginTop','marginBottom','marginLeft','marginRight',
  'width','height','maxWidth','minWidth','maxHeight','minHeight','display','flexDirection','justifyContent','alignItems','flexWrap','gap','rowGap','columnGap',
  'gridTemplateColumns','gridTemplateRows','borderRadius','border','borderTop','borderBottom','borderLeft','borderRight','borderColor','borderWidth','borderStyle',
  'boxShadow','textShadow','position','top','right','bottom','left','zIndex','opacity','transform','transformOrigin','transition',
  'objectFit','objectPosition','aspectRatio','overflow','overflowX','overflowY','whiteSpace','clipPath','filter','backdropFilter','mixBlendMode','cursor',
];

// 把 grab/walk 作为字符串注入页面（避免序列化函数的坑）
function injectExtractors() {
  return `
    window.__PROPS = ${JSON.stringify(PROPS)};
    window.__grab = function(el, pseudo){
      const cs = pseudo ? getComputedStyle(el, pseudo) : getComputedStyle(el);
      const r = {};
      window.__PROPS.forEach(p => { const v = cs[p];
        if (v && v!=='none' && v!=='normal' && v!=='auto' && v!=='0px' && v!=='rgba(0, 0, 0, 0)' && v!=='start' && v!=='0s') r[p]=v; });
      return r;
    };
    window.__walk = function(el, depth, maxDepth){
      if (!el || depth > maxDepth) return null;
      const kids = [...el.children];
      const rect = el.getBoundingClientRect();
      const node = {
        tag: el.tagName.toLowerCase(),
        id: el.id || undefined,
        cls: (el.className && el.className.toString ? el.className.toString().split(' ').filter(Boolean).slice(0,6) : undefined),
        rect: { x: Math.round(rect.left), y: Math.round(rect.top+window.scrollY), w: Math.round(rect.width), h: Math.round(rect.height) },
        text: (el.childNodes.length===1 && el.childNodes[0].nodeType===3) ? el.textContent.trim().slice(0,300) : undefined,
        styles: window.__grab(el),
        href: el.tagName==='A' ? el.getAttribute('href') : undefined,
        img: el.tagName==='IMG' ? { src: el.currentSrc||el.src, srcset: el.srcset||undefined, alt: el.alt, nw: el.naturalWidth, nh: el.naturalHeight } : undefined,
        svg: (el.tagName==='svg'||el.tagName==='SVG') ? { viewBox: el.getAttribute('viewBox'), outerHTML: el.outerHTML.slice(0,4000) } : undefined,
        children: kids.length ? kids.slice(0,40).map(c => window.__walk(c, depth+1, maxDepth)).filter(Boolean) : undefined,
      };
      const bBg = getComputedStyle(el,'::before').backgroundImage, bC = getComputedStyle(el,'::before').content;
      const aBg = getComputedStyle(el,'::after').backgroundImage, aC = getComputedStyle(el,'::after').content;
      if ((bBg&&bBg!=='none')||(bC&&bC!=='none'&&bC!=='""')) node['::before']=window.__grab(el,'::before');
      if ((aBg&&aBg!=='none')||(aC&&aC!=='none'&&aC!=='""')) node['::after']=window.__grab(el,'::after');
      return node;
    };
  `;
}

// ====================================================================
// 命令实现
// ====================================================================

async function cmdProbe(url, opts) {
  const root = ensureDir(outRoot(url, opts));
  const art = ensureDir(path.join(root, 'artifacts'));
  const shots = ensureDir(path.join(root, 'shots'));
  const { browser, page, vw } = await openPage(url, opts);

  const topo = await page.evaluate(() => {
    const brief = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      return { tag: el.tagName.toLowerCase(), id: el.id||null,
        cls: (el.className&&el.className.toString?el.className.toString().split(' ').filter(Boolean).slice(0,4):[]),
        y: Math.round(r.top+window.scrollY), h: Math.round(r.height), w: Math.round(r.width),
        pos: cs.position, bg: cs.backgroundColor, text: (el.innerText||'').trim().slice(0,80).replace(/\n/g,' / '), childCount: el.children.length }; };
    const main = document.querySelector('main') || document.body;
    return {
      title: document.title, lang: document.documentElement.lang,
      bodyChildren: [...document.body.children].map(el => el.tagName.toLowerCase()+(el.id?'#'+el.id:'')),
      hasMain: !!document.querySelector('main'),
      mainSections: [...main.querySelectorAll(':scope > *')].map(brief),
      h1: [...document.querySelectorAll('h1')].map(h=>h.innerText.trim()),
      h2: [...document.querySelectorAll('h2')].map(h=>h.innerText.trim()).slice(0,30),
      navItems: [...document.querySelectorAll('header a, nav a')].map(a=>a.innerText.trim()).filter(Boolean).slice(0,40),
      imgCount: document.querySelectorAll('img').length, svgCount: document.querySelectorAll('svg').length,
      pageHeight: document.body.scrollHeight,
    };
  });
  fs.writeFileSync(path.join(art, 'topology.json'), JSON.stringify(topo, null, 2));
  await safeScreenshot(page, path.join(shots, `viewport-${vw}.png`), { fullPage: false });
  await safeScreenshot(page, path.join(shots, `full-${vw}.png`), { fullPage: true });

  console.log(`[probe] ${topo.title} | lang=${topo.lang} | pageH=${topo.pageHeight} | imgs=${topo.imgCount} svgs=${topo.svgCount}`);
  console.log(`[probe] H1: ${JSON.stringify(topo.h1)}`);
  console.log(`[probe] → ${path.join(art,'topology.json')} + shots/viewport-${vw}.png, full-${vw}.png`);
  await browser.close();
}

async function cmdDump(url, opts) {
  const root = ensureDir(outRoot(url, opts));
  const art = ensureDir(path.join(root, 'artifacts'));
  const depth = parseInt(opts.depth) || 5;
  const { browser, page } = await openPage(url, opts);
  await page.addScriptTag({ content: injectExtractors() });

  // 不传 selector → 内置猜测 header / hero(含h1的块) / footer；传了就只 dump 那一个
  const targets = opts.selector
    ? [{ name: sanitize(opts.selector), sel: opts.selector }]
    : null;

  const result = await page.evaluate(({ targets, depth }) => {
    const out = {};
    if (targets) {
      for (const t of targets) { const el = document.querySelector(t.sel); out[t.name] = el ? window.__walk(el, 0, depth) : { error: 'not found: '+t.sel }; }
    } else {
      const header = document.querySelector('header') || document.querySelector('[class*="header"]');
      if (header) out.header = window.__walk(header, 0, Math.min(depth,4));
      const h1 = document.querySelector('h1');
      let hero = h1; for (let i=0;i<5&&hero;i++){ if (hero.getBoundingClientRect().height>200) break; hero = hero.parentElement; }
      if (hero) out.hero = window.__walk(hero, 0, depth);
      const footer = document.querySelector('footer') || document.querySelector('[class*="footer"]');
      if (footer) out.footer = window.__walk(footer, 0, Math.min(depth,4));
    }
    return out;
  }, { targets, depth });

  const names = Object.keys(result);
  for (const name of names) fs.writeFileSync(path.join(art, `section-${name}.json`), JSON.stringify(result[name], null, 2));
  console.log(`[dump] sections: ${names.join(', ')} → ${art}\\section-*.json`);
  await browser.close();
}

async function cmdAssets(url, opts) {
  const root = ensureDir(outRoot(url, opts));
  const art = ensureDir(path.join(root, 'artifacts'));
  const { browser, page } = await openPage(url, opts);

  const assets = await page.evaluate(() => {
    const abs = u => { try { return new URL(u, location.href).href; } catch { return u; } };
    return {
      images: [...document.querySelectorAll('img')].map(img => ({ src: abs(img.currentSrc||img.src), srcset: img.srcset||null, alt: img.alt, w: img.naturalWidth, h: img.naturalHeight, loading: img.loading })),
      backgroundImages: [...document.querySelectorAll('*')].filter(el=>{const b=getComputedStyle(el).backgroundImage;return b&&b!=='none'&&b.includes('url');}).map(el=>({ url: getComputedStyle(el).backgroundImage, el: el.tagName+(el.className&&el.className.toString?'.'+el.className.toString().split(' ').filter(Boolean)[0]:'') })),
      videos: [...document.querySelectorAll('video')].map(v=>({ src: v.src||v.querySelector('source')?.src, poster: v.poster, autoplay: v.autoplay, loop: v.loop, muted: v.muted })),
      svgs: [...document.querySelectorAll('svg')].map((s,i)=>({ index:i, viewBox:s.getAttribute('viewBox'), cls:s.getAttribute('class'), aria:s.getAttribute('aria-label'), outerHTML: s.outerHTML.slice(0,4000) })),
      fonts: { body: getComputedStyle(document.body).fontFamily, h1: document.querySelector('h1')?getComputedStyle(document.querySelector('h1')).fontFamily:null,
        fontLinks: [...document.querySelectorAll('link[href*="font" i]')].map(l=>l.href) },
      favicons: [...document.querySelectorAll('link[rel*="icon" i],link[rel="apple-touch-icon"],link[rel="manifest"]')].map(l=>({ rel:l.rel, href:l.href, sizes:l.sizes?.toString(), type:l.type })),
      meta: { title: document.title, desc: document.querySelector('meta[name="description"]')?.content,
        ogImage: document.querySelector('meta[property="og:image"]')?.content, themeColor: document.querySelector('meta[name="theme-color"]')?.content },
    };
  });
  fs.writeFileSync(path.join(art, 'assets-raw.json'), JSON.stringify(assets, null, 2));

  // 生成下载候选 manifest（人改名/删垃圾后喂给 fetch）。过滤 1x1 像素追踪 gif。
  const manifest = { referer: url, items: [] };
  assets.images.filter(im => !(im.w===1 && im.h===1)).forEach((im,i) => {
    const guessName = nameFromUrl(im.src) || `image-${i}`;
    manifest.items.push({ url: im.src, name: guessName, kind: 'image', alt: im.alt, size: `${im.w}x${im.h}` });
  });
  assets.videos.forEach((v,i)=>{ if (v.src) manifest.items.push({ url: abs2(v.src,url), name: nameFromUrl(v.src)||`video-${i}`, kind:'video' }); });
  (assets.favicons||[]).filter(f=>/32x32|favicon\.ico/i.test(f.href||'')).slice(0,1).forEach(f=>manifest.items.push({ url:f.href, name:'favicon-32x32.png', kind:'favicon' }));
  fs.writeFileSync(path.join(art, 'asset-manifest.json'), JSON.stringify(manifest, null, 2));

  console.log(`[assets] imgs=${assets.images.length} bg=${assets.backgroundImages.length} video=${assets.videos.length} svg=${assets.svgs.length}`);
  console.log(`[assets] fonts.body=${assets.fonts.body} | fonts.h1=${assets.fonts.h1}`);
  console.log(`[assets] → assets-raw.json (全量) + asset-manifest.json (${manifest.items.length} 项候选，改名/删垃圾后用 fetch 下载)`);
  await browser.close();
}

async function cmdFetch(url, opts) {
  const root = outRoot(url, opts);
  const manifestPath = opts.manifest ? path.resolve(process.cwd(), opts.manifest) : path.join(root, 'artifacts', 'asset-manifest.json');
  if (!fs.existsSync(manifestPath)) { console.error(`[fetch] manifest 不存在: ${manifestPath}（先跑 assets 命令生成）`); process.exit(1); }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const outDir = ensureDir(path.resolve(process.cwd(), opts.out || path.join(root, 'public', 'images')));
  const referer = manifest.referer || url;

  const results = [];
  const used = new Set();
  for (const it of manifest.items) {
    // 同名加序号，防止 manifest 里重名项静默覆盖（人工去重前的保险）
    let name = it.name;
    if (used.has(name)) { const ext = path.extname(name), base = name.slice(0, name.length-ext.length);
      let n = 2; while (used.has(`${base}-${n}${ext}`)) n++; name = `${base}-${n}${ext}`; }
    used.add(name);
    const dest = path.join(outDir, name);
    try {
      const res = await fetch(it.url, { headers: { Referer: referer, 'User-Agent': 'Mozilla/5.0' } });
      if (!res.ok) { results.push(`✗ ${name}: HTTP ${res.status}`); continue; }
      const buf = Buffer.from(await res.arrayBuffer());
      fs.writeFileSync(dest, buf);
      results.push(`✓ ${name}: ${(buf.length/1024).toFixed(0)} KB`);
    } catch (e) { results.push(`✗ ${name}: ${e.message}`); }
  }
  console.log(results.join('\n'));
  const fails = results.filter(r => r.startsWith('✗'));
  console.log(fails.length ? `\n[fetch] !! ${fails.length}/${manifest.items.length} 失败 → ${outDir}` : `\n[fetch] 全部 OK (${manifest.items.length}) → ${outDir}`);
}

async function cmdMeasure(url, opts) {
  if (!opts.selector && !opts.text) { console.error('[measure] 需要 --selector S 或 --text T'); process.exit(1); }
  const root = ensureDir(outRoot(url, opts));
  const art = ensureDir(path.join(root, 'artifacts'));
  const { browser, page } = await openPage(url, opts);
  await page.addScriptTag({ content: injectExtractors() });

  const data = await page.evaluate(({ selector, text }) => {
    let el = null;
    if (selector) el = document.querySelector(selector);
    else { el = [...document.querySelectorAll('*')].find(e => e.children.length===0 && e.textContent.trim() === text)
                || [...document.querySelectorAll('*')].find(e => e.textContent.includes(text)); }
    if (!el) return { error: 'not found' };
    const r = el.getBoundingClientRect();
    const out = { tag: el.tagName, text: el.textContent.trim().slice(0,80),
      rect: { w: Math.round(r.width), h: Math.round(r.height) }, styles: window.__grab(el) };
    // ::before/::after 只在真有装饰（content 非空 或 有背景图）时才输出，避免一大坨重复
    for (const pseudo of ['::before','::after']) {
      const cs = getComputedStyle(el, pseudo);
      if ((cs.content && cs.content!=='none' && cs.content!=='""') || (cs.backgroundImage && cs.backgroundImage!=='none'))
        out[pseudo] = window.__grab(el, pseudo);
    }
    return out;
  }, { selector: opts.selector || null, text: opts.text || null });

  const fname = `measure-${sanitize(opts.selector || opts.text)}.json`;
  fs.writeFileSync(path.join(art, fname), JSON.stringify(data, null, 2));
  console.log(JSON.stringify(data, null, 2));
  console.log(`[measure] → ${path.join(art, fname)}`);
  await browser.close();
}

async function cmdShot(url, opts) {
  const root = ensureDir(outRoot(url, opts));
  const shots = ensureDir(path.join(root, 'shots'));
  const { browser, page, vw } = await openPage(url, opts);
  const dest = opts.out ? path.resolve(process.cwd(), opts.out) : path.join(shots, `shot-${vw}.png`);
  await safeScreenshot(page, dest, { fullPage: !opts.viewport });
  const h = await page.evaluate(() => document.body.scrollHeight);
  console.log(`[shot] pageHeight=${h} → ${dest}`);
  await browser.close();
}

// ---------- 小工具 ----------
// 只去掉文件系统非法字符，保留 unicode（日文/中文选择器也能当文件名）
function sanitize(s) { return String(s).replace(/[\\/:*?"<>|\s]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'el'; }
function nameFromUrl(u) {
  try {
    const p = new URL(u).pathname;
    let base = p.split('/').filter(Boolean).pop() || '';
    base = base.split(':')[0]; // 去掉 AEM 的 :cq5dam... 后缀
    if (!/\.[a-z0-9]{2,5}$/i.test(base)) base += guessExt(u);
    return base.replace(/[^a-zA-Z0-9._-]+/g, '-');
  } catch { return null; }
}
function guessExt(u) { if (/\.svg/i.test(u)) return '.svg'; if (/\.png/i.test(u)) return '.png'; if (/\.webp/i.test(u)) return '.webp'; if (/\.mp4/i.test(u)) return '.mp4'; return '.jpg'; }
function abs2(u, base) { try { return new URL(u, base).href; } catch { return u; } }

// ====================================================================
// 入口
// ====================================================================
const COMMANDS = { probe: cmdProbe, dump: cmdDump, assets: cmdAssets, fetch: cmdFetch, measure: cmdMeasure, shot: cmdShot };

(async () => {
  const { command, url, opts } = parseArgs(process.argv.slice(2));
  if (!command || !COMMANDS[command]) {
    console.log('用法: node clone-kit.cjs <probe|dump|assets|fetch|measure|shot> <url> [options]');
    console.log('详见文件头注释或 clone-kit用法.md');
    process.exit(command ? 1 : 0);
  }
  if (!url) { console.error(`[${command}] 需要 url`); process.exit(1); }
  try { await COMMANDS[command](url, opts); }
  catch (e) { console.error(`[${command}] FAIL: ${e.message}`); if (opts.debug) console.error(e.stack); process.exit(1); }
})();
