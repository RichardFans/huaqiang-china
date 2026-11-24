// 构建后断言：全局样式表必须真的作用于页面内容。
//
// 背景（2026-11-24 实锤）：Astro 组件内的 <style> 默认带作用域（选择器会被改写成
// .x[data-astro-cid-…]），布局里的样式管不到经 <slot> 渲染进来的页面内容。站点上线后
// 整页没有样式，而 HTML 与 CSS 文件都返回 200，只查“资源可达”发现不了。
//
// 现在《征服二创宇宙档案》站点的全部样式都走 src/styles/global.css。本脚本在构建后检查：
//   1. 产物里存在 CSS；
//   2. CSS 里没有任何作用域选择器（data-astro-cid-*）；
//   3. 设计令牌与关键组件选择器确实在产物里；
//   4. 首页确实通过 <link rel="stylesheet"> 引用了这份样式表。
// 任一不满足即退出码 1，让 CI 失败。
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const dist = 'dist';
const astroDir = join(dist, '_astro');
const fail = (msg) => {
  console.error(`[assert-global-css] FAIL: ${msg}`);
  process.exit(1);
};

let files;
try {
  files = readdirSync(astroDir).filter((f) => f.endsWith('.css'));
} catch {
  fail(`找不到 ${astroDir}（先运行 astro build）`);
}
if (!files.length) fail('构建产物里没有 CSS 文件');

const css = files.map((f) => readFileSync(join(astroDir, f), 'utf8')).join('\n');
const scoped = css.match(/data-astro-cid-[a-z0-9]+/gi) || [];
if (scoped.length) {
  fail(`样式表里出现 ${scoped.length} 处作用域选择器（data-astro-cid-*）。`
    + '带作用域的样式管不到 <slot> 里的页面内容，请把规则放进 src/styles/global.css。');
}
for (const needle of ['--bg:', '--red:', '.site-head', '.rank li', '.wall .card-main', '.stat b', '.badge']) {
  if (!css.includes(needle)) fail(`样式表缺少全局规则或令牌：${needle}`);
}

const html = readFileSync(join(dist, 'index.html'), 'utf8');
if (!/<link[^>]*rel="stylesheet"[^>]*href="[^"]*_astro\/[^"]+\.css"/.test(html)) {
  fail('首页没有通过 <link rel="stylesheet"> 引用构建产物样式表');
}

console.log(`[assert-global-css] PASS: ${files.length} 个样式表，${css.length} 字节，全部为全局样式`);
