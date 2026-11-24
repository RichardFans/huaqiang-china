# 贡献与运维指南

## 三种参与方式（都走 issue 模板）

- **投稿收录**：发现值得入册的二创 → [submit_video](.github/ISSUE_TEMPLATE/submit_video.yml)
- **勘误校对**：数据有误，或 UP主 想校对自己的条目 → [correction](.github/ISSUE_TEMPLATE/correction.yml)
- **申请下架**：内容权利人 → [takedown](.github/ISSUE_TEMPLATE/takedown.yml)（72 小时处置承诺）

## 开发环境

见 README「快速开始」节。提交前门禁：`python -m zfq.validate`（R1–R7）+ `python -m pytest -q`。

## 站点部署（GitHub Pages）

- 数据门禁、管线构建、站点构建与发布都在 `ci` 工作流内完成（`deploy-pages` job）。
- 首次启用需一次性设置：仓库 **Settings → Pages → Source 选 「GitHub Actions」**。
- 本地预览：`cd site && npm install && npm run build` → `site/dist/`（纯静态）。

## 修改站点地址（SITE_URL）

站点 URL 在两处保持同步：`site/astro.config.mjs`（`site` + `base`）与
`tools/zfq/build.py` 的 `SITE_URL`。改动后必须重跑 `python -m zfq build`——
订阅源、榜单中的站点切面链接都会随之重新生成，CI 的 R7 规则校验一致性。

## 本地预览与界面核对

1. `python -m zfq.build`，然后 `cd site && npm run build`；
2. 回到仓库根目录运行 `python site/scripts/preview.py 8686`，打开
   http://127.0.0.1:8686/huaqiang-china/ （8686 是本机端口台账里本项目的预览端口）。

**界面改动必须实际渲染之后再交付**，只核对 HTML 结构不够。至少看三样：桌面宽度、
手机宽度（约 390px）、系统深色模式。

站点样式全部写在 `site/src/styles/global.css`，不要在组件里写 `<style>`：Astro 默认给它加
作用域，管不到经 `<slot>` 渲染进来的页面内容（2026-11-24 实锤，站点上线后整页没有样式）。
`npm run build` 会在构建后拦截作用域选择器，部署后另有冒烟任务检查线上样式表与脚本可达。

## 数据生成的图

时间线（`tools/zfq/timeline.py`）与创作者星图（`tools/zfq/graph.py`）都是数据的纯函数，
由 `zfq build` 生成 SVG，并受门禁 R10、R11 逐字节校验。README 里作为 `<img>` 使用，
靠 SVG 内部的 `prefers-color-scheme` 媒体查询适配 GitHub 的深色模式；站点里内联使用，
通过 CSS 变量跟随页面令牌。

## 复刻指南（规划中）

「用 zfq 管线给任意梗建档案」的复刻指南正在准备，欢迎先读
[docs/decisions/](docs/decisions/) 了解架构决策。
