#!/usr/bin/env node
/**
 * gen-refs.cjs — 生成网页设计参考图（无参考站时的原料来源）。
 *
 * 链路补全：有参考站 → clone-kit shot 截图当原料；没有 → 这个脚本让 GPT-image /
 * Nano Banana 生成精美网页参考图，再喂给实现 AI 当视觉蓝本。
 *
 * 设计依据（2026 实测最佳实践 + taste-skill image-to-code 经验）：
 *   - 分区块出图 > 一张大图塞全部（单图多屏→文字糊→AI 提取不出来）。默认每区块一张。
 *   - 图要大、高清、视觉层级分明；prompt 要点名组件、写设计意图，避免通用 AI 味。
 *
 * 用法:
 *   node gen-refs.cjs "<整体设计意图>" [options]
 * 例:
 *   node gen-refs.cjs "极简 SaaS 着陆页，藏青蓝主色，Noto Sans" --sections hero,features,pricing --n 2
 *   node gen-refs.cjs "企业服务页" --ref ./shot.png        # 有真站截图→出变体/对齐风格
 *
 * options:
 *   --backend <openai|gemini>  默认 openai（gpt-image-2 优先）
 *   --sections <a,b,c>         区块清单，每区块一张图。默认 hero
 *   --ref <png>               参考图（可多次）。有则当视觉锚点传给模型
 *   --n <int>                 每区块候选数，默认 1
 *   --aspect <landscape|square|portrait>  默认 landscape（真 16:9 网页比例）
 *       gpt-image-2 接受任意尺寸 → landscape=1920×1088(≈16:9)；gemini=16:9。两后端都是宽屏网页比例。
 *   --outdir <dir>            默认 _refs-<slug>
 *   --model <id>             覆盖后端默认模型
 *
 * key: 优先环境变量 OPENAI_API_KEY / GEMINI_API_KEY；缺则就近找 .env（当前工作目录 → 脚本同目录）。
 *      不写死任何外部路径——换电脑只需 export env，或在跑命令的目录放个 .env（写 OPENAI_API_KEY=xxx）。
 */
const fs = require('fs');
const path = require('path');

// ---------- 参数解析 ----------
function parseArgs(argv) {
  const intent = argv[0];
  const o = { ref: [] };
  for (let i = 1; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const k = a.slice(2), next = argv[i + 1];
    if (k === 'ref') { if (next && !next.startsWith('--')) { o.ref.push(next); i++; } }
    else if (next === undefined || next.startsWith('--')) o[k] = true;
    else { o[k] = next; i++; }
  }
  return { intent, o };
}

// ---------- key 读取：env 优先 + 就近 .env 兜底（不写死任何外部路径，换电脑只需配 env 或丢个 .env）----------
function readKey(name) {
  if (process.env[name]) return process.env[name];
  // fallback：按顺序找 .env —— 当前工作目录 → 脚本同目录。哪台电脑都靠这两处之一配。
  const candidates = [
    path.resolve(process.cwd(), '.env'),
    path.resolve(__dirname, '.env'),
  ];
  for (const p of candidates) {
    try {
      const m = fs.readFileSync(p, 'utf8').match(new RegExp(`^${name}\\s*=\\s*(.+)$`, 'm'));
      if (m && m[1].trim()) return m[1].trim().replace(/^["']|["']$/g, ''); // 去掉可能的引号
    } catch {}
  }
  return null;
}

// ---------- 输出目录 ----------
function slugify(s) { return String(s).replace(/[^a-zA-Z0-9一-龥ぁ-んァ-ヶ]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 24) || 'site'; }

// ---------- 设计系统注入：读 design-systems/<brand>，浓缩成"风格锁定"前缀 ----------
// 极简版（不学 AIPowerPoint 的三层合并/lint）：tokens.css 抽确切值 + DESIGN.md 抽气质。
// 灵活降级：dir 不存在 / 文件缺 / 抽不到 → 返回 ''（等于没传，不崩）。
function loadDesignSystem(dir) {
  if (!dir) return '';
  const root = path.resolve(process.cwd(), dir);
  const grabCss = (css, name) => { const m = css.match(new RegExp(`--${name}\\s*:\\s*([^;]+);`)); return m ? m[1].trim() : null; };
  const grabSection = (md, titleRe, max) => {
    // 两步法（避开 multiline 下 $ 匹配每行末的歧义）：① 定位标题行 ② 从其后截到下一个 "\n## " 或文末
    const head = md.match(new RegExp(`^##[^\\n]*(?:${titleRe})[^\\n]*\\n`, 'm'));
    if (!head) return null;
    const after = md.slice(head.index + head[0].length);
    const nextH2 = after.search(/\n##\s/);
    const body = nextH2 === -1 ? after : after.slice(0, nextH2);
    return body.replace(/[#>*\`|]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max) || null;
  };

  const lines = [];
  // 1) tokens.css 的确切值（精确——色值/字体/形状）
  try {
    const css = fs.readFileSync(path.join(root, 'tokens.css'), 'utf8');
    const accent = grabCss(css, 'accent'), link = grabCss(css, 'accent-link');
    const bg = grabCss(css, 'bg'), surface = grabCss(css, 'surface'), fg = grabCss(css, 'fg');
    const fontD = grabCss(css, 'font-display'), fontB = grabCss(css, 'font-body');
    const rSm = grabCss(css, 'radius-sm'), rPill = grabCss(css, 'radius-pill');
    const palette = [accent && `brand accent ${accent}`, link && `interactive accent ${link}`,
      bg && `bg ${bg}`, surface && `surface ${surface}`, fg && `text ${fg}`].filter(Boolean).join(', ');
    if (palette) lines.push(`Palette: ${palette}.`);
    if (fontD || fontB) lines.push(`Fonts: ${[fontD, fontB].filter(Boolean).join(' / ')}.`);
    // 形状：sm=0 是直角、pill=9999 是胶囊 —— 用人话表达而非裸值
    if (rSm || rPill) {
      const shape = [];
      if (rSm) shape.push(parseInt(rSm) <= 2 ? 'square / sharp-corner containers' : `containers radius ${rSm}`);
      if (rPill) shape.push('pill / capsule buttons');
      lines.push(`Shape: ${shape.join(', ')}.`);
    }
  } catch {}
  // 2) DESIGN.md 的气质（意图——一句话氛围）
  try {
    const md = fs.readFileSync(path.join(root, 'DESIGN.md'), 'utf8');
    const atmosphere = grabSection(md, 'Visual Theme|Atmosphere|视觉|氛围', 280)
      || grabSection(md, 'Quick|快速参考|Agent Prompt', 280);
    if (atmosphere) lines.push(`Atmosphere: ${atmosphere}`);
  } catch {}

  if (!lines.length) return ''; // 啥也没抽到 → 当没传
  // 陈述事实，不下命令（学 AIPowerPoint：给品牌的色/字/形状/气质，让模型照着这个世界设计）。
  // continuity 靠「每个区块都给同一份事实」自然达成，不靠 MUST/LOCK 强命令。
  return [
    `## Design system (this brand's visual language — design within it)`,
    ...lines,
    `These sections belong to one site, so they share this brand's name, palette, fonts, shape language, and copy language.`,
  ].join('\n');
}

// ---------- prompt 模板：把最佳实践写进去（分区块、可读、点组件、避 AI 味）----------
// 软指示哲学（学 AIPowerPoint）：给足「事实」——设计系统(色/字/组件/气质) + 内容 + 区块，
// 具体怎么设计、排版、艺术化交给图像模型。不堆"avoid/no/don't"禁令把模型框死。
// 只保留少量「输出格式」约束（每区块一张、横版、文字可读）——这是技术必要，不是设计干预。
function buildPrompt(intent, section, dsPrefix) {
  return [
    ...(dsPrefix ? [dsPrefix, ``] : []),  // 设计系统事实（陈述，非命令）；没传则无
    `Design a premium website "${section}" section as a build-reference mockup.`,
    `What this page is about: ${intent}.`,
    ``,
    `Use real, plausible UI components and concrete copy that fit a ${section} (e.g. nav, headline, CTAs, cards — whatever this section genuinely needs). You decide the layout, composition, and art direction.`,
    ``,
    `Output format: one single ${section} section per image, full-width, horizontal. Keep typography large and legible — this image is used to build from.`,
  ].join('\n');
}

// gpt-image-2 接受任意尺寸（官方约束：边≤3840、均为16的倍数、长短比≤3:1、像素655360–8294400）。
// 网页参考图用真 16:9。1920×1088 ≈ 16:9（1088=68×16，最接近 1080 的合规值）。
const ASPECT_OPENAI = { landscape: '1920x1088', square: '1024x1024', portrait: '1088x1920' };
const ASPECT_GEMINI = { landscape: '16:9', square: '1:1', portrait: '9:16' };

// ====================================================================
// 后端
// ====================================================================
async function backendOpenAI({ prompt, refs, n, aspect, model }) {
  const OpenAI = require('openai');
  const { toFile } = require('openai');
  const key = readKey('OPENAI_API_KEY');
  if (!key) throw new Error('缺 OPENAI_API_KEY（env 或 AIPowerPoint/.env）');
  const client = new OpenAI({ apiKey: key });
  const mdl = model || 'gpt-image-2';
  const size = ASPECT_OPENAI[aspect] || ASPECT_OPENAI.landscape;

  let res;
  if (refs.length) {
    // 有参考图 → images.edit。用 toFile 显式带 mimetype，否则 SDK 默认
    // application/octet-stream 被 API 拒（实测 400，已查证官方修法）。
    const images = await Promise.all(refs.map(p =>
      toFile(fs.readFileSync(p), path.basename(p), { type: 'image/png' })));
    res = await client.images.edit({ model: mdl, image: images, prompt, size, quality: 'high', n });
  } else {
    res = await client.images.generate({ model: mdl, prompt, size, quality: 'high', n });
  }
  // 总是 b64_json
  return res.data.map(d => Buffer.from(d.b64_json, 'base64'));
}

async function backendGemini({ prompt, refs, n, aspect, model }) {
  const { GoogleGenAI } = require('@google/genai');
  const key = readKey('GEMINI_API_KEY');
  if (!key) throw new Error('缺 GEMINI_API_KEY（env 或 AIPowerPoint/.env）');
  const ai = new GoogleGenAI({ apiKey: key });
  const mdl = model || 'gemini-3.1-flash-image';
  const aspectRatio = ASPECT_GEMINI[aspect] || ASPECT_GEMINI.landscape;

  // Gemini 单次一张 → 循环 n 次。参考图作为 inlineData 一并传。
  const out = [];
  for (let i = 0; i < n; i++) {
    const parts = [{ text: prompt }];
    for (const p of refs) {
      const b64 = fs.readFileSync(p).toString('base64');
      parts.push({ inlineData: { mimeType: 'image/png', data: b64 } });
    }
    const res = await ai.models.generateContent({
      model: mdl,
      contents: [{ role: 'user', parts }],
      config: { responseModalities: ['TEXT', 'IMAGE'], responseFormat: { image: { aspectRatio, imageSize: '2K' } } },
    });
    const cand = (res.candidates || [])[0];
    const imgPart = (cand?.content?.parts || []).find(p => p.inlineData?.data);
    if (!imgPart) throw new Error('Gemini 返回无图片 part');
    out.push(Buffer.from(imgPart.inlineData.data, 'base64'));
  }
  return out;
}

const BACKENDS = { openai: backendOpenAI, gemini: backendGemini };

// ====================================================================
// 主流程
// ====================================================================
(async () => {
  const { intent, o } = parseArgs(process.argv.slice(2));
  if (!intent) { console.error('用法: node gen-refs.cjs "<设计意图>" [--sections hero,features] [--design-system design-systems/<brand>] [--ref x.png] [--n 1] [--backend openai|gemini]'); process.exit(1); }

  const backendName = (o.backend || 'openai').toLowerCase();
  const backend = BACKENDS[backendName];
  if (!backend) { console.error(`未知 backend: ${backendName}（openai|gemini）`); process.exit(1); }

  const sections = (o.sections || 'hero').split(',').map(s => s.trim()).filter(Boolean);
  const refs = (o.ref || []).map(p => path.resolve(process.cwd(), p));
  for (const r of refs) if (!fs.existsSync(r)) { console.error(`参考图不存在: ${r}`); process.exit(1); }
  const n = Math.max(1, parseInt(o.n) || 1);
  const aspect = o.aspect || 'landscape';
  const outdir = path.resolve(process.cwd(), o.outdir || `_refs-${slugify(intent)}`);
  fs.mkdirSync(outdir, { recursive: true });

  // 设计系统注入（可选）：传了就把品牌风格锁进每个区块的 prompt；没传/抽不到 → 空串，零侵入。
  const dsDir = o['design-system'];
  const dsPrefix = loadDesignSystem(dsDir);
  if (dsDir && !dsPrefix) console.warn(`[gen-refs] ⚠️ --design-system ${dsDir} 未抽到 tokens.css/DESIGN.md，按未注入处理`);

  console.log(`[gen-refs] backend=${backendName} | 区块=[${sections.join(', ')}] | n=${n} | aspect=${aspect}${refs.length ? ` | refs=${refs.length}` : ''}${dsPrefix ? ` | 设计系统=${path.basename(path.resolve(process.cwd(), dsDir))}` : ''}`);

  const manifest = { intent, backend: backendName, aspect, refs, designSystem: dsPrefix ? dsDir : null, generated: [] };
  for (const section of sections) {
    const prompt = buildPrompt(intent, section, dsPrefix);
    // request dump（调 API 前先写，失败可复盘）
    fs.writeFileSync(path.join(outdir, `_request-${section}.txt`),
      `backend=${backendName}\nmodel=${o.model || '(default)'}\naspect=${aspect}\nrefs=${refs.join(', ')||'(none)'}\n\n--- prompt ---\n${prompt}\n`);

    let buffers;
    try {
      buffers = await retry(() => backend({ prompt, refs, n, aspect, model: o.model }), 2);
    } catch (e) {
      console.error(`  ✗ ${section}: ${e.message}`);
      manifest.generated.push({ section, error: e.message });
      continue;
    }
    buffers.forEach((buf, i) => {
      const fname = n > 1 ? `${section}-${i + 1}.png` : `${section}.png`;
      fs.writeFileSync(path.join(outdir, fname), buf);
      console.log(`  ✓ ${fname}  (${(buf.length / 1024).toFixed(0)} KB)`);
      manifest.generated.push({ section, file: fname, bytes: buf.length });
    });
  }

  fs.writeFileSync(path.join(outdir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  const ok = manifest.generated.filter(g => g.file).length;
  console.log(`[gen-refs] 完成: ${ok} 张 → ${outdir}`);
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });

async function retry(fn, times) {
  let last;
  for (let i = 0; i < times; i++) {
    try { return await fn(); } catch (e) { last = e; }
  }
  throw last;
}
