/**
 * scripts/render_docs.js
 * 同步 src/templates/report.html 到 docs/index.html
 *
 * docs/index.html 会在浏览器侧读取 docs/gold_data.json 自动更新内容，
 * 因此此脚本只需保持模板与发布文件一致。
 *
 * 使用：node scripts/render_docs.js
 */

const fs = require('fs').promises;
const path = require('path');

const DOCS_DIR = path.join(__dirname, '..', 'docs');
const TEMPLATE_FILE = path.join(__dirname, '..', 'src', 'templates', 'report.html');
const OUT_FILE = path.join(DOCS_DIR, 'index.html');

async function main() {
  try {
    const html = await fs.readFile(TEMPLATE_FILE, 'utf8');
    await fs.writeFile(OUT_FILE, html, 'utf8');
    console.log(`成功：已更新 ${OUT_FILE}`);
  } catch (err) {
    console.error('生成失败：', err);
    process.exit(2);
  }
}

main();
