# 验证协议：凭什么说数据是对的

> 设计原则：**正确性不由作者自证**。任何人（含第三方）都能用下列手段复核。

## 1. 可复现（管线级）

- 一条命令重跑全管线（见 README 快速开始）；所有产物（curated/列表/feeds/站点数据）
  是 data/ 的纯函数——构建确定性有单测保障（`test_build_deterministic`）；
- 每个快照带 `captured_at` + `endpoint`；原始 API 响应留存于 `data/snapshots/日期/`，
  随 git 版本化，可对任何历史时点审计。

## 2. 双面交叉验证（计数级）

同一 bvid 同日两个独立采集面：

- **A 面**：`api.bilibili.com/x/web-interface/view`（JSON 端点）
- **B 面**：视频页 HTML 内嵌状态（`"stat":{...}` 块解析）

两面计数逐字段比对（view/like/coin/favorite/share/danmaku/reply），
结果写入 `reports/cross-check.json`。B 面快照同时入条目证据链。

**2026-11-21 实测**：8/8 完全一致；此前一轮曾出现 2 条小幅不一致（两抓取时刻之间
计数自然跳动），复跑后一致——结论：两面共享同一后端计数，差异只来自时点。
另注：`like` 存在真实的小幅回收（327276→327270，3 分钟内），系平台取消赞聚合，
非数据错误（R4 规则据此分「警告/错误」两级，见 §4）。

## 3. 双通道 schema（结构级）

每个条目同时过两道校验：pydantic 模型（R1）+ pydantic 导出的 JSON Schema
经 jsonschema 库（R2）。CI 任一不过即阻断合并。

## 4. CI 门禁（规则级，`zfq.validate`）

- R1/R2 模型与 schema 双通道
- R3 受控词表与 `data/vocabulary.md` 同步（slug 失同步即 FAIL）
- R4 计数单调性：**分端点**序列内比较（跨端点有时差口径差，实测教训）；
  小幅回退（≤1% 且 ≤1000）降级为警告
- R5 快照 (endpoint, date) 唯一
- R6 seed 必填 tier_basis、auto 必填判定依据

## 5. 社区闭环（人间级）

- 误收/漏收/数据异常 → `correction` issue，处置记录公开；
- UP 主本人或权利方 → `takedown` issue，72 小时内处置承诺（ADR-0002）；
- 复核状态（pending/confirmed）在站点公开展示，「未复核不冒充确认」。

## 6. 外部三角验证（档案级，进行中）

- 观测站曲线（历史趋势旁证）——未接入；
- KnowYourMeme / 海外搬运与评述（国际接收证据）——未接入；
- 公开研究与媒体报道——未接入。
接入后与档案数据冲突处须显式标注，不得抹平。
