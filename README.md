# 🍉 征服二创宇宙档案 · The Conquest Remix Archive

> 《征服》(2003) 二创生态的**收集 · 整理 · 跟踪**——一个把过程本身做成可复现数据管线的
> 开源研究档案。An open, reproducible research archive of the remix universe around
> *The Conquest* (2003), the TV drama behind “你这瓜保熟吗？”.

**English intro below ↓**

## 这是什么

- **收集**：以 B站为主战场，按[显式收录标准](docs/decisions/0001-scope-and-inclusion.md)
  收录「最火」的《征服》二创（华强买瓜 / 宋老虎请客 / 封彪桥段等全部名场面；
  鬼畜、音MAD、剧情剪辑、AI翻唱、AI视频等形态），每条带完整证据链；
- **整理**：[多切面链接列表](docs/lists/)（桥段/UP主/分级）+ [编年视图](reports/chronicle-draft.md)
  + [研究问题](RESEARCH.md)驱动的分析；
- **跟踪**：每日自动快照、涨幅榜、失效检测、双面交叉验证——档案是活的。

## 快速开始

```bash
uv venv .venv && uv pip install --python .venv/Scripts/python.exe requests pydantic jsonschema pytest
# 或：python -m pip install requests pydantic jsonschema pytest

export PYTHONPATH=tools   # Windows PowerShell: $env:PYTHONPATH='tools'
python -m zfq.validate     # 质量门禁 R1-R6（无需联网）
python -m pytest -q        # 测试（12 项）
python -m zfq.track        # 跟踪刷新（联网，限速 1 req/s）
python -m zfq.build        # 重建视图/列表/订阅源/站点数据
```

站点（本地）：`cd site && npm install && npm run build` → `site/dist/`（纯静态）。

## 目录导览

| 路径 | 内容 |
|---|---|
| `data/vocabulary.md` | 规范词表（canonical 名 + 变体/错写映射，检索的基石） |
| `data/entries/` `data/creators/` | 档案本体（每视频/每 UP 主一 JSON，带快照证据链） |
| `data/snapshots/` | 原始 API 响应留档（按日），manifest 记搜索页哈希 |
| `data/candidates/` | 拒绝日志——「为什么没收录」也是档案 |
| `docs/decisions/` | ADR ×6：收录标准 / 合规姿态 / 命名 / 选型 / 发现路线 / 评审门控 |
| `docs/methodology.md` `docs/verification.md` | 分期方法（预先注册）与验证协议 |
| `docs/lists/` | 多切面链接列表（自动生成） |
| `reports/` | 编年初稿 / 跟踪报告 / 交叉验证记录 |
| `tools/zfq/` | 数据管线（客户端限速退避 · 入册 · 跟踪 · 校验 · 构建 · issuebot） |
| `site/` | Astro 5 双语静态站 + 订阅源 |

## 订阅（国际推广通道）

- 新收录 RSS（中文）`/feeds/new.rss.xml` ｜ New entries RSS (EN) `/feeds/new.en.rss.xml`
- 周涨幅榜 `/feeds/movers.rss.xml` ｜ Atom `/feeds/atom.xml` ｜ JSON Feed `/feeds/feed.json`

## 采集合规（重要）

本项目**不复刻、不分发平台的访问控制/签名机制**，仅以浏览器等价方式访问公开页面与端点，
仅收录元数据、默认限速、遇风控退避降级，并提供
[下架通道](.github/ISSUE_TEMPLATE/takedown.yml)。背景（含 bilibili-API-collect 律师函事件
与 robots.txt 留档）：[ADR-0002](docs/decisions/0002-collection-legal-posture.md)。

## 自动化

GitHub Actions：`ci`（门禁+站点构建）· `track`（每日刷新 → 自动 PR）·
`discover`（每周发现 → 待评审 PR）· `issue-bot`（提交视频 issue → 实时校验 → PR）。
新条目默认 `review=pending`（[ADR-0006 评审门控](docs/decisions/0006-review-gate.md)），
站点以「⚠ 待复核」徽标明示不确定状态。

## 许可

- 代码：MIT（见 [LICENSE](LICENSE)）
- 内容与数据：[CC BY-SA 4.0](LICENSE.content)
- 视频内容版权归原权利人与创作者所有；本仓库不存储任何音视频字节。

## 部署备注

站点 URL 当前假设 `huaqiang-china.github.io`（根域 Pages）。实际仓库位置确定后，需同步修改
`site/astro.config.mjs` 与 `tools/zfq/build.py` 的 `SITE_URL`，并重跑 `zfq build`。

---

## English

**The Conquest Remix Archive** catalogues the derivative-work universe around
*The Conquest* (《征服》, 2003) — chiefly Bilibili remixes (guichu, 音MAD, edits,
AI voice-covers) of its iconic scenes: Liu Huaqiang buying a watermelon
(“Is this melon ripe?”), Song Laohu’s banquet, and Feng Biao’s standoffs.

Every number is a **timestamped first-hand snapshot** from public endpoints,
cross-validated across two independent surfaces (API JSON × page state).
Auto-catalogued entries are visibly marked *pending review* — we show
uncertainty instead of hiding it. The full pipeline (polite crawler →
review-gated ingest → daily tracking → validation gates → site & feeds)
is open and reproducible.

- Feeds: see **订阅** section above — subscribe from any RSS reader worldwide.
- Cultural guide for international readers: the 🍉 badge on the
  [English page](https://huaqiang-china.github.io/en/).
- Contributing: submit a video via the issue form (bot-validated), or file a
  correction. Takedown requests are honored within 72 hours.
