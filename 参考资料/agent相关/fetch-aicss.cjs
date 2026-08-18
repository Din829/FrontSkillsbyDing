#!/usr/bin/env node
/**
 * fetch-aicss.cjs — 取 aicss.dev 组件源码（React / CSS / Vue / Svelte 四份）
 *
 * 为什么存在：aicss.dev 的组件代码**无再分发授权**（官网只有一句 "Free to use"，
 *   没有 LICENSE、没有条款页、没有 GitHub 仓库）。源码目录不入公开仓库（.gitignore 排除）。
 *   需要时现场取即可 —— 取来用进用户项目在作者授权内，不落公开仓库就没有再分发问题。
 *
 * 为什么零依赖（关键判断，改脚本前先读）：
 *   站点是 Next.js App Router，**四个框架的代码随首屏一起下发**，不需要浏览器点 tab。
 *   （旧版用 playwright 点 tab 抓，是没找到下面这条路。）
 *   代码藏在 RSC 流式载荷里，解三层：
 *     ① self.__next_f.push([1,"…"]) 抓出所有分片拼接
 *     ② 反转义（载荷是 JS 字符串字面量）
 *     ③ 剥 <pre class="shiki">…</pre> 里的 span 标签 + HTML 实体反转义
 *   页面**没有**文件名/框架标签可用（不在载荷里），所以按内容特征认：
 *     <template> 开头→Vue ｜ 选择器开头→CSS ｜ 有 import+JSX→React ｜ 有 <style> 其余→Svelte
 *
 * 用法：
 *   node fetch-aicss.cjs --list                  列出全部组件 slug
 *   node fetch-aicss.cjs thinking-state          打印到 stdout（agent 现场用，不落盘）
 *   node fetch-aicss.cjs --all --out aicss-dev   全量落盘（换机器重建）
 *
 * 环境：Node 18+（内置 fetch，无需 npm install）
 * 站点变了怎么修：先跑 --list 看还能不能发现组件；再单拉一个组件看块数对不对。
 *   块数为 0 → 载荷格式变了，看 decodeRsc；块数对但分类错 → 看 classify。
 */
const fs = require('fs');
const path = require('path');
const BASE = 'https://www.aicss.dev';
const UA = { 'user-agent': 'Mozilla/5.0' };

// 必须用 JSON.parse，不能手写 replace 反转义。
// 原因（踩过）：载荷是 JS 字符串字面量，而组件代码**自身**也含转义序列
// （如 ' '、"\n" 这种字面量）。手写 replace 分不清哪层该解，会把代码里
// 本该保留的   解成真的 NBSP、把 "\n" 解成真换行 —— 产出的代码是坏的。
// JSON.parse 天然只解一层，正是我们要的。
function decodeRsc(html) {
  const parts = [...html.matchAll(/self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)/gs)];
  return parts
    .map((m) => {
      try {
        return JSON.parse(m[1]);
      } catch {
        return '';
      }
    })
    .join('');
}

// 实体必须**一次性**解，不能分步 replace（踩过两次）。
// 分步的坑：组件代码里本身就有 HTML 实体字面量（如做转义的 { "&": "&amp;" }），
// shiki 会把它二次编码成 &#x26;amp;。先解数字实体得到 &amp;（此时已正确），
// 后面那步再解命名实体就会把它变成 & —— 解了两次，代码语义被破坏。
// 下面用单个正则一次匹配，每个位置只解一次，不产生级联。
const NAMED = { lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', amp: '&' };
function stripTags(s) {
  return s
    .replace(/<[^>]+>/g, '')
    .replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+);/g, (m, e) => {
      if (e[0] === '#') {
        const code = e[1] === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
        return Number.isFinite(code) ? String.fromCodePoint(code) : m;
      }
      return NAMED[e] !== undefined ? NAMED[e] : m;
    });
}

// 站点上的真实组件名（如 task-list 页的组件叫 TodoList），从 tsx 里取，取不到才退回 slug 推导
function realName(blocks, slug) {
  for (const c of blocks) {
    const m = c.match(/\.\/([A-Za-z][A-Za-z0-9_]*)\.module\.css/) || c.match(/export function ([A-Za-z][A-Za-z0-9_]*)/);
    if (m) return m[1];
  }
  return slug.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join('');
}

// 产物结构对齐索引里写的：<slug>/{react,vue,svelte}/<真实名>.*
//
// 分类靠 import 来源优先，不能只看开头标签（踩过）：
//   ai-agent-input 的 Vue 版是 `<script setup lang="ts">` 开头、<template> 在后面，
//   只认 "<template> 开头" 会把它误判成 Svelte（因为它也含 <style>）。
function classify(code, comp) {
  // 先剥开头的块注释再看首字符：orbs 的 CSS 以 /* … */ 说明开头，不剥就认不出选择器
  const head = code.trimStart().replace(/^\/\*[\s\S]*?\*\//, '').trimStart().slice(0, 80);
  if (/from ["']vue["']/.test(code)) return ['vue', comp + '.vue'];
  if (/from ["']svelte["']/.test(code)) return ['svelte', comp + '.svelte'];
  if (head.startsWith('<template>')) return ['vue', comp + '.vue'];
  if (/^[.#@:*[]/.test(head)) return ['react', comp + '.module.css'];
  const hasImport = /\bimport\b|\bexport (default|function|const)\b/.test(code);
  const hasJsx = /className=|=>|return \(|return </.test(code);
  if (hasImport && hasJsx && !code.includes('<style')) return ['react', comp + '.tsx'];
  if (code.includes('<style')) return ['svelte', comp + '.svelte'];
  return ['_unknown', comp + '.txt'];
}

async function getFiles(slug) {
  const res = await fetch(BASE + '/components/' + slug, { headers: UA });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const rsc = decodeRsc(await res.text());
  const blocks = [...rsc.matchAll(/<pre class="shiki[^"]*"[^>]*>(.*?)<\/pre>/gs)]
    .map((m) => stripTags(m[1]).trim())
    .filter((c) => c.length > 20);
  const comp = realName(blocks, slug);
  const seen = new Map();
  return blocks.map((code) => {
    const [dir, base] = classify(code, comp);
    let name = dir + '/' + base;
    const n = (seen.get(name) || 0) + 1;
    seen.set(name, n);
    if (n > 1) name = name.replace(/\/([^./]+)/, '/$1-' + n);
    return { name, code };
  });
}

async function listSlugs() {
  const html = await (await fetch(BASE, { headers: UA })).text();
  const found = [...html.matchAll(/\/components\/([a-z0-9-]+)/g)].map((m) => m[1]);
  return [...new Set(found)].sort();
}

(async () => {
  const args = process.argv.slice(2);
  const outIdx = args.indexOf('--out');
  const outDir = outIdx > -1 ? args[outIdx + 1] : null;

  if (args.includes('--list')) {
    (await listSlugs()).forEach((s) => console.log(s));
    return;
  }

  const slugs = args.includes('--all')
    ? await listSlugs()
    : args.filter((a) => !a.startsWith('--') && a !== outDir);

  if (!slugs.length) {
    console.error('用法：node fetch-aicss.cjs --list | <slug> | --all --out <dir>');
    process.exit(1);
  }

  let ok = 0;
  for (const slug of slugs) {
    try {
      const files = await getFiles(slug);
      if (!files.length) throw new Error('未提取到代码块（站点结构可能变了，见文件头注释）');
      if (outDir) {
        const dir = path.join(outDir, slug);
        files.forEach((f) => {
          const dest = path.join(dir, f.name);
          fs.mkdirSync(path.dirname(dest), { recursive: true });
          fs.writeFileSync(dest, f.code);
        });
        console.log('✓ ' + slug.padEnd(20) + files.length + ' 个文件 → ' + dir);
      } else {
        console.log('\n════════ ' + slug + ' ════════');
        files.forEach((f) => console.log('\n──── ' + f.name + ' ────\n' + f.code));
      }
      ok++;
    } catch (e) {
      console.error('✗ ' + slug + ': ' + e.message);
    }
  }
  if (outDir) console.log('\n完成 ' + ok + '/' + slugs.length);
})();
