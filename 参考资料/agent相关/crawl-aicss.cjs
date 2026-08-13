#!/usr/bin/env node
/**
 * crawl-aicss.cjs — 爬取 aicss.dev 全部组件源码（React/Vue/Svelte 三实现）
 *
 * 用途：aicss.dev 的组件代码无再分发授权，源码目录不入公开仓库（.gitignore 排除）。
 *       换机器后跑本脚本即可再生全部产物。
 *
 * 环境：node + playwright（npm i playwright && npx playwright install chromium）
 * 用法：node crawl-aicss.cjs [--out aicss-dev]
 * 产物：<out>/<组件slug>/<框架>/<文件名>
 *       orbs 特殊：25 个变体逐个爬 → <out>/orbs/<变体>/<框架>/<文件名>
 *       另存 <out>/_meta.json（组件清单+页面描述，索引素材）
 *
 * 原理（2026-08 站点结构，变了按此思路修）：
 *   首页 a[href*="/components/"] 发现组件 → 每页依次点 React/Vue/Svelte 框架 tab
 *   → 每框架下点各"文件名 tab"（带扩展名的按钮）→ 抓 pre.shiki 文本落盘。
 *   orbs 页代码随变体选择器（button.orbCard > span.orbCardName，文本 S1..M5）切换，
 *   页面只给"当前变体裁剪版"代码，故先遍历 25 变体、每变体再走三框架。
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.resolve(process.argv.includes('--out')
  ? process.argv[process.argv.indexOf('--out') + 1] : 'aicss-dev');
const BASE = 'https://www.aicss.dev';
const FRAMEWORKS = ['React', 'Vue', 'Svelte'];
const FILE_RE = /\.(tsx|jsx|ts|js|css|vue|svelte|html)$/;

const sleep = ms => new Promise(r => setTimeout(r, ms));
const failures = [];
let fileCount = 0;

/** 抓当前页面状态下的三框架代码 → outDir/<框架>/<文件名>；文件清单写进 filesObj */
async function grabFrameworks(page, outDir, filesObj) {
  for (const fw of FRAMEWORKS) {
    const fwTab = page.locator(`button:text-is("${fw}")`).first();
    if (!(await fwTab.count())) continue;
    await fwTab.click().catch(() => {});
    await sleep(500);

    const fileTabs = (await page.$$eval('button', els =>
      els.map(e => (e.textContent || '').trim())))
      .filter(t => FILE_RE.test(t) && t.length < 60);
    const uniqTabs = [...new Set(fileTabs)];
    if (!uniqTabs.length) { failures.push(`${outDir}/${fw}: 无文件tab`); continue; }

    filesObj[fw] = [];
    for (const fname of uniqTabs) {
      await page.locator(`button:text-is("${fname}")`).first().click().catch(() => {});
      await sleep(450);
      const code = await page.$eval('pre', e => e.textContent).catch(() => '');
      if (!code || code.length < 20) { failures.push(`${outDir}/${fw}/${fname}: 代码为空`); continue; }
      const dir = path.join(outDir, fw.toLowerCase());
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, fname), code, 'utf8');
      filesObj[fw].push({ name: fname, bytes: Buffer.byteLength(code) });
      fileCount++;
    }
  }
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const meta = { crawledFrom: BASE, components: [] };

  // 1. 发现组件列表
  await page.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 60000 });
  const links = await page.$$eval('a[href*="/components/"]', as =>
    [...new Set(as.map(a => a.getAttribute('href')))]);
  console.log(`发现 ${links.length} 个组件页`);

  // 2. 逐组件爬取
  for (const link of links) {
    const slug = link.split('/').pop();
    await page.goto(BASE + link, { waitUntil: 'networkidle', timeout: 60000 });
    await sleep(1500);

    const title = await page.$eval('h1', e => e.textContent.trim()).catch(() => slug);
    const desc = await page.$eval('h1 ~ p', e => e.textContent.trim()).catch(() => '');
    const comp = { slug, title, desc, files: {} };

    // orbs：页面代码是"当前变体裁剪版"，遍历全部变体
    const variants = await page.$$eval('[class*="orbCardName"]', els =>
      els.map(e => (e.textContent || '').trim()).filter(t => /^[A-Z]\d$/.test(t)))
      .catch(() => []);
    if (variants.length) {
      console.log(`  ${slug}: ${variants.length} 个变体`);
      for (const v of variants) {
        await page.getByText(v, { exact: true }).first().click({ force: true, timeout: 8000 })
          .catch(() => failures.push(`${slug}/${v}: 变体点击失败`));
        await sleep(600);
        comp.files[v] = {};
        await grabFrameworks(page, path.join(OUT, slug, v), comp.files[v]);
      }
    } else {
      await grabFrameworks(page, path.join(OUT, slug), comp.files);
    }

    const brief = variants.length
      ? `${variants.length} 变体`
      : Object.entries(comp.files).map(([k, v]) => `${k}:${v.length}`).join(' ');
    meta.components.push(comp);
    console.log(`✓ ${slug}  (${brief})`);
  }

  fs.mkdirSync(OUT, { recursive: true });
  fs.writeFileSync(path.join(OUT, '_meta.json'), JSON.stringify(meta, null, 2), 'utf8');
  await browser.close();

  console.log(`\n完成：${meta.components.length} 组件 / ${fileCount} 个代码文件 → ${OUT}`);
  if (failures.length) { console.log(`失败 ${failures.length} 项：`); failures.forEach(f => console.log('  ✗ ' + f)); }
})().catch(e => { console.error('FAIL:', e); process.exit(1); });
