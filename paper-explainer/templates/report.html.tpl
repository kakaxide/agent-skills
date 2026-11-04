<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}} · 文献讲解</title>
<style>
  :root {
    --text: #1f2328;
    --muted: #5a6472;
    --border: #e3e6ea;
    --surface: #f6f7f9;
    --accent: #2e5077;
    --accent-soft: #eef3f8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--surface);
    color: var(--text);
    font: 400 15px/1.75 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  }
  .page {
    max-width: 880px;
    margin: 0 auto;
    padding: 48px 40px 64px;
    background: #fff;
  }
  header.paper { border-bottom: 2px solid var(--text); padding-bottom: 20px; margin-bottom: 28px; }
  h1.doc-title { font-size: 24px; line-height: 1.4; margin: 0 0 6px; }
  .meta { color: var(--muted); font-size: 13px; }
  .oneliner {
    margin-top: 14px; padding: 12px 16px;
    background: var(--accent-soft); border-left: 3px solid var(--accent);
    font-size: 14.5px;
  }
  .banner {
    margin: 0 0 28px; padding: 12px 16px;
    background: #fdf3e0; border: 1px solid #e5c55b; border-left: 4px solid #d9a520;
    font-size: 13.5px; color: #6b5200;
  }
  h2 { font-size: 19px; margin: 36px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
  h3 { font-size: 16px; margin: 26px 0 8px; }
  p { margin: 10px 0; }
  ul { margin: 8px 0; padding-left: 22px; }
  li { margin: 4px 0; }
  table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 13.5px; }
  th, td { border: 1px solid var(--border); padding: 7px 10px; text-align: left; }
  th { background: var(--surface); font-weight: 600; }
  figure { margin: 22px 0; padding: 14px; border: 1px solid var(--border); background: #fff; }
  figure img { display: block; max-width: 100%; height: auto; margin: 0 auto; }
  figcaption { margin-top: 10px; font-size: 12.5px; color: var(--muted); text-align: center; }
  .fig-note {
    margin-top: 10px; padding: 10px 14px;
    background: var(--surface); border-left: 3px solid var(--accent);
    font-size: 13.5px; line-height: 1.7;
  }
  .fig-src {
    display: inline-block; margin-right: 8px; padding: 0 6px;
    background: var(--accent-soft); color: var(--accent);
    font-size: 11.5px; border-radius: 3px; vertical-align: 1px;
  }
  .fig-missing { color: #a33; font-size: 13px; }
  footer {
    margin-top: 48px; padding-top: 14px; border-top: 1px solid var(--border);
    color: var(--muted); font-size: 12px;
  }
  @media print { body { background: #fff; } .page { padding: 0; } }
</style>
</head>
<body>
<div class="page">
  <header class="paper">
    <h1 class="doc-title">{{title}}</h1>
    <div class="meta">{{meta_line}}</div>
    <div class="oneliner"><strong>一句话总结</strong>：{{oneliner}}</div>
  </header>
  {{banner}}
  <main>
{{body}}
  </main>
  <footer>由 paper-explainer 生成于 {{generated_at}} · 图片均为论文原图，讲解请以原文为准</footer>
</div>
</body>
</html>
