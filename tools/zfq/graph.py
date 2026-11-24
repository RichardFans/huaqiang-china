# -*- coding: utf-8 -*-
"""知识图谱数据层（ADR-0008）：节点/边 + 证据链，gexf 导出。

节点三类：
  creator（id: mid:<mid>，label 取平台当前昵称）
  work    （id: bv:<bvid>，label 标题）
  scene   （id: scene:<slug>，仅数据层）

边三类（每条边带 evidence）：
  created       creator → work   证据 = entries.owner（条目本体）
  collaborated  creator → work   证据 = 最新 view 快照 data.staff（平台标注的合作角色）
  in_scene      work → scene     证据 = scene_status + scene_evidence（仅数据层）

staff 语义（2026-11-24 实测六个样本）：staff[0] 恒为投稿者本人（title="UP主"），其余成员的
title 是平台标注的角色（参演 / 剪辑 / 后期 / 配音 / 文案 / 填词 / 赞助商），name 是昵称。
因此**排除投稿者本人**，只把其余成员记为 collaborated，role 取平台原字面量，不做推断。

视图层见 zfq.charts（ADR-0008 修订二）：星座图已退役——在册创作者大多是「一人一片」的
哑铃结构，画出来信息量稀薄；公开页面改用作品全景散点与形态演化。关系数据保留在本层与
gexf 导出里，供网络分析（社区检测等）在库外复现。

铁律：禁止从标题臆造边；本模块完全确定性，零 LLM。构建是 data + snapshots 的纯函数（R9）。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from xml.sax.saxutils import escape, quoteattr

from . import config
from .schema import Entry
from .track import load_entries

SCENE_LABEL_ZH = {
    "maigua": "华强买瓜", "song-laohu-banquet": "宋老虎请客", "feng-biao": "封彪桥段",
    "zhengfu-other": "其他征服名场面", "crossover": "跨素材联动",
}
# 图表用色：三个命名桥段各一个色相，zhengfu-other 与 crossover 并入中性「其他」。
# 色值已过 dataviz 六检（任意两点口径；浅色表面 #ffffff / 深色表面 #171b17）：
# 节点网络属于任意两点都可能相邻的图形式，色觉安全上限是 3 个色相，多出的并入 Other。
# (浅色, 深色)
SCENE_COLOR: dict[str, tuple[str, str]] = {
    "maigua": ("#b93a32", "#e8607a"),
    "song-laohu-banquet": ("#c98500", "#c98500"),
    "feng-biao": ("#6250d6", "#9085e9"),
}
OTHER_COLOR = ("#8a9490", "#8f978f")
SCENE_ORDER = ("maigua", "song-laohu-banquet", "feng-biao", "zhengfu-other", "crossover")

_LINK_REL = ("created", "collaborated")


def scene_key(scenes: list[str]) -> str:
    """作品主桥段是否属于三个命名桥段，否则归「其他」。"""
    return scenes[0] if scenes and scenes[0] in SCENE_COLOR else "other"


def staff_from_snapshots(bvid: str, owner_mid: int) -> tuple[list[dict], str]:
    """合作成员（排除投稿者本人）。返回 (成员列表, 证据日期)，取最晚日期的 view 快照。"""
    for view_dir in sorted(config.SNAPSHOTS_DIR.glob("*/view"), reverse=True):
        p = view_dir / f"{bvid}.json"
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("code") != 0:
            continue
        day = view_dir.parent.name
        staff = (payload.get("data") or {}).get("staff") or []
        out = []
        for s in staff if isinstance(staff, list) else []:
            mid = s.get("mid")
            if not mid or mid == owner_mid:
                continue
            out.append({"mid": int(mid), "name": s.get("name") or f"mid:{mid}",
                        "role": s.get("title") or ""})
        return out, day
    return [], ""


def build_graph(entries: list[Entry] | None = None) -> dict:
    if entries is None:
        entries = load_entries()
    derivatives = [e for e in entries if e.kind == "derivative" and e.status == "ok"]

    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(nid: str, kind: str, label: str, **attrs) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "kind": kind, "label": label, **attrs}

    def creator_url(nid: str) -> str:
        return f"https://space.bilibili.com/{nid.split(':', 1)[1]}"

    for e in sorted(derivatives, key=lambda x: x.bvid):
        wid, cid = f"bv:{e.bvid}", f"mid:{e.owner.mid}"
        add_node(wid, "work", e.title, scenes=list(e.scenes), scene=scene_key(e.scenes),
                 tier=e.tier, view=e.latest.view if e.latest else 0,
                 pubdate=e.pubdate.strftime("%Y-%m"), owner=e.owner.name,
                 url=f"https://www.bilibili.com/video/{e.bvid}")
        add_node(cid, "creator", e.owner.name, url=creator_url(cid))
        edges.append({"source": cid, "target": wid, "relation": "created",
                      "role": "", "evidence": "entries.owner"})
        staff, day = staff_from_snapshots(e.bvid, e.owner.mid)
        for s in staff:
            sid = f"mid:{s['mid']}"
            add_node(sid, "creator", s["name"], url=creator_url(sid))
            edges.append({"source": sid, "target": wid, "relation": "collaborated",
                          "role": s["role"],
                          "evidence": f"view-snapshot:data.staff[title={s['role']}]@{day}"})
        for slug in e.scenes:       # 数据层保留桥段归属边
            edges.append({"source": wid, "target": f"scene:{slug}", "relation": "in_scene",
                          "role": "", "evidence": f"scene_status={e.scene_status}"
                                                  f"（{e.scene_evidence}）"})
        if e.original_bvid:
            edges.append({"source": wid, "target": f"bv:{e.original_bvid}",
                          "relation": "reprinted", "role": "",
                          "evidence": "entries.original_bvid"})
    for slug, zh in SCENE_LABEL_ZH.items():
        if any(x["relation"] == "in_scene" and x["target"] == f"scene:{slug}" for x in edges):
            add_node(f"scene:{slug}", "scene", zh)

    degree: Counter[str] = Counter()
    works_of: Counter[str] = Counter()
    scenes_of: dict[str, set[str]] = defaultdict(set)
    for ed in edges:
        if ed["relation"] in _LINK_REL:
            degree[ed["source"]] += 1
            degree[ed["target"]] += 1
            scenes_of[ed["source"]].add(nodes[ed["target"]]["scene"])
            scenes_of[ed["target"]].add(nodes[ed["target"]]["scene"])
            if ed["relation"] == "created":
                works_of[ed["source"]] += 1

    def scene_sort(s: str) -> int:
        return SCENE_ORDER.index(s) if s in SCENE_ORDER else 99

    for nid, n in nodes.items():
        if n["kind"] == "creator":
            n["degree"] = degree[nid]
            n["works"] = works_of[nid]
            n["scenes"] = sorted(scenes_of[nid], key=scene_sort) or ["other"]
    roles = Counter(x["role"] for x in edges if x["relation"] == "collaborated")
    return {
        "nodes": [nodes[k] for k in sorted(nodes)],
        "edges": sorted(edges, key=lambda d: (d["source"], d["target"], d["relation"])),
        "meta": {
            "n_nodes": len(nodes), "n_edges": len(edges),
            "n_creators": sum(1 for n in nodes.values() if n["kind"] == "creator"),
            "n_works": sum(1 for n in nodes.values() if n["kind"] == "work"),
            "n_serial": sum(1 for n in nodes.values()
                            if n["kind"] == "creator" and n.get("works", 0) >= 2),
            "n_collaborated": sum(1 for e in edges if e["relation"] == "collaborated"),
            "roles": dict(sorted(roles.items(), key=lambda kv: (-kv[1], kv[0]))),
            "n_components": _components(nodes, edges),
        },
    }


def _components(nodes: dict[str, dict], edges: list[dict]) -> int:
    """创作者-作品连通分量数（不含桥段节点）。"""
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e["relation"] in _LINK_REL:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
    seen: set[str] = set()
    n = 0
    for nid in nodes:
        if nid in seen or not adj[nid]:
            continue
        n += 1
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adj[cur] - seen)
    return n


# ---------------------------------------------------------------- gexf 导出

def to_gexf(graph: dict) -> str:
    """GEXF 1.3 导出（Gephi 等网络分析工具可直接打开，社区检测用）。"""
    ids = {n["id"]: i for i, n in enumerate(graph["nodes"])}
    node_attrs = ("kind", "scene", "scenes", "tier", "view", "pubdate", "owner", "works")
    edge_attrs = ("relation", "role", "evidence")
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<gexf xmlns="http://gexf.net/1.3" version="1.3">',
         '<creator>zfq build (ADR-0008)</creator>',
         '<description>Conquest remix graph: deterministic, evidence-chained</description>',
         '<graph defaultedgetype="directed">',
         '<attributes class="node">']
    L += [f'  <attribute id="{k}" title="{k}" type="string"/>' for k in node_attrs]
    L.append('</attributes>')
    L.append('<attributes class="edge">')
    L += [f'  <attribute id="{k}" title="{k}" type="string"/>' for k in edge_attrs]
    L += ['</attributes>', '<nodes>']
    for n in graph["nodes"]:
        atts = "".join(
            f'<attvalue for="{k}" value={quoteattr(str(n[k]))}/>'
            for k in node_attrs if k in n and n[k] not in (None, ""))
        L.append(f'  <node id="{ids[n["id"]]}" label={quoteattr(n["label"])}>'
                 f'<attvalues>{atts}</attvalues></node>')
    L += ['</nodes>', '<edges>']
    for i, e in enumerate(graph["edges"]):
        atts = "".join(f'<attvalue for="{k}" value={quoteattr(str(e[k])[:180])}/>'
                       for k in edge_attrs if e.get(k))
        L.append(f'  <edge id="{i}" source="{ids[e["source"]]}" target="{ids[e["target"]]}">'
                 f'<attvalues>{atts}</attvalues></edge>')
    L += ['</edges>', '</graph>', '</gexf>']
    return "\n".join(L) + "\n"
