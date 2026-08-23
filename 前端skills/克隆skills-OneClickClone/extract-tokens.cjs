#!/usr/bin/env node
/**
 * extract-tokens.cjs — 从真站提取「设计系统槽位」的真实值 + 证据。
 * clone-kit 的上游延伸雏形：面向 open-design 的 token schema，扒齐 surface/fg/accent/
 * 字号阶/间距/圆角/字体栈/容器宽，并记录每个值「取自哪个元素」。
 *
 * 不做判断（哪个色是 accent 需人确认），只做「扫描真值 + 频次统计 + 用途线索」。
 *
 * 用法: node extract-tokens.cjs <url> [--outdir DIR] [--locale ja-JP] [--vw 1440]
 * 产出: <outdir>/tokens.source.json —— 原始扒到的值+证据，喂给人/AI 归类成 tokens.css
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

function parseArgs(a){ const url=a[0]; const o={}; for(let i=1;i<a.length;i++){const x=a[i];if(x.startsWith('--')){const k=x.slice(2);const n=a[i+1];if(n===undefined||n.startsWith('--'))o[k]=true;else{o[k]=n;i++;}}} return {url,o}; }

(async () => {
  const { url, o } = parseArgs(process.argv.slice(2));
  if (!url) { console.error('需要 url'); process.exit(1); }
  let host='site'; try{host=new URL(url).hostname.replace(/^www\./,'');}catch{}
  const outdir = path.resolve(process.cwd(), o.outdir || `_clone-${host}/artifacts`);
  fs.mkdirSync(outdir, { recursive: true });

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: parseInt(o.vw)||1440, height: 900 }, locale: o.locale||'ja-JP' });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(2500);
  const cb = await page.$('#onetrust-accept-btn-handler'); if (cb) { await cb.click(); await page.waitForTimeout(500); }
  await page.evaluate(async()=>{const h=document.body.scrollHeight;for(let y=0;y<h;y+=window.innerHeight/2){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,200));}window.scrollTo(0,0);await new Promise(r=>setTimeout(r,300));});

  const data = await page.evaluate(() => {
    const tag = el => el.tagName.toLowerCase()+(el.className&&el.className.toString?'.'+el.className.toString().split(' ').filter(Boolean)[0]:'');

    // ---- 1) 颜色频次统计：背景色按「覆盖面积」加权，文字色按「字符数」加权 ----
    const bgArea = {}, bgSample = {};   // 背景色 → 总面积 / 一个样本元素
    const textChars = {}, textSample = {};
    const accentHints = {};             // 按钮/链接的高显眼色 → 出现次数（accent 线索）
    document.querySelectorAll('*').forEach(el => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      // 背景
      const bg = cs.backgroundColor;
      if (bg && bg!=='rgba(0, 0, 0, 0)' && bg!=='transparent') {
        bgArea[bg]=(bgArea[bg]||0)+r.width*r.height; if(!bgSample[bg])bgSample[bg]=tag(el);
      }
      // 文字（只统计直接含文字的）
      const txt = [...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('').length;
      if (txt>0) { const c=cs.color; textChars[c]=(textChars[c]||0)+txt; if(!textSample[c])textSample[c]=tag(el); }
      // accent 线索：按钮/链接的背景色 或 链接文字色
      if (el.tagName==='A' || el.tagName==='BUTTON' || cs.cursor==='pointer') {
        if (bg && bg!=='rgba(0, 0, 0, 0)' && bg!=='transparent') accentHints[bg]=(accentHints[bg]||0)+1;
        const lc = cs.color; if (el.tagName==='A' && lc) accentHints['text:'+lc]=(accentHints['text:'+lc]||0)+1;
      }
    });
    const top = (obj, n) => Object.entries(obj).sort((a,b)=>b[1]-a[1]).slice(0,n);

    // ---- 2) 字号阶：统计所有渲染字号 + 字重 + 行高，去重排序 ----
    const sizeMap = {}; // "px|weight" → {count, lineHeight样本, sample}
    document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,a,span,li,div,button,label').forEach(el=>{
      const txt=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent.trim()).join('');
      if(!txt) return;
      const cs=getComputedStyle(el); const key=`${cs.fontSize}|${cs.fontWeight}`;
      if(!sizeMap[key]) sizeMap[key]={fontSize:cs.fontSize,fontWeight:cs.fontWeight,lineHeight:cs.lineHeight,letterSpacing:cs.letterSpacing,count:0,sample:el.tagName.toLowerCase()};
      sizeMap[key].count++;
    });
    const sizes = Object.values(sizeMap).sort((a,b)=>parseFloat(b.fontSize)-parseFloat(a.fontSize));

    // ---- 3) 字体栈 ----
    const fonts = { display: document.querySelector('h1,h2')?getComputedStyle(document.querySelector('h1,h2')).fontFamily:null,
      body: getComputedStyle(document.body).fontFamily,
      computed: [...new Set([...document.querySelectorAll('h1,h2,h3,p,a,span,button')].map(e=>getComputedStyle(e).fontFamily))].slice(0,8) };

    // ---- 4) 间距：统计常见 padding/gap 值 ----
    const spaceFreq = {};
    document.querySelectorAll('section,div,article,main,header,footer').forEach(el=>{
      const cs=getComputedStyle(el);
      [cs.paddingTop,cs.paddingBottom,cs.gap,cs.rowGap].forEach(v=>{ if(v&&/^\d+px$/.test(v)&&parseInt(v)>0){spaceFreq[v]=(spaceFreq[v]||0)+1;} });
    });

    // ---- 5) 圆角：按组件类别分别统计（不全站取频次——会被卡片0px带偏，漏掉按钮32px）----
    // 教训：KPMG 全站 0px 最多，但按钮其实是 32px 胶囊。圆角必须按角色分桶。
    const radiusByRole = { button: {}, card: {}, input: {}, pill: {}, other: {} };
    const roleOf = el => {
      const t = el.tagName, cls = (el.className&&el.className.toString?el.className.toString().toLowerCase():'');
      if (t==='BUTTON' || /\bbtn\b|button|cta/.test(cls) || (t==='A' && getComputedStyle(el).backgroundColor!=='rgba(0, 0, 0, 0)')) return 'button';
      if (t==='INPUT' || t==='SELECT' || t==='TEXTAREA' || /input|field|search/.test(cls)) return 'input';
      if (/card|teaser|tile|panel/.test(cls) || t==='ARTICLE') return 'card';
      if (/tag|chip|badge|pill/.test(cls)) return 'pill';
      return 'other';
    };
    document.querySelectorAll('*').forEach(el=>{
      const v=getComputedStyle(el).borderRadius; if(!v||!/px/.test(v)) return;
      const r=el.getBoundingClientRect(); if(r.width<8||r.height<8) return;
      const bucket = radiusByRole[roleOf(el)]; bucket[v]=(bucket[v]||0)+1;
    });
    const summarizeRadius = obj => top(obj, 4).map(([v,n])=>({value:v,count:n}));

    // ---- 6) 按钮真实样式采样（带背景的可点元素）----
    const buttonSamples = [...document.querySelectorAll('a,button,[role="button"]')]
      .filter(b=>{const cs=getComputedStyle(b),r=b.getBoundingClientRect();return cs.backgroundColor!=='rgba(0, 0, 0, 0)'&&cs.backgroundColor!=='transparent'&&r.height>28&&r.width>56;})
      .slice(0,6).map(b=>{const cs=getComputedStyle(b);return {text:b.innerText.trim().slice(0,24),bg:cs.backgroundColor,color:cs.color,borderRadius:cs.borderRadius,padding:cs.padding,fontSize:cs.fontSize,fontWeight:cs.fontWeight};});

    // ---- 7) 阴影：非 none 的 box-shadow 频次 ----
    const shadowFreq={}; document.querySelectorAll('*').forEach(el=>{const s=getComputedStyle(el).boxShadow;if(s&&s!=='none'){shadowFreq[s]=(shadowFreq[s]||0)+1;}});

    // ---- 8) 容器宽 ----
    const widths={}; document.querySelectorAll('div,section,main,header').forEach(el=>{const mw=getComputedStyle(el).maxWidth;if(mw&&/px/.test(mw)&&parseInt(mw)>600){widths[mw]=(widths[mw]||0)+1;}});

    return {
      bgByArea: top(bgArea,8).map(([c,a])=>({color:c,area:Math.round(a),sample:bgSample[c]})),
      textByChars: top(textChars,8).map(([c,n])=>({color:c,chars:n,sample:textSample[c]})),
      accentHints: top(accentHints,8).map(([c,n])=>({value:c,count:n})),
      typeScale: sizes,
      fonts,
      spacing: top(spaceFreq,12).map(([v,n])=>({value:v,count:n})),
      radiusByRole: { button: summarizeRadius(radiusByRole.button), card: summarizeRadius(radiusByRole.card), input: summarizeRadius(radiusByRole.input), pill: summarizeRadius(radiusByRole.pill), other: summarizeRadius(radiusByRole.other) },
      buttonSamples,
      shadows: top(shadowFreq,6).map(([v,n])=>({value:v,count:n})),
      containerWidths: top(widths,5).map(([v,n])=>({value:v,count:n})),
    };
  });

  data._meta = { url, host, extractedViewport: parseInt(o.vw)||1440,
    note: '原始真值+频次，需 AI 归类到 token schema。圆角：buttonSamples 的 borderRadius 比 radiusByRole.button 更可靠（角色启发式会把手风琴/列表项误判为 button，污染频次）。归类按钮圆角以 buttonSamples 中真正 CTA 的值为准。' };
  fs.writeFileSync(path.join(outdir,'tokens.source.json'), JSON.stringify(data, null, 2));
  console.log(`[tokens] → ${path.join(outdir,'tokens.source.json')}`);
  console.log(`  背景色(按面积): ${data.bgByArea.slice(0,3).map(x=>x.color).join(', ')}`);
  console.log(`  accent线索: ${data.accentHints.slice(0,3).map(x=>x.value).join(', ')}`);
  console.log(`  字号阶: ${data.typeScale.length} 档 | 字体: ${data.fonts.display}`);
  const rb = data.radiusByRole;
  console.log(`  圆角(按组件): 按钮 ${rb.button[0]?.value||'-'} | 卡片 ${rb.card[0]?.value||'-'} | 输入 ${rb.input[0]?.value||'-'}`);

  // ---- 组件结构采样 → source/snippets/（证据核对表，铁律5：源码当参考，不照搬）----
  // 每类组件取代表，存真实 outerHTML + 容器关键 computed。AI 据此重写成 token 化干净组件。
  const snippets = await page.evaluate(() => {
    const pickComputed = el => { const cs=getComputedStyle(el); const want=['display','padding','margin','borderRadius','border','background','backgroundColor','color','fontSize','fontWeight','boxShadow','gap','gridTemplateColumns','flexDirection','alignItems','justifyContent','width','maxWidth']; const o={}; want.forEach(p=>{const v=cs[p];if(v&&v!=='none'&&v!=='normal'&&v!=='auto'&&v!=='0px'&&v!=='rgba(0, 0, 0, 0)')o[p]=v;}); return o; };
    const grab = (selList, label, max) => {
      const seen = new Set(); const out = [];
      for (const sel of selList) {
        for (const el of document.querySelectorAll(sel)) {
          const r = el.getBoundingClientRect(); if (r.width<40||r.height<20) continue;
          const html = el.outerHTML; if (seen.has(html.slice(0,200))) continue; seen.add(html.slice(0,200));
          out.push({ label, selector: sel, computed: pickComputed(el), outerHTML: html.slice(0, 2500) });
          if (out.length>=max) return out;
        }
        if (out.length>=max) break;
      }
      return out;
    };
    return {
      button: grab(['a[class*="btn"]','button[class*="btn"]','[class*="cta"] a','a[class*="action"]','button'], 'button', 3),
      card: grab(['[class*="card"]','[class*="teaser"]','[class*="tile"]','article'], 'card', 2),
      input: grab(['input[type="text"]','input[type="search"]','[class*="search"] input','input'], 'input', 1),
    };
  });
  const snipDir = path.join(path.dirname(outdir), 'source', 'snippets'); // outdir 是 .../artifacts，snippets 放兄弟 source/
  fs.mkdirSync(snipDir, { recursive: true });
  const allSnips = [...snippets.button, ...snippets.card, ...snippets.input];
  fs.writeFileSync(path.join(snipDir, 'components.snippets.json'), JSON.stringify({
    _note: '组件真实结构+computed，证据核对表（非成品）。AI 重写成 var(--token) 干净组件，别照搬混淆 class。',
    samples: allSnips,
  }, null, 2));
  console.log(`  组件采样: 按钮${snippets.button.length} 卡片${snippets.card.length} 输入${snippets.input.length} → source/snippets/components.snippets.json`);

  await browser.close();
})().catch(e=>{console.error('FAIL:',e.message);process.exit(1);});
