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

## 复刻指南（规划中）

「用 zfq 管线给任意梗建档案」的复刻指南正在准备，欢迎先读
[docs/decisions/](docs/decisions/) 了解架构决策。
