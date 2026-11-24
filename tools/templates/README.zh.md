# 🍉 征服二创宇宙档案 · The Conquest Remix Archive

> 《征服》(2003) 二创生态的**收集 · 整理 · 跟踪**——这个梗火了五年，还没人给它记账。
> 人类对华强的开发不足 0.1%，本档案负责记账。
> **English? → [README.en.md](README.en.md)** ｜ 🌐 站点 / Site：[richardfans.github.io/huaqiang-china](https://richardfans.github.io/huaqiang-china/)

[![在册二创](https://img.shields.io/endpoint?url=https%3A%2F%2Frichardfans.github.io%2Fhuaqiang-china%2Fbadges%2Fcount.json)](https://richardfans.github.io/huaqiang-china/)
[![华强开发度](https://img.shields.io/endpoint?url=https%3A%2F%2Frichardfans.github.io%2Fhuaqiang-china%2Fbadges%2Fdevelopment.json)](docs/decisions/0009-development-metric.md)
[![ci](https://img.shields.io/github/actions/workflow/status/RichardFans/huaqiang-china/ci.yml?branch=main)](https://github.com/RichardFans/huaqiang-china/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/code-MIT-content-CC_BY--SA_4.0)](LICENSE.content)

<p align="center">
  <img src="docs/assets/ignition-timeline.svg" alt="华强二创投稿密度月度时间线，2021-07 引爆窗口高亮" width="880">
</p>

## 🍉 这是什么

2026 年 11 月，作者又一次在B站刷到新的华强买瓜二创——从《萨日朗》到 AI 翻唱，
五年过去，这个梗还在长出新的形态，却没有任何一份系统的档案。

本项目想做的不是技术演示，而是一件更简单的事：把这段正在发生的互联网文化
**整理**清楚、持续**跟踪**它的演化，并把它**分享**给更多人——包括B站之外的世界。
手段恰好是开源的：每条数据带快照证据链，每个榜单由管线从数据生成、可复现。

## 🧑‍💻 关于作者

作者是一名B站大会员，看华强二创下饭多年。本项目为爱发电、非商业、无任何平台
官方背景；立项原因无他：喜欢，且觉得该有人做。

发现错漏，或想以 UP主 身份校对自己的条目？欢迎提 issue：
[投稿收录](.github/ISSUE_TEMPLATE/submit_video.yml) ·
[勘误校对](.github/ISSUE_TEMPLATE/correction.yml) ·
[申请下架](.github/ISSUE_TEMPLATE/takedown.yml)。

<!-- zfq:generated:start -->
<!-- zfq:generated:end -->

## 📡 订阅与切面

- 新收录 RSS（中文）`/feeds/new.rss.xml` ｜ New entries RSS (EN) `/feeds/new.en.rss.xml`
- 周涨幅榜 `/feeds/movers.rss.xml` ｜ Atom `/feeds/atom.xml` ｜ JSON Feed `/feeds/feed.json`
- 站点：[榜单实验室](https://richardfans.github.io/huaqiang-china/charts/)（按点赞/投币/评论等排序与筛选）、
  [作品全景](https://richardfans.github.io/huaqiang-china/graph/)、
  [编年](https://richardfans.github.io/huaqiang-china/chronicle/)
- 仓库内完整切面：[docs/lists/](docs/lists/)（桥段 / UP主 / 分级，自动生成）

## 🚀 快速开始（开发者）

```bash
uv venv .venv && uv pip install --python .venv/Scripts/python.exe requests pydantic jsonschema pytest
# 或：python -m pip install requests pydantic jsonschema pytest

export PYTHONPATH=tools   # Windows PowerShell: $env:PYTHONPATH='tools'
python -m zfq.validate     # 质量门禁 R1-R7（无需联网）
python -m pytest -q        # 测试
python -m zfq.track        # 跟踪刷新（联网，限速 1 req/s）
python -m zfq.build        # 重建视图/列表/README/订阅源/站点数据
```

站点（本地）：`cd site && npm install && npm run build` → `site/dist/`（纯静态）。
部署与站点地址配置见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 🗂 治理与导览

| 路径 | 内容 |
|---|---|
| `data/vocabulary.md` | 规范词表（canonical 名 + 变体/错写映射，检索的基石） |
| `data/entries/` `data/creators/` | 档案本体（每视频/每 UP 主一 JSON，带快照证据链） |
| `data/candidates/` | 拒绝日志——「为什么没收录」也是档案 |
| `docs/decisions/` | ADR ×9：收录 / 合规 / 命名 / 选型 / 发现 / 评审门控 / 封面链接 / 图谱 / 开发度 |
| `docs/methodology.md` `docs/verification.md` | 分期方法（预先注册）与验证协议 |
| `reports/` | 编年初稿 / 跟踪报告 / 交叉验证记录 |
| `tools/zfq/` | 数据管线（限速客户端 · 入册 · 跟踪 · 校验 · 构建 · issuebot） |
| `site/` | Astro 5 双语静态站 + 订阅源 |

**本 README 的全部榜单由 `zfq build` 自动生成**（数据即唯一事实源）；改数据后重跑 build，
CI 的 R7 规则会拦截「README 与数据不一致」的提交。

## ⚖️ 采集合规（重要）

本项目**不复刻、不分发平台的访问控制/签名机制**，仅以浏览器等价方式访问公开页面与端点，
仅收录元数据、默认限速、遇风控退避降级，并提供
[下架通道](.github/ISSUE_TEMPLATE/takedown.yml)（72 小时处置承诺）。背景（含
bilibili-API-collect 律师函事件与 robots.txt 留档）：[ADR-0002](docs/decisions/0002-collection-legal-posture.md)。

## 🤖 自动化

GitHub Actions：`ci`（门禁+站点构建+Pages 部署）· `track`（每日刷新 → 自动 PR）·
`discover`（每周发现 → 待评审 PR）· `issue-bot`（提交视频 issue → 实时校验 → PR）。
新条目默认 `review=pending`（[ADR-0006 评审门控](docs/decisions/0006-review-gate.md)），
榜单以「⚠」明示待复核状态。

## 📄 许可

- 代码：MIT ｜ 内容与数据：[CC BY-SA 4.0](LICENSE.content)
- 视频内容版权归原权利人与创作者所有；本仓库不存储任何音视频字节。
