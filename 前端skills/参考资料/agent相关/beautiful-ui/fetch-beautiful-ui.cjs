// 把 beautifului.dev（MIT, Shane Levine）20 个组件的源码抓到本地。
// 站是 Next.js，源码在懒加载 chunk 里 curl 拿不到；但页面每个组件区块有 "Copy code" 按钮，
// 点一下源码就进剪贴板——用 Playwright 点 + 读剪贴板，最稳。
// 用法：node fetch.cjs <输出目录>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const out = process.argv[2];
if (!out) { console.error('usage: node fetch.cjs <outdir>'); process.exit(1); }
fs.mkdirSync(out, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await ctx.newPage();
  await page.goto('https://www.beautifului.dev/', { waitUntil: 'networkidle', timeout: 90000 });

  // 每个组件区块：section[id] 里含 Copy code 按钮
  const blocks = await page.evaluate(() => {
    const res = [];
    for (const sec of document.querySelectorAll('section[id]')) {
      const btn = sec.querySelector('button[aria-label="Copy code"]');
      if (!btn) continue;
      const h = sec.querySelector('h1,h2,h3');
      const p = sec.querySelector('p');
      res.push({ id: sec.id, title: h ? h.textContent.trim() : sec.id, caption: p ? p.textContent.trim() : '' });
    }
    return res;
  });
  console.log('blocks:', blocks.length);

  const index = [];
  for (const b of blocks) {
    const btn = page.locator(`section#${b.id} button[aria-label="Copy code"]`).first();
    await btn.scrollIntoViewIfNeeded();
    await page.evaluate(() => navigator.clipboard.writeText(''));
    await btn.click();
    await page.waitForTimeout(400);
    const code = await page.evaluate(() => navigator.clipboard.readText());
    if (!code || code.length < 200) { console.log('  !! empty:', b.id); continue; }
    // 文件名取源码里的组件名；没有就用 id
    const m = code.match(/export (?:default )?function ([A-Z][A-Za-z0-9]*)/) || code.match(/export const ([A-Z][A-Za-z0-9]*)/);
    const name = m ? m[1] : b.id;
    const file = `${name}.tsx`;
    fs.writeFileSync(path.join(out, file), code, 'utf8');
    const deps = [...code.matchAll(/from ["']([^"'.][^"']*)["']/g)].map(x => x[1]).filter((v, i, a) => a.indexOf(v) === i);
    index.push({ id: b.id, title: b.title, caption: b.caption, file, lines: code.split('\n').length, deps });
    console.log('  ok', b.id, '->', file, code.length, 'chars', 'deps:', deps.join(','));
  }
  fs.writeFileSync(path.join(out, '_index.json'), JSON.stringify(index, null, 2), 'utf8');
  await browser.close();
})();
