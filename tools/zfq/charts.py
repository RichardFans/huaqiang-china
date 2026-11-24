# -*- coding: utf-8 -*-
"""表现力图表（ADR-0008 修订二）：确定性 SVG，Python 字符串构建，零 JS。

两张图，讲同一份在册语料的两条故事线：
  1. 作品全景散点 works_scatter_svg：横轴发布时间 × 纵轴播放量（对数），每部作品一个点。
     引爆窗口（2021-07）着色月带、殿堂级名作直接标注、AI 系形态用菱形标记——
     引爆、长尾、2026 年 AI 再爆发一眼可见。
  2. 形态演化 form_evolution_svg：按季堆叠的形态构成（剪辑 / 鬼畜·音MAD / AI 系 / 其他），
     讲「这个梗的工业化」。

设计（dataviz 规范）：散点用桥段三色相 + 中性灰（任意两点口径已验证）；形态用独立三色
（蓝/橙/青，任意两点口径已验证，与桥段色不混用以免语义串色）；细网格发丝线、选择性直接
标注、单轴（散点 y 对数轴 + 年份刻度）；颜色走 CSS 变量并带字面量回退（README <img> 靠
内部媒体查询适配 GitHub 深色，站点内联跟随页面令牌）。

产物是 data 的纯函数（R11 逐字节比对）。
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .graph import OTHER_COLOR, SCENE_COLOR, scene_key
from .schema import Entry

INK, INK_DARK = "#1a1d1a", "#e9ece8"
MUTED, MUTED_DARK = "#66706a", "#96a098"
GRID, GRID_DARK = "#e3e7e2", "#2a302a"
BAND = ("#b93a32", "#e8607a")        # 引爆月带 = 品牌红（低透明度）
FONT = ("system-ui, -apple-system, 'Segoe UI', 'PingFang SC', "
        "'Microsoft YaHei', 'Noto Sans SC', sans-serif")

FORM_GROUP = {
    "clip": "edit", "guichu": "guichu", "yinmad": "guichu",
    "ai-cover": "ai", "ai-video": "ai", "ai-other": "ai",
    "other": "other", "source": "other",
}
FORM_GROUP_LABEL = {"edit": "剧情剪辑", "guichu": "鬼畜·音MAD", "ai": "AI 系", "other": "其他"}
FORM_GROUP_ORDER = ("edit", "guichu", "ai", "other")
# 与桥段色刻意不同色相（蓝/橙/青，dataviz 六检通过；浅色下青 2.82:1 以图例直接标注补偿）
FORM_COLOR = {
    "edit": ("#2a78d6", "#3987e5"),
    "guichu": ("#eb6834", "#d95926"),
    "ai": ("#1baf7a", "#199e70"),
}

_ZH_UNITS = [(1e8, "亿"), (1e4, "万")]


def _fmt_cn(v: float) -> str:
    for div, unit in _ZH_UNITS:
        if v >= div:
            s = f"{v / div:.0f}"
            return f"{s}{unit}"
    return f"{v:.0f}"


def _label_text(title: str, limit: int) -> str:
    t = re.sub(r"\s+", "", title or "").strip() or "(无标题)"
    return t if len(t) <= limit else t[:limit] + "…"


def _text_w(s: str, size: float) -> float:
    return sum(size * (1.0 if ord(ch) > 0x2E7F else 0.58) for ch in s)


# ---------------------------------------------------------------- 作品全景散点

def works_scatter_svg(entries: list[Entry], *, chrome: bool = True) -> str:
    works = [e for e in entries if e.kind == "derivative" and e.status == "ok"]
    works.sort(key=lambda e: (e.pubdate, e.bvid))
    n = len(works)
    W, H = 920, 470 if chrome else 420
    ML, MR, MT = 56, 18, 74 if chrome else 26
    MB = 34
    u = "scw"
    if not works:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
                f'width="{W}" height="{H}" role="img" aria-label="暂无在册作品"></svg>')

    def ts(e: Entry) -> float:
        return e.pubdate.timestamp()

    x0, x1 = ts(works[0]), ts(works[-1])
    span = max(x1 - x0, 86400.0 * 30)
    x0, x1 = x0 - span * 0.02, x1 + span * 0.02

    views = [e.latest.view if e.latest else 0 for e in works]
    vmax = max(max(views), 10)
    lo = math.floor(math.log10(max(min(v for v in views if v > 0), 10)))
    hi = math.ceil(math.log10(vmax))
    lo = min(lo, hi - 1)

    def X(t: float) -> float:
        return ML + (t - x0) / (x1 - x0) * (W - MR - ML)

    def Y(v: float) -> float:
        vv = max(v, 10)
        lv = (math.log10(vv) - lo) / (hi - lo)
        return H - MB - lv * (H - MB - MT)

    def color(e: Entry) -> str:
        k = scene_key(e.scenes)
        return (f"var(--sc-{k},{SCENE_COLOR[k][0]})" if k in SCENE_COLOR
                else f"var(--sc-other,{OTHER_COLOR[0]})")

    def dark(e: Entry) -> str:
        k = scene_key(e.scenes)
        return (f"var(--sc-{k},{SCENE_COLOR[k][1]})" if k in SCENE_COLOR
                else f"var(--sc-other,{OTHER_COLOR[1]})")

    s: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" class="{u}" role="img" aria-labelledby="{u}-t {u}-d">',
        f"<style>.{u}-t{{font-family:{FONT}}}",
        f".{u}-ink{{fill:var(--sc-ink,{INK})}}.{u}-mut{{fill:var(--sc-muted,{MUTED})}}",
        f".{u}-grid{{stroke:var(--sc-grid,{GRID});stroke-width:1}}",
        f".{u}-band{{fill:var(--sc-red,{BAND[0]});fill-opacity:.07}}",
        f".{u}-bandline{{stroke:var(--sc-red,{BAND[0]});stroke-width:1;"
        f"stroke-dasharray:3 3;fill:none}}",
        f".{u}-bandlab{{fill:var(--sc-red,{BAND[0]});font-weight:600}}",
        f".{u}-dot{{fill:var(--sc-fill,{BAND[0]})}}",
        "@media (prefers-color-scheme: dark){",
        f".{u}-ink{{fill:var(--sc-ink,{INK_DARK})}}",
        f".{u}-mut{{fill:var(--sc-muted,{MUTED_DARK})}}",
        f".{u}-grid{{stroke:var(--sc-grid,{GRID_DARK})}}",
        f".{u}-band{{fill:var(--sc-red,{BAND[1]});fill-opacity:.09}}",
        f".{u}-bandline{{stroke:var(--sc-red,{BAND[1]})}}",
        f".{u}-bandlab{{fill:var(--sc-red,{BAND[1]})}}",
        "}</style>",
        f'<title id="{u}-t">作品全景：发布时间与播放量（在册样本 {n} 部）</title>',
        f'<desc id="{u}-d">横轴为发布时间（2020 至今），纵轴为播放量（对数刻度）。'
        f'每部在册作品一个点：颜色为桥段，菱形为 AI 系形态，播放量最高的名作直接标注，'
        f'2021 年 7 月的着色月带为引爆窗口。</desc>',
    ]
    if chrome:
        s += [
            f'<text class="{u}-t {u}-ink" x="{ML}" y="24" font-size="15" font-weight="600">'
            f'作品全景：发布时间 × 播放量（在册样本 {n} 部）</text>',
            f'<text class="{u}-t {u}-mut" x="{ML}" y="44" font-size="11">'
            f'每点一部作品：颜色为桥段，菱形为 AI 系形态，纵轴对数。'
            f'在册样本偏向播放头部，长尾被系统性低估。</text>',
            f'<text class="{u}-t {u}-mut" x="{ML}" y="{H - 8}" font-size="9.5">'
            f'数据：仓库一手快照（CC BY-SA 4.0）· zfq build 确定性生成</text>',
        ]
    # 引爆月带（铺整月）
    import datetime as _dt

    band_t0 = _dt.datetime(2021, 7, 1, tzinfo=_dt.timezone.utc).timestamp()
    band_t1 = _dt.datetime(2021, 8, 1, tzinfo=_dt.timezone.utc).timestamp()
    bx0, bx1 = X(band_t0), X(band_t1)
    if bx1 > ML + 4:
        s.append(f'<rect class="{u}-band" x="{bx0:.1f}" y="{MT}" width="{bx1 - bx0:.1f}" '
                 f'height="{H - MB - MT}"/>')
        s.append(f'<line class="{u}-bandline" x1="{bx1:.1f}" y1="{MT}" x2="{bx1:.1f}" '
                 f'y2="{H - MB}"/>')
        # 标签放在图区顶线之上，避开高播放量名作的标注区（数据标注最低 y ≈ MT+40）
        lab_x = min(max((bx0 + bx1) / 2, 92), W - MR - 96)
        s.append(f'<text class="{u}-t {u}-bandlab" x="{lab_x:.1f}" y="{MT - 8}" '
                 f'font-size="11" text-anchor="middle">引爆窗口 2021-07</text>')
    # 网格 + 对数刻度
    for d in range(lo, hi + 1):
        v = 10 ** d
        y = Y(v)
        s.append(f'<line class="{u}-grid" x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}"/>')
        s.append(f'<text class="{u}-t {u}-mut" x="{ML - 8}" y="{y + 3.5:.1f}" '
                 f'font-size="10.5" text-anchor="end">{_fmt_cn(v)}</text>')
    s.append(f'<line class="{u}-grid" x1="{ML}" y1="{H - MB}" x2="{W - MR}" y2="{H - MB}" '
             f'stroke-width="1.4"/>')
    # 年份刻度
    years = sorted({e.pubdate.year for e in works})
    for yr in years:
        t = _dt.datetime(yr, 1, 1, tzinfo=_dt.timezone.utc).timestamp()
        x = X(t)
        if ML - 1 <= x <= W - MR + 1:
            s.append(f'<line class="{u}-grid" x1="{x:.1f}" y1="{H - MB}" x2="{x:.1f}" '
                     f'y2="{H - MB + 5}"/>')
            s.append(f'<text class="{u}-t {u}-mut" x="{x:.1f}" y="{H - MB + 18}" '
                     f'font-size="10.5" text-anchor="middle">{yr}</text>')
    # 数据点（后画覆盖网格）
    for e in works:
        v = e.latest.view if e.latest else 0
        x, y = X(ts(e)), Y(v)
        tip = (f"{e.title}\n{e.owner.name}　播放 {_fmt_cn(v)}　"
               f"{e.pubdate:%Y-%m-%d}")
        k = scene_key(e.scenes)
        sc = " ".join(dict.fromkeys(
            [x2 for x2 in e.scenes if x2 in SCENE_COLOR]
            + (["other"] if any(x2 not in SCENE_COLOR for x2 in e.scenes) else [])))
        fill = color(e)
        dfill = dark(e)
        ai = e.form.startswith("ai")
        r = 6.0 if e.tier == "hall" else (4.6 if e.tier == "hot" else 3.6)
        style = f"fill:{fill}"
        dsty = f"fill:{dfill}"
        common = (f'<g class="{u}-pt" data-scene="{sc}" data-id="bv:{e.bvid}" '
                  f'tabindex="0"><title>{tip}</title>')
        if ai:      # 菱形标记：AI 系形态（第二编码通道，形状不依赖色相）
            half = r * 1.25
            s.append(common +
                     f'<rect x="{x - half:.1f}" y="{y - half:.1f}" width="{half * 2:.1f}" '
                     f'height="{half * 2:.1f}" rx="1" transform="rotate(45 {x:.1f} {y:.1f})" '
                     f'style="{style}" data-dark="{dsty}"/></g>')
        else:
            s.append(f'{common}<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
                     f'style="{style}" data-dark="{dsty}"/></g>')
    # 选择性直接标注：播放量前 6
    top = sorted(works, key=lambda e: (-(e.latest.view if e.latest else 0), e.bvid))[:6]
    labeled_x: list[float] = []
    for i, e in enumerate(top):
        v = e.latest.view if e.latest else 0
        x, y = X(ts(e)), Y(v)
        text = _label_text(e.title, 8)
        w = _text_w(text, 11)
        right = x < W - MR - w - 26
        lx = x + 10 if right else x - 10
        anchor = "start" if right else "end"
        ly = y + (4 if i % 2 == 0 else -7)
        # 简单避让：与已标注 x 距离过近时上下错开
        for px in labeled_x:
            if abs(px - lx) < 30:
                ly += 13
                break
        labeled_x.append(lx)
        s.append(f'<text class="{u}-t {u}-ink" x="{lx:.1f}" y="{ly:.1f}" font-size="11" '
                 f'text-anchor="{anchor}">{text}</text>')
    s.append("</svg>")
    return "\n".join(s)


# ---------------------------------------------------------------- 形态演化

def _quarter(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def form_evolution_svg(entries: list[Entry], *, chrome: bool = True) -> str:
    works = [e for e in entries if e.kind == "derivative" and e.status == "ok"]
    u = "fev"
    W, H = 920, 300 if chrome else 244
    ML, MR, MT = 46, 18, 88 if chrome else 64
    MB = 34
    by_q: dict[str, Counter] = defaultdict(Counter)
    for e in works:
        by_q[_quarter(e.pubdate.strftime("%Y-%m"))][FORM_GROUP.get(e.form, "other")] += 1
    quarters = sorted(by_q)
    if not quarters:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
                f'width="{W}" height="{H}" role="img" aria-label="暂无数据"></svg>')
    # 补空季（相邻之间）保证时间轴等距
    def qrange(a: str, b: str):
        ya, qa = int(a[:4]), int(a[5])
        yb, qb = int(b[:4]), int(b[5])
        out, cur = [], (ya, qa)
        end = (yb, qb)
        while cur <= end:
            out.append(f"{cur[0]}Q{cur[1]}")
            cur = (cur[0] + 1, 1) if cur[1] == 4 else (cur[0], cur[1] + 1)
        return out

    qs = qrange(quarters[0], quarters[-1])
    totals = [sum(by_q[q].values()) if q in by_q else 0 for q in qs]
    ymax = max(totals)

    slot = (W - ML - MR) / len(qs)
    bar_w = max(3.0, slot - 3)
    scale = (H - MB - MT) / ymax

    s: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" class="{u}" role="img" aria-labelledby="{u}-t {u}-d">',
        f"<style>.{u}-t{{font-family:{FONT}}}",
        f".{u}-ink{{fill:var(--fe-ink,{INK})}}.{u}-mut{{fill:var(--fe-muted,{MUTED})}}",
        f".{u}-grid{{stroke:var(--fe-grid,{GRID});stroke-width:1}}",
    ]
    for g in FORM_GROUP_ORDER:
        light, darkc = FORM_COLOR.get(g, OTHER_COLOR)
        s.append(f".{u}-{g}{{fill:var(--fe-{g},{light})}}")
    s += [
        "@media (prefers-color-scheme: dark){",
        f".{u}-ink{{fill:var(--fe-ink,{INK_DARK})}}",
        f".{u}-mut{{fill:var(--fe-muted,{MUTED_DARK})}}",
        f".{u}-grid{{stroke:var(--fe-grid,{GRID_DARK})}}",
    ]
    for g in FORM_GROUP_ORDER:
        light, darkc = FORM_COLOR.get(g, OTHER_COLOR)
        s.append(f".{u}-{g}{{fill:var(--fe-{g},{darkc})}}")
    s.append("}</style>")
    n_total = sum(totals)
    s += [
        f'<title id="{u}-t">形态演化：季度投稿构成（在册样本 {n_total} 部）</title>',
        f'<desc id="{u}-d">按发布季度堆叠的形态构成：剧情剪辑、鬼畜与音MAD、'
        f'AI 系（翻唱、视频、其他）、其他。2026 年起 AI 系占比显著上升。</desc>',
    ]
    if chrome:
        s += [
            f'<text class="{u}-t {u}-ink" x="{ML}" y="24" font-size="15" font-weight="600">'
            f'形态演化：这个梗的工业化（季度构成，{n_total} 部）</text>',
            f'<text class="{u}-t {u}-mut" x="{ML}" y="44" font-size="11">'
            f'按发布季度堆叠的形态构成。AI 系（翻唱/视频/其他）自 2023 年出现，'
            f'2026 年成为主力之一——同一批名场面，换了新喉咙。</text>',
        ]
    # 图例（chrome 与 bare 都带：浅色下青色需直接标注补偿）
    lx = ML
    for g in FORM_GROUP_ORDER:
        label = FORM_GROUP_LABEL[g]
        s.append(f'<rect class="{u}-{g}" x="{lx:.1f}" y="{(58 if chrome else 18) + 1}" '
                 f'width="10" height="10" rx="2"/>')
        s.append(f'<text class="{u}-t {u}-mut" x="{lx + 15:.1f}" y="{(58 if chrome else 18) + 10}" '
                 f'font-size="11">{label}</text>')
        lx += 15 + _text_w(label, 11) + 22
    # 网格（横向 2~3 条）+ 左刻度
    step = 5 if ymax > 12 else (2 if ymax > 5 else 1)
    v = step
    while v < ymax + 0.01:
        y = H - MB - v * scale
        s.append(f'<line class="{u}-grid" x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}"/>')
        s.append(f'<text class="{u}-t {u}-mut" x="{ML - 7}" y="{y + 3.5:.1f}" '
                 f'font-size="10" text-anchor="end">{v}</text>')
        v += step
    s.append(f'<line class="{u}-grid" x1="{ML}" y1="{H - MB}" x2="{W - MR}" y2="{H - MB}" '
             f'stroke-width="1.4"/>')
    # 堆叠柱（段间 2px 表面色隙）+ 年份刻度
    for i, q in enumerate(qs):
        x = ML + slot * i + (slot - bar_w) / 2
        y_cur = H - MB
        counts = by_q.get(q, Counter())
        total = sum(counts.values())
        for g in FORM_GROUP_ORDER:
            c = counts.get(g, 0)
            if c <= 0:
                continue
            h = c * scale
            y_cur -= h
            s.append(f'<rect class="{u}-{g}" x="{x:.1f}" y="{y_cur + 1:.1f}" '
                     f'width="{bar_w:.1f}" height="{max(h - 2, 1):.1f}" rx="1.5">'
                     f'<title>{q} · {FORM_GROUP_LABEL[g]}：{c} 部（共 {total} 部）</title></rect>')
            y_cur -= 0  # 段间距用 height-1/y+1 实现
        if q.endswith("Q1") or i == 0:
            s.append(f'<text class="{u}-t {u}-mut" x="{x + bar_w / 2:.1f}" '
                     f'y="{H - MB + 17}" font-size="10.5" text-anchor="middle">{q[:4]}</text>')
    # 最高季直接标注
    imax = totals.index(max(totals))
    s.append(f'<text class="{u}-t {u}-mut" x="{ML + slot * imax + slot / 2:.1f}" '
             f'y="{H - MB - max(totals) * scale - 7:.1f}" font-size="10.5" '
             f'text-anchor="middle">{max(totals)} 部</text>')
    if chrome:
        s.append(f'<text class="{u}-t {u}-mut" x="{ML}" y="{H - 8}" font-size="9.5">'
                 f'数据：仓库一手快照（CC BY-SA 4.0）· zfq build 确定性生成</text>')
    s.append("</svg>")
    return "\n".join(s)
