# -*- coding: utf-8 -*-
"""引爆时间线（README hero + 站点内联图，ADR-0008 §7）：确定性 SVG，Python 字符串构建，零 JS。

设计（dataviz 规范落地）：
  - 形态：单序列月度柱状（密度故事）；单色系（品牌红），引爆月实心 + 直接标注；
  - 细柱 + 2px 间隙、顶端圆角、基线锚定、无网格、年份刻度、选择性直接标注；
  - 颜色走 CSS 变量并带字面量回退：README 里作为 <img> 使用（内部
    prefers-color-scheme 媒体查询适配 GitHub 深色模式）；站点内联时跟随页面令牌；
  - 口径说明内嵌（在册样本有发现偏差，不冒充分期结论）。

变体：
  wide + chrome   README hero（自带标题/口径/脚注）
  wide + bare     站点内联（标题与口径由页面 HTML 承担）
  compact + bare  站点移动端内联（字号不被缩到不可读）

产物是 data 的纯函数：同输入同输出（R10 门禁逐字节比对）。
"""
from __future__ import annotations

from collections import Counter

from .schema import Entry

IGNITION_MONTH = "2021-07"  # 一手 pubdate 实证窗口（methodology.md H1，非臆断）
IGNITION_LABEL = "引爆窗口 2021-07-16 至 07-19"

INK, INK_DARK = "#1a1d1a", "#e9ece8"
MUTED, MUTED_DARK = "#66706a", "#96a098"
LINE, LINE_DARK = "#c5ccc5", "#3a423a"
RED, RED_DARK = "#b93a32", "#e8607a"
FONT = ("system-ui, -apple-system, 'Segoe UI', 'PingFang SC', "
        "'Microsoft YaHei', 'Noto Sans SC', sans-serif")


def month_series(entries: list[Entry]) -> list[dict]:
    """在册二创按 pubdate 月度聚合计数（确定性：按月排序，空月补零桶）。"""
    derivatives = [e for e in entries if e.kind == "derivative" and e.status == "ok"]
    c: Counter[str] = Counter(e.pubdate.strftime("%Y-%m") for e in derivatives)
    if not c:
        return []
    months = sorted(c)
    lo, hi = months[0], months[-1]
    y, m = int(lo[:4]), int(lo[5:7])
    out = []
    while True:
        mo = f"{y:04d}-{m:02d}"
        out.append({"month": mo, "count": c.get(mo, 0), "ignition": mo == IGNITION_MONTH})
        if mo == hi:
            return out
        m += 1
        if m > 12:
            y, m = y + 1, 1


def _bar_path(x: float, y: float, w: float, h: float, r: float = 2.0) -> str:
    """顶端圆角、底端锚定基线的柱。"""
    r = max(0.0, min(r, w / 2, h))
    b = y + h
    if r <= 0.2:
        return f"M{x:.1f},{b:.1f}V{y:.1f}H{x + w:.1f}V{b:.1f}Z"
    return (f"M{x:.1f},{b:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f},{x + r:.1f},{y:.1f}"
            f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f},{x + w:.1f},{y + r:.1f}V{b:.1f}Z")


def _style(u: str) -> str:
    return (
        f"<style>"
        f".{u}-t{{font-family:{FONT}}}"
        f".{u}-ink{{fill:var(--tl-ink,{INK})}}.{u}-mut{{fill:var(--tl-muted,{MUTED})}}"
        f".{u}-bar{{fill:var(--tl-red,{RED})}}.{u}-line{{stroke:var(--tl-line,{LINE})}}"
        f".{u}-red{{fill:var(--tl-red,{RED})}}"
        f".{u}-g:hover .{u}-bar,.{u}-g:focus .{u}-bar{{opacity:1}}"
        f"@media (prefers-color-scheme: dark){{"
        f".{u}-ink{{fill:var(--tl-ink,{INK_DARK})}}"
        f".{u}-mut{{fill:var(--tl-muted,{MUTED_DARK})}}"
        f".{u}-bar{{fill:var(--tl-red,{RED_DARK})}}.{u}-red{{fill:var(--tl-red,{RED_DARK})}}"
        f".{u}-line{{stroke:var(--tl-line,{LINE_DARK})}}}}"
        f"</style>")


def build_timeline_svg(entries: list[Entry], *, variant: str = "wide",
                       chrome: bool = True) -> str:
    rows = month_series(entries)
    n_total = sum(r["count"] for r in rows)
    wide = variant == "wide"
    u = "tlw" if wide else "tlc"
    if wide:
        W, H = 920, (318 if chrome else 226)       # chrome：底部另留三行脚注的位置
        ML = MR = 14
        top, baseline = (92, H - 76) if chrome else (50, H - 34)
    else:
        W, H = 400, 214
        ML = MR = 8
        top, baseline, chrome = 44, H - 30, False

    plot_w = W - ML - MR
    m = len(rows) or 1
    slot = plot_w / m
    bar_w = max(2.0, slot - 2)
    max_y = max((r["count"] for r in rows), default=1)
    scale = (baseline - top) / max_y

    s: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" class="{u}" role="img" aria-labelledby="{u}-t {u}-d">',
        _style(u),
        f'<title id="{u}-t">华强二创投稿密度时间线（月度，在册样本 {n_total} 条）</title>',
        f'<desc id="{u}-d">2020 年至今在册二创按发布月聚合，共 {n_total} 条；'
        f'2021 年 7 月 16 至 19 日为一手 pubdate 实证的引爆窗口。</desc>',
    ]
    if chrome:
        s.append(f'<text class="{u}-t {u}-ink" x="{ML}" y="24" font-size="15" '
                 f'font-weight="600">华强二创投稿密度（月度，在册样本 {n_total} 条）</text>')
        s.append(f'<text class="{u}-t {u}-mut" x="{ML}" y="44" font-size="11">'
                 f'按一手 pubdate 聚合。实心柱为 2021-07 引爆窗口：四天内名作密集出现。'
                 f'在册样本偏向播放头部，不作为分期结论。</text>')
        s.append(f'<text class="{u}-t {u}-mut" x="{ML}" y="{H - 32}" font-size="9.5">'
                 f'数据：仓库一手快照（CC BY-SA 4.0）</text>')
        s.append(f'<text class="{u}-t {u}-mut" x="{ML}" y="{H - 20}" font-size="9.5">'
                 f'图由 zfq build 确定性生成，口径见 docs/methodology.md</text>')
        s.append(f'<text class="{u}-t {u}-mut" x="{ML}" y="{H - 8}" font-size="9.5">'
                 f'The Conquest Remix Archive　richardfans.github.io/huaqiang-china</text>')

    # 基线
    s.append(f'<line class="{u}-line" x1="{ML}" y1="{baseline}" x2="{W - MR}" '
             f'y2="{baseline}" stroke-width="1"/>')

    # 年份刻度：每个年份组居中标注
    i = 0
    while i < len(rows):
        j = i
        while j + 1 < len(rows) and rows[j + 1]["month"][:4] == rows[i]["month"][:4]:
            j += 1
        x0, x1 = ML + slot * i, ML + slot * (j + 1)
        s.append(f'<line class="{u}-line" x1="{x0:.1f}" y1="{baseline}" x2="{x0:.1f}" '
                 f'y2="{baseline + 4}" stroke-width="1"/>')
        s.append(f'<text class="{u}-t {u}-mut" x="{(x0 + x1) / 2:.1f}" y="{baseline + 16}" '
                 f'font-size="10.5" text-anchor="middle">{rows[i]["month"][:4]}</text>')
        i = j + 1
    s.append(f'<line class="{u}-line" x1="{W - MR:.1f}" y1="{baseline}" x2="{W - MR:.1f}" '
             f'y2="{baseline + 4}" stroke-width="1"/>')

    # 柱（含悬停提示）
    tops: list[tuple[float, float, float]] = []     # (x0, x1, top_y)
    ign = None
    for idx, r in enumerate(rows):
        if r["count"] <= 0:
            continue
        x = ML + slot * idx + (slot - bar_w) / 2
        h = max(2.0, r["count"] * scale)
        y = baseline - h
        tops.append((x, x + bar_w, y))
        if r["ignition"]:
            ign = (x + bar_w / 2, y, r["count"])
        cls = f"{u}-g" if r["ignition"] else f"{u}-g"
        op = "" if r["ignition"] else ' opacity="0.5"'
        s.append(f'<g class="{cls}" tabindex="0"><title>{r["month"]}：{r["count"]} 条</title>'
                 f'<path class="{u}-bar"{op} d="{_bar_path(x, y, bar_w, h)}"/></g>')

    # 选择性直接标注：引爆月（必标）+ 最高月（若不是引爆月）
    half = 78 if wide else 44
    if ign:
        cx, y, cnt = ign
        lx = min(max(cx, ML + half), W - MR - half)
        near = [t[2] for t in tops if t[1] >= lx - half and t[0] <= lx + half] or [y]
        y2 = min(near) - 9
        if wide:
            s.append(f'<text class="{u}-t {u}-red" x="{lx:.1f}" y="{y2 - 14:.1f}" font-size="11" '
                     f'font-weight="600" text-anchor="middle">'
                     f'{IGNITION_LABEL}</text>')
            s.append(f'<text class="{u}-t {u}-ink" x="{lx:.1f}" y="{y2:.1f}" font-size="11" '
                     f'text-anchor="middle">{cnt} 条</text>')
        else:
            s.append(f'<text class="{u}-t {u}-red" x="{lx:.1f}" y="{y2 - 13:.1f}" font-size="11" '
                     f'font-weight="600" text-anchor="middle">'
                     f'2021-07 引爆</text>')
    max_row = max(rows, key=lambda r: r["count"]) if rows else None
    if wide and max_row and not max_row["ignition"] and ign:
        idx = rows.index(max_row)
        cx = ML + slot * idx + slot / 2
        s.append(f'<text class="{u}-t {u}-mut" x="{cx:.1f}" y="{baseline - max_row["count"] * scale - 6:.1f}" '
                 f'font-size="10.5" text-anchor="middle">{max_row["count"]} 条</text>')

    s.append('</svg>')
    return "\n".join(s)
