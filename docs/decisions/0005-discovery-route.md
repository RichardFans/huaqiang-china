# ADR-0005 · 作品发现路线

- 状态：Accepted（2026-11-21）
- 关联：ADR-0002（合规边界）

## 背景

B站搜索 JSON API 需 WBI 签名与登录态风控。依据 ADR-0002 原则 1，本仓库不实现签名机制。
2026-11-21 实测：搜索结果页 HTML 以混淆的 `window.__pinia` IIFE 内嵌结果数据，
其中 BV 号、标题、作者等以明文 JS 字面量出现，可无损解析。

## 决策：四条发现路线（按优先级）

1. **搜索页锚点解析**（主路线，自动）：`search.bilibili.com/all?keyword=<词表关键词>&order=click|pubdate`
   HTML → 正则抽取 `{author, mid, bvid, title, play, pubdate}`（浏览器等价 GET，
   首页取游客 cookie，无登录态）。
2. **`view` 端点富化**（自动）：`api.bilibili.com/x/web-interface/view?bvid=` 为无签名公开端点
   （浏览器直接可开），提供权威计数；`relation/stat?vmid=` 取 UP 主粉丝数。
3. **人工提交**（社区路线）：issue form 提交 BV 号 → Actions bot 调 view 端点校验 → PR。
4. **外部线索导航**（KYM/报道/论文提到的作品）：只作线索，数据仍须 1/2 路线一手核实。

## 明确不做

- WBI 签名、风控绕过、cookie 池、登录态模拟（ADR-0002）；
- 任何对平台私有协议的逆向文档化。

## 交叉验证面

计数一致性用「API view 端点 × 视频页 HTML 内嵌状态」双面核对（见 docs/verification.md）。
