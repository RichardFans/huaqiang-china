# -*- coding: utf-8 -*-
"""知识图谱（ADR-0008）：数据层（节点/边 + 证据链）与确定性视图（gexf / 创作者星图 SVG）。

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

桥段归属（in_scene）保留在数据层（graph.json / gexf）；视图层以作品节点的颜色 + 图例筛选
呈现、不画连线：桥段是超级枢纽，画出来必然是毛线球（见 ADR-0008 修订）。

铁律：禁止从标题臆造边；本模块完全确定性，零 LLM。构建是 data + snapshots 的纯函数（R9）。
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from xml.sax.saxutils import escape, quoteattr

from . import config
from .schema import Entry
from .track import load_entries

SCENE_LABEL_ZH = {
    "maigua": "华强买瓜", "song-laohu-banquet": "宋老虎请客", "feng-biao": "封彪桥段",
    "zhengfu-other": "其他征服名场面", "crossover": "跨素材联动",
}
# 视图层用色：三个命名桥段各一个色相，zhengfu-other 与 crossover 并入中性「其他」。
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

INK, INK_DARK = "#1a1d1a", "#e9ece8"
INK2, INK2_DARK = "#454c46", "#b7bfb7"
LINE, LINE_DARK = "#c5ccc5", "#3a423a"
SURFACE, SURFACE_DARK = "#ffffff", "#0d1117"   # 回退值面向 README（GitHub 页面底色）
FONT = ("system-ui, -apple-system, 'Segoe UI', 'PingFang SC', "
        "'Microsoft YaHei', 'Noto Sans SC', sans-serif")

_LINK_REL = ("created", "collaborated")


def scene_key(scenes: list[str]) -> str:
    """作品主桥段是否属于三个命名桥段，否则归「其他」。"""
    return scenes[0] if scenes and scenes[0] in SCENE_COLOR else "other"


def _scene_attr(scenes: list[str]) -> str:
    """节点/边的桥段筛选属性（空格分隔，供 CSS [data-scene~=x] 使用）。"""
    out = [s for s in scenes if s in SCENE_COLOR]
    if any(s not in SCENE_COLOR for s in scenes):
        out.append("other")
    return " ".join(dict.fromkeys(out))


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
        for slug in e.scenes:       # 数据层保留桥段归属边（视图层不画）
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
            "n_reprinted": sum(1 for e in edges if e["relation"] == "reprinted"),
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


# ---------------------------------------------------------------- 确定性布局

_RING = {2: 44, 3: 52, 4: 60, 5: 66, 6: 72, 7: 78, 8: 84}
LABEL_SIZE = 12                              # README 里整图缩到 880px 宽后约 8.8px


def _label_text(title: str, limit: int) -> str:
    t = re.sub(r"\s+", "", title or "").strip() or "(无标题)"
    return t if len(t) <= limit else t[:limit] + "…"


def _text_w(s: str, size: float = LABEL_SIZE) -> float:
    """文本宽度粗估：CJK/全角按 1em，其余按 0.58em。"""
    return sum(size * (1.0 if ord(ch) > 0x2E7F else 0.58) for ch in s)


def _work_radius(view: int) -> float:
    """作品节点半径：播放量的对数映射（1 千 → 4px，5000 万 → 约 15px）。"""
    return round(4 + 2.4 * math.log10(max(view, 1000) / 1000), 2)


def _mid_key(nid: str) -> tuple:
    return (-int(re.sub(r"\D", "", nid) or 0), nid)


def _layout_component(comp: list[str], nodes: dict[str, dict],
                      adj: dict[str, list[tuple[str, str]]]) -> dict | None:
    """单个连通分量（一个「星座」）的局部坐标与其外接框。"""
    creators = sorted(c for c in comp if nodes[c]["kind"] == "creator")
    works = sorted((w for w in comp if nodes[w]["kind"] == "work"),
                   key=lambda w: (-(nodes[w].get("view") or 0), w))
    if not works or not creators:
        return None
    out: dict = {"key": comp[0], "nodes": {}, "labels": [], "plate": ""}
    boxes: list[tuple[float, float, float, float]] = []

    def put(nid: str, x: float, y: float, r: float, shape: str) -> None:
        out["nodes"][nid] = {"x": x, "y": y, "r": r, "shape": shape}

    def label(nid: str, text: str, x: float, y: float, r: float,
              ux: float, uy: float) -> None:
        """沿 (ux, uy) 方向把标签放到节点之外；标签外接框并入分量外接框。"""
        w = _text_w(text)
        if ux >= 0.35:
            lx, ly, anchor = x + r + 5, y + 4, "start"
        elif ux <= -0.35:
            lx, ly, anchor = x - r - 5, y + 4, "end"
        elif uy < 0:
            lx, ly, anchor = x, y - r - 6, "middle"
        else:
            lx, ly, anchor = x, y + r + LABEL_SIZE + 3, "middle"
        x0 = lx if anchor == "start" else (lx - w if anchor == "end" else lx - w / 2)
        out["labels"].append({"for": nid, "x": lx, "y": ly, "text": text,
                              "anchor": anchor, "cls": ""})
        boxes.append((x0, ly - LABEL_SIZE, x0 + w, ly + 2.5))

    counts = Counter(nb for w in works for nb, _rel in adj[w]
                     if nodes[nb]["kind"] == "creator")
    anchor = max(creators, key=lambda c: (counts.get(c, 0), _mid_key(c)))
    solo = len(creators) == 1

    if len(works) == 1:                      # 哑铃：投稿者 - 作品（+ 合作者）
        w = works[0]
        wr = _work_radius(nodes[w].get("view") or 0)
        wx = 21 if solo else 4
        put(anchor, -21 if solo else -24, 0, 5, "creator")
        put(w, wx, 0, wr, "work")
        others = sorted((c for c in creators if c != anchor), key=_mid_key)
        for i, c in enumerate(others):
            put(c, wx + 32, -17 if i % 2 == 0 else 17, 5, "creator")
        if nodes[w].get("tier") == "hall":
            label(w, _label_text(nodes[w]["label"], 9), wx, 0, wr, 1, 0)
    else:                                    # 星座：投稿者居中，作品绕圈
        ac = counts.get(anchor, 0)
        radius = _RING.get(len(works), 36 + 6 * len(works))
        put(anchor, 0, 0, 6.5 if ac >= 3 else 5.5, "creator")
        placed: dict[str, tuple] = {}
        for i, w in enumerate(works):
            ang = -math.pi / 2 + 2 * math.pi * i / len(works)
            ux, uy = math.cos(ang), math.sin(ang)
            placed[w] = (radius * ux, radius * uy, ux, uy,
                         _work_radius(nodes[w].get("view") or 0))
            put(w, radius * ux, radius * uy, placed[w][4], "work")
        for w in works:
            x, y, ux, uy, wr = placed[w]
            for c, _rel in adj[w]:
                if nodes[c]["kind"] == "creator" and c != anchor:
                    put(c, x + 40 * ux, y + 40 * uy, 5, "creator")
            if nodes[w].get("tier") == "hall":
                label(w, _label_text(nodes[w]["label"], 9), x, y, wr, ux, uy)
        if ac >= 3:
            out["plate"] = _label_text(nodes[anchor]["label"], 10)
            out["plate_for"] = anchor

    for n in out["nodes"].values():
        boxes.append((n["x"] - n["r"] - 2, n["y"] - n["r"] - 2,
                      n["x"] + n["r"] + 2, n["y"] + n["r"] + 2))
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    if out["plate"]:
        out["plate_pos"] = (x0, y0 - 9)      # 星座铭牌：左上角、组件外，与下方标签留出空隙
        y0 -= LABEL_SIZE + 13
    pad = 12
    out["bbox"] = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    return out


def layout_graph(graph: dict, *, width: int = 1200, margin: int = 18,
                 gap: int = 12) -> dict:
    """确定性布局：每个连通分量单独排好，再按「高度优先」货架装箱。无重叠、可复算。"""
    nodes = {n["id"]: n for n in graph["nodes"]}
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in graph["edges"]:
        if e["relation"] in _LINK_REL:
            adj[e["source"]].append((e["target"], e["relation"]))
            adj[e["target"]].append((e["source"], e["relation"]))

    comps: list[list[str]] = []
    seen: set[str] = set()
    for nid in nodes:
        if nodes[nid]["kind"] != "creator" or nid in seen or not adj[nid]:
            continue
        stack, comp = [nid], []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.append(cur)
            stack.extend(sorted((nb for nb, _ in adj[cur] if nb not in seen), reverse=True))
        comps.append(sorted(comp))

    layouts = [L for L in (_layout_component(c, nodes, adj) for c in comps) if L]
    order = sorted(layouts, key=lambda L: (-(L["bbox"][3] - L["bbox"][1]),
                                           -(L["bbox"][2] - L["bbox"][0]), L["key"]))
    inner = width - 2 * margin
    x = y = row_h = 0.0
    for L in order:
        bx0, by0, bx1, by1 = L["bbox"]
        w, h = bx1 - bx0, by1 - by0
        if x > 0 and x + w > inner:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        L["shift"] = (margin + x - bx0, margin + y - by0)
        x += w + gap
        row_h = max(row_h, h)
    height = int(math.ceil(margin + y + row_h + margin))

    pos: dict[str, dict] = {}
    labels: list[dict] = []
    plates: list[dict] = []
    boxes: list[tuple[float, float, float, float]] = []
    for L in order:
        sx, sy = L["shift"]
        bx0, by0, bx1, by1 = L["bbox"]
        boxes.append((round(bx0 + sx, 1), round(by0 + sy, 1),
                      round(bx1 + sx, 1), round(by1 + sy, 1)))
        for nid, n in L["nodes"].items():
            pos[nid] = {"x": round(n["x"] + sx, 1), "y": round(n["y"] + sy, 1),
                        "r": n["r"], "shape": n["shape"]}
        for lab in L["labels"]:
            labels.append({**lab, "x": round(lab["x"] + sx, 1), "y": round(lab["y"] + sy, 1)})
        if L["plate"]:
            plates.append({"text": L["plate"], "for": L["plate_for"],
                           "x": round(L["plate_pos"][0] + sx, 1),
                           "y": round(L["plate_pos"][1] + sy, 1)})
    return {"width": width, "height": height, "pos": pos, "labels": labels,
            "plates": plates, "boxes": boxes, "components": len(order)}


# ---------------------------------------------------------------- SVG 视图

def _svg_style() -> str:
    def rules(idx: int) -> str:
        return "".join(f".cm-s-{k}{{fill:var(--cm-{k},{v[idx]})}}"
                       for k, v in SCENE_COLOR.items())
    return (
        "<style>"
        f".cm-t{{font-family:{FONT}}}"
        f".cm-e{{stroke:var(--cm-line,{LINE});stroke-width:1;fill:none}}"
        ".cm-e-collab{stroke-dasharray:3 3;stroke-width:1.4}"
        f".cm-l{{font-size:{LABEL_SIZE}px;fill:var(--cm-ink,{INK});paint-order:stroke;"
        f"stroke:var(--cm-surface,{SURFACE});stroke-width:3px;stroke-linejoin:round}}"
        ".cm-plate{font-weight:600}"
        f".cm-creator{{fill:var(--cm-ink2,{INK2})}}"
        f".cm-halo{{fill:none;stroke:var(--cm-surface,{SURFACE});stroke-width:2.4}}"
        f".cm-ring{{fill:none;stroke:var(--cm-ink,{INK});stroke-width:1.4}}"
        + rules(0) +
        f".cm-s-other{{fill:var(--cm-other,{OTHER_COLOR[0]})}}"
        "@media (prefers-color-scheme: dark){"
        f".cm-e{{stroke:var(--cm-line,{LINE_DARK})}}"
        f".cm-l{{fill:var(--cm-ink,{INK_DARK});stroke:var(--cm-surface,{SURFACE_DARK})}}"
        f".cm-creator{{fill:var(--cm-ink2,{INK2_DARK})}}"
        f".cm-halo{{stroke:var(--cm-surface,{SURFACE_DARK})}}"
        f".cm-ring{{stroke:var(--cm-ink,{INK_DARK})}}"
        + rules(1) +
        f".cm-s-other{{fill:var(--cm-other,{OTHER_COLOR[1]})}}"
        "}</style>")


def to_svg(graph: dict, *, width: int = 1200) -> str:
    """创作者星图（确定性 SVG）。README 作为 <img> 使用；站点内联后叠加交互。"""
    lay = layout_graph(graph, width=width)
    nodes = {n["id"]: n for n in graph["nodes"]}
    pos = lay["pos"]
    W, H = lay["width"], lay["height"]
    m = graph["meta"]

    def fmt(v: int) -> str:
        return f"{v:,}"

    s: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" class="cm" role="group" aria-labelledby="cm-t cm-d">',
        _svg_style(),
        '<title id="cm-t">征服二创创作者星图</title>',
        f'<desc id="cm-d">{m["n_creators"]} 位创作者、{m["n_works"]} 部在册作品、'
        f'{m["n_components"]} 个互不相连的创作单元。圆点为作品，大小随播放量、颜色为桥段；'
        f'菱形为创作者；虚线为平台标注的合作关系。</desc>',
        '<g class="cm-edges">',
    ]
    for e in graph["edges"]:
        if e["relation"] not in _LINK_REL or e["source"] not in pos or e["target"] not in pos:
            continue
        a, b = pos[e["source"]], pos[e["target"]]
        cls = "cm-e cm-e-collab" if e["relation"] == "collaborated" else "cm-e"
        s.append(f'<line class="{cls}" data-s="{e["source"]}" data-t="{e["target"]}" '
                 f'data-scene="{_scene_attr(nodes[e["target"]]["scenes"])}" '
                 f'x1="{a["x"]}" y1="{a["y"]}" x2="{b["x"]}" y2="{b["y"]}"/>')
    s.append('</g>')
    s.append('<g class="cm-nodes">')
    for nid in sorted(pos):
        n, p = nodes[nid], pos[nid]
        x, y, r = p["x"], p["y"], p["r"]
        sc = _scene_attr(n["scenes"])
        if n["kind"] == "work":
            tip = f"{n['label']}\n{n['owner']}　播放 {fmt(n.get('view') or 0)}　{n['pubdate']}"
            aria = f"{n['label']}，{n['owner']}，播放 {fmt(n.get('view') or 0)}"
            search = f"{n['owner']} {n['label']}"
        else:
            tip = f"{n['label']}\n在册作品 {n.get('works', 0)} 部"
            aria, search = n["label"], n["label"]
        common = (f'<a class="cm-n" href={quoteattr(n["url"])} target="_blank" '
                  f'rel="noopener" data-id="{nid}" data-scene="{sc}" '
                  f'data-search={quoteattr(search)} aria-label={quoteattr(aria)}>'
                  f'<title>{escape(tip)}</title>')
        if n["kind"] == "work":
            extra = ""
            if n.get("tier") == "hall":      # 殿堂级：留白圈 + 墨色外环
                extra = (f'<circle class="cm-halo" cx="{x}" cy="{y}" r="{round(r + 2.2, 1)}"/>'
                         f'<circle class="cm-ring" cx="{x}" cy="{y}" r="{round(r + 3.6, 1)}"/>')
            s.append(common + extra +
                     f'<circle class="cm-dot cm-s-{n["scene"]}" cx="{x}" cy="{y}" r="{r}"/></a>')
        else:
            half = round(r * 1.3, 2)
            s.append(f'{common}<rect class="cm-dot cm-creator" x="{round(x - half, 1)}" '
                     f'y="{round(y - half, 1)}" width="{round(half * 2, 1)}" '
                     f'height="{round(half * 2, 1)}" rx="1" '
                     f'transform="rotate(45 {x} {y})"/></a>')
    s.append('</g>')
    s.append('<g class="cm-labels">')
    for lab in lay["labels"]:
        s.append(f'<text class="cm-t cm-l" data-for="{lab["for"]}" '
                 f'data-scene="{_scene_attr(nodes[lab["for"]]["scenes"])}" '
                 f'x="{lab["x"]}" y="{lab["y"]}" text-anchor="{lab["anchor"]}">'
                 f'{escape(lab["text"])}</text>')
    for pl in lay["plates"]:
        s.append(f'<text class="cm-t cm-l cm-plate" data-for="{pl["for"]}" '
                 f'data-scene="{_scene_attr(nodes[pl["for"]]["scenes"])}" '
                 f'x="{pl["x"]}" y="{pl["y"]}">{escape(pl["text"])}</text>')
    s.append('</g>')
    s.append('</svg>')
    return "\n".join(s)
