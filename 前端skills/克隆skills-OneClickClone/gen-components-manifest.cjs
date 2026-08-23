#!/usr/bin/env node
/**
 * gen-components-manifest.cjs — 从 components.html + tokens.css 生成 components.manifest.json。
 * open-design 的「可重建缓存」：校验组件与 token 是否一致。纯静态解析，不起浏览器。
 *
 * 核心价值（会静默坏的 bug）：
 *   - undeclaredReferenced：组件用了 tokens.css 没声明的 var() → artifact 里解析成空、规则失效
 *   - literals：组件里没走 token 的裸 hex/px/字体 → 违反「零裸 hex」目标
 *
 * 用法: node gen-components-manifest.cjs <design-systems/<slug> 目录>
 *   读该目录下的 tokens.css + components.html，写出同目录 components.manifest.json
 */
const fs = require('fs');
const path = require('path');

const uniq = a => [...new Set(a)].sort();
const matchAll = (re, s) => { const out=[]; let m; while((m=re.exec(s))!==null) out.push(m[1]); return out; };

(async () => {
  const dir = path.resolve(process.cwd(), process.argv[2] || '.');
  const tokensPath = path.join(dir, 'tokens.css');
  const compPath = path.join(dir, 'components.html');
  // 边界防御：外部文件 IO
  if (!fs.existsSync(tokensPath)) { console.error(`tokens.css 不存在: ${tokensPath}`); process.exit(1); }
  if (!fs.existsSync(compPath)) { console.error(`components.html 不存在: ${compPath}`); process.exit(1); }

  // 剥注释（CSS /* */ 和 HTML <!-- -->），免得注释里的说明文字（如 "全部 var(--token)"）被误当引用
  const stripComments = s => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '');
  const tokensCss = stripComments(fs.readFileSync(tokensPath, 'utf8'));
  const html = stripComments(fs.readFileSync(compPath, 'utf8'));

  // tokens.css 声明的 token（--name: ...，只取 :root 里的声明，排除 var() 引用）
  const declared = uniq(matchAll(/^\s*(--[\w-]+)\s*:/gm, tokensCss));

  // components.html 引用的 token（var(--name)）。--token 是文档占位词，不算真引用。
  const referenced = uniq(matchAll(/var\(\s*(--[\w-]+)/g, html)).filter(t => t !== '--token');

  const declaredSet = new Set(declared), refSet = new Set(referenced);
  const unusedDeclared = declared.filter(t => !refSet.has(t));
  const undeclaredReferenced = referenced.filter(t => !declaredSet.has(t));

  // 裸值检测（components.html 里 <style> 中没走 token 的硬编码）
  const styleMatch = html.match(/<style[^>]*>([\s\S]*?)<\/style>/i);
  const styleBody = styleMatch ? styleMatch[1] : html;
  // 去掉 :root 块再数裸值（:root 里的 hex 是 token 定义，不算违规）
  const styleNoRoot = styleBody.replace(/:root\s*\{[\s\S]*?\}/g, '');
  const hardHex = matchAll(/(#[0-9a-fA-F]{3,8})\b/g, styleNoRoot);
  const hardPx = matchAll(/:\s*([0-9.]+px)\b/g, styleNoRoot);
  // 图标字体（Material/FontAwesome 等）是渲染机制不是设计 token，必须写死字体名，不算违规
  const ICON_FONTS = /material symbols|material icons|font ?awesome|bootstrap-icons|icomoon|iconfont/i;
  // 走了 token 的 var(--font-*) 不算裸值；图标字体也排除
  const hardFont = matchAll(/font-family\s*:\s*([^;}\n]+)/g, styleNoRoot).filter(f => !/var\(/.test(f) && !ICON_FONTS.test(f));

  // 选择器 / class
  const selectors = uniq(matchAll(/^\s*([.#][\w-]+(?:[:.][\w-]+)*)\s*[,{]/gm, styleBody)).slice(0, 200);
  const classes = uniq(matchAll(/class="([^"]+)"/g, html).flatMap(c => c.split(/\s+/)).filter(Boolean));

  const title = (html.match(/<title>([^<]+)<\/title>/i)||[])[1] || `${path.basename(dir)} — reference components`;

  const manifest = {
    schemaVersion: 1,
    brandId: path.basename(dir),
    source: { componentsHtml: 'components.html', tokensCss: 'tokens.css' },
    fixture: {
      title,
      styleBlockCount: (html.match(/<style/g)||[]).length,
      selectorCount: selectors.length,
      classCount: classes.length,
      elementCount: (html.match(/<[a-z][\w-]*/gi)||[]).length,
    },
    tokens: { declared, referenced, unusedDeclared, undeclaredReferenced },
    selectors,
    classes,
    literals: {
      colorExpressions: hardHex.length,
      pixelValues: hardPx.length,
      hardcodedFontFamilies: hardFont.length,
    },
  };

  fs.writeFileSync(path.join(dir, 'components.manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(`[manifest] → ${path.join(dir, 'components.manifest.json')}`);
  console.log(`  token: 声明 ${declared.length} / 引用 ${referenced.length} / 未用 ${unusedDeclared.length}`);
  if (undeclaredReferenced.length) console.error(`  🔴 用了未声明的 token（会静默失效）: ${undeclaredReferenced.join(', ')}`);
  else console.log(`  ✓ 无未声明引用`);
  const lit = manifest.literals;
  if (lit.colorExpressions || lit.hardcodedFontFamilies) console.warn(`  ⚠️ 裸值: hex ${lit.colorExpressions} / 硬字体 ${lit.hardcodedFontFamilies}（理想为0，应改 var(--token)）| 裸px ${lit.pixelValues}（micro 间距可接受）`);
  else console.log(`  ✓ 无裸 hex/字体（裸px ${lit.pixelValues}）`);
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
