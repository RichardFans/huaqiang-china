# ADR-0007 · 封面回填与 UP主 链接（cover mining & creator links）

- 状态：Accepted（2026-11-24）
- 背景：P2 门面轮需要封面墙与 UP主 可达性。原始素材**已经在库内**：
  `data/snapshots/*/view/*.json` 的 `data.pic` 即封面 URL、`owner.mid` 即 UP主 恒定 ID，
  无需任何新采集。

## 决策

1. **cover 是挖掘产物，不是独立采集**：
   - `Entry` 新增 `cover`（URL 引用）与 `cover_evidence`（如 `mined: api-view@2026-11-21`）；
   - 挖掘规则：取该 BV **最晚日期** view 快照的 `data.pic`（`zfq.mine`，幂等）；
   - 新条目在 `zfq.ingest` 入册时即写入 cover；
   - `track`/`discover` 工作流在快照刷新后自动跑 `zfq mine`。
2. **R8 门禁**：`entries.cover` 必须与最新快照 pic 一致，且有 cover_evidence——
   漂移即 CI FAIL（与 R7 的 README 纪律同构：可复算、可拦截）。
3. **UP主 一律按 mid 链接**（`space.bilibili.com/{mid}`）：名字会改（库内已有
   names_history 证据），mid 恒定。README 榜单、docs/lists/by-creator、站点全部生效。
4. **封面字节不入库**（延续「不存储任何音视频字节」立场，扩展到图片）：
   - 站点侧热链 B站 图床，`<img referrerpolicy="no-referrer">` + `loading="lazy"`
     （B站图床对非常规 Referer 返回 403，no-referrer 为通行做法）；
   - README 不嵌图床图（GitHub camo 代理对 hdslb 常态 403）——README 的视觉升级
     走自托管 SVG 图表（后续时间线/开发度）。

## 后果

- 封面 URL 随 UP主 换封面而变化时，R8 会推动 entries 更新（这是特性：档案跟随一手状态）；
- 快照若未来做瘦身/轮转（仓库体积治理），cover 已固化在 entries 精编层，不随快照消失；
- 封面墙仅在站点呈现，仓库 git 历史保持零媒体字节。
