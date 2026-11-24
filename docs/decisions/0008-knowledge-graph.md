# ADR-0008 · 知识图谱（deterministic graph）

- 状态：Accepted（2026-11-24）
- 背景：P2 阶段 3。图谱是门面差异点，但「画个图」最容易滑向臆造——本档案的图谱
  必须与数据管线同一纪律：**只从确定性字段建边，每条边可回溯证据**。

## 决策

1. 节点三类：`creator`（mid 恒定 ID）、`work`（bvid）、`scene`（桥段）。
2. 边四类（全部带 evidence 字段）：
   - `created`：creator→work，证据 = entries.owner（条目本体）；
   - `collaborated`：creator→work，证据 = 最新 view 快照 `data.staff`（合作联合投稿）；
   - `in_scene`：work→scene，证据 = scene_status + scene_evidence（ADR-0006 门控值）；
   - `reprinted`：work→work，证据 = entries.original_bvid。
3. 铁律：**禁止从标题臆造关系**；任何 LLM 参与的归类须先过评审门控（ADR-0006）
   才能进入本层——当前实现完全确定性，零 LLM。
4. 构建是 data+snapshots 的纯函数（不含时间戳）→ `R9` 门禁：graph.json 与按当前
   数据重建结果不一致即 CI FAIL（与 R7 同构的防漂移）。
5. 产物三件套：`data/curated/graph.json`（R9 对象）+ `graph.gexf`（Gephi 等网络分析
   工具可直接打开，供社区检测/离线研究）+ 站点 `/graph/` 页（ECharts force 布局，
   节点按类型着色，hover 显示证据链）。
6. 形态/年份不进 v1 图谱（时间维度由编年时间线承担，避免毛线球化）。

## 后果

- 图谱随数据自动更新（track/discover → build），无手工维护面；
- staff 仅存在于合作投稿快照（当前 3 例），边数少是**数据事实**，不是缺陷；
- gexf 导出使「UP主 合作社区检测」等研究可在库外一键复现。

## 修订（2026-11-24）：视图改为构建期确定性 SVG，合作边按平台语义重定义

上线前用真实数据渲染，对原决策做了三处修正。

1. **合作边的正确语义**（实测六个带 staff 的样本）：`data.staff[0]` 恒为投稿者本人
   （title="UP主"），其余成员的 title 是平台标注的角色（参演、剪辑、后期、配音、文案、填词、
   赞助商），name 才是昵称。初版把角色字样当成了节点名，还把投稿者连向自己的作品记成了
   「合作」。现规定：排除投稿者本人；`role` 取平台原字面量，不做推断；证据写明
   `view-snapshot:data.staff[title=<角色>]@<快照日期>`。
2. **弃用客户端力导向布局（ECharts），改为 `zfq build` 在构建期算出确定性 SVG**：
   - 力导向每次刷新结果都不同，无法纳入防漂移门禁；
   - 196 部作品全部连向 5 个桥段枢纽，画出来必然是毛线球；
   - 要多加载约 180KB（gzip）脚本，且无法进 README 当传播素材。
   - 布局算法「星座装箱」：每个创作者与作品的连通分量单独排好（单作品为哑铃，多作品为
     投稿者居中的星形），再按高度优先做货架装箱。无重叠，同数据同输出（R11）。
   - `in_scene` 边只保留在数据层（graph.json 与 gexf）；视图层用作品节点的颜色和图例筛选呈现。
3. **视图层用色收敛为三个色相加一个中性灰**：节点网络属于任意两点都可能相邻的图形式，
   色觉安全上限是三个色相；`zhengfu-other` 与 `crossover` 本就是「其他」桶，并入中性灰。
   色值在项目自己的表面色上按任意两点口径通过 dataviz 六检
   （浅色表面 #ffffff：#b93a32、#c98500、#6250d6；深色表面 #171b17：#e8607a、#c98500、#9085e9；
   中性灰 #8a9490 与 #8f978f）。测试 `test_site_graph_palette_in_sync` 守住 Python 回退值与站点 CSS 一致。
4. 新增门禁 `R11`：README 与站点各一份星图 SVG，必须与重建结果逐字节一致。
