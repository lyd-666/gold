/**
 * scripts/render_docs.js
 * 读取 docs/gold_data.json 并生成 docs/index.html
 *
 * 使用：node scripts/render_docs.js
 *
 * 说明：
 * - 假设文件位于仓库的 docs/ 目录： docs/gold_data.json -> docs/index.html
 * - 如果路径不同，请修改下面的常量
 */

const fs = require('fs').promises;
const path = require('path');

const DOCS_DIR = path.join(__dirname, '..', 'docs');
const JSON_FILE = path.join(DOCS_DIR, 'gold_data.json');
const OUT_FILE = path.join(DOCS_DIR, 'index.html');

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function renderComplexValue(value) {
  if (value === null) return '<span class="null">null</span>';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return `<pre class="small">${escapeHtml(String(value))}</pre>`;
  }
  try {
    return `<pre class="small">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
  } catch (e) {
    return `<pre class="small">${escapeHtml(String(value))}</pre>`;
  }
}

function renderObject(obj) {
  const entries = Object.keys(obj).map(k => {
    return `<div class="kv-row"><div class="key">${escapeHtml(k)}</div><div class="val">${renderComplexValue(obj[k])}</div></div>`;
  }).join('\n');
  return `<div class="kv">${entries}</div>`;
}

function renderArray(arr) {
  const areObjects = arr.every(item => item && typeof item === 'object' && !Array.isArray(item));
  if (areObjects) {
    // collect keys
    const keys = Array.from(arr.reduce((s, it) => {
      Object.keys(it).forEach(k => s.add(k));
      return s;
    }, new Set()));
    const ths = keys.map(k => `<th>${escapeHtml(k)}</th>`).join('');
    const rows = arr.map(item => {
      const tds = keys.map(k => `<td>${item.hasOwnProperty(k) ? renderComplexValue(item[k]) : ''}</td>`).join('');
      return `<tr>${tds}</tr>`;
    }).join('\n');
    return `<table><thead><tr>${ths}</tr></thead><tbody>${rows}</tbody></table>`;
  } else {
    const rows = arr.map(item => `<tr><td>${renderComplexValue(item)}</td></tr>`).join('\n');
    return `<table><thead><tr><th>Value</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
}

function generateHtmlFromJson(data) {
  // Build a simple HTML page with styles and rendered content
  let bodyContent = '';
  if (Array.isArray(data)) {
    if (data.length === 0) {
      bodyContent = '<p class="muted">数据是空数组。</p>';
    } else {
      bodyContent = renderArray(data);
    }
  } else if (data && typeof data === 'object') {
    bodyContent = renderObject(data);
  } else {
    bodyContent = `<pre class="small">${escapeHtml(String(data))}</pre>`;
  }

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Gold Data Viewer</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial; padding: 20px; color:#222; }
    h1 { margin-top: 0; }
    .muted { color:#666; font-size: 14px; }
    table { border-collapse: collapse; width: 100%; max-width: 1200px; margin-top: 8px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #f7f7f7; font-weight: 600; }
    pre.small { margin:0; white-space: pre-wrap; word-break: break-word; font-size: 13px; background:#fafafa; padding:8px; border-radius:4px; }
    .kv { display: grid; grid-template-columns: 200px 1fr; gap: 6px 12px; align-items: start; max-width: 1200px; }
    .kv-row { display: contents; }
    .key { font-weight: 600; color:#333; padding:8px 0; }
    .val { color:#111; padding:8px 0; }
    .null { color:#a00; font-weight:600; }
  </style>
</head>
<body>
  <h1>Gold Data Viewer</h1>
  <div id="content">
    ${bodyContent}
  </div>
  <footer style="margin-top:20px;color:#666;font-size:13px;">
    自动生成：docs/gold_data.json → docs/index.html
  </footer>
</body>
</html>`;
  return html;
}

async function main() {
  try {
    const raw = await fs.readFile(JSON_FILE, 'utf8');
    const data = JSON.parse(raw);
    const html = generateHtmlFromJson(data);
    await fs.writeFile(OUT_FILE, html, 'utf8');
    console.log(`成功：已生成 ${OUT_FILE}`);
  } catch (err) {
    console.error('生成失败：', err);
    process.exit(2);
  }
}

main();
