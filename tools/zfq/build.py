# -*- coding: utf-8 -*-
"""构建层：从 data/entries + creators + deltas 生成切面视图、链接列表、站点数据与订阅源。

构建必须是 data 的**纯函数**：同输入同输出（tests 校验确定性）。
生成物：data/curated/*、docs/lists/*、site/src/data/generated/*、site/public/feeds/*。
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import timezone
from email.utils import format_datetime
from xml.etree import ElementTree as ET

from . import config
from .schema import Entry, iso, utcnow
from .track import load_entries

SCENE_ZH = {
    "maigua": "华强买瓜", "song-laohu-banquet": "宋老虎请客", "feng-biao": "封彪桥段",
    "zhengfu-other": "其他征服名场面", "crossover": "跨素材联动",
}
FORM_ZH = {
    "source": "原片段/素材", "clip": "剧情剪辑", "guichu": "鬼畜调教", "yinmad": "音MAD",
    "ai-cover": "AI翻唱/语音克隆", "ai-video": "AI视频生成", "ai-other": "AI其他", "other": "其他",
}
TIER_ZH = {"hall": "殿堂级", "hot": "热门", "rising": "新晋", "seed": "种子"}
SITE_URL = "https://richardfans.github.io/huaqiang-china"  # GitHub Pages 项目页（与 site/astro.config.mjs 同步）


def _slim(e: Entry) -> dict:
    s = e.latest
    return {
        "bvid": e.bvid, "title": e.title, "url": e.url,
        "owner": {"mid": e.owner.mid, "name": e.owner.name},
        "cover": e.cover,
        "pubdate": iso(e.pubdate),
        "kind": e.kind, "scenes": e.scenes, "form": e.form, "tier": e.tier,
        "scene_status": e.scene_status, "form_status": e.form_status,
        "review": e.review,
        "status": e.status, "archive_url": e.archive_url,
        "first_seen": iso(e.first_seen),
        "latest": {"captured_at": iso(s.captured_at), "view": s.view, "like": s.like,
                   "coin": s.coin, "favorite": s.favorite, "share": s.share,
                   "danmaku": s.danmaku} if s else None,
    }


def build_curated(entries: list[Entry]) -> dict:
    derivatives = [e for e in entries if e.kind == "derivative"]
    by_scene: dict[str, list] = defaultdict(list)
    by_form: dict[str, list] = defaultdict(list)
    by_tier: dict[str, list] = defaultdict(list)
    by_creator: dict[int, list] = defaultdict(list)
    by_year: dict[str, list] = defaultdict(list)
    for e in derivatives:
        slim = _slim(e)
        for s in e.scenes:
            by_scene[s].append(slim)
        by_form[e.form].append(slim)
        by_tier[e.tier].append(slim)
        by_creator[e.owner.mid].append(slim)
        by_year[e.pubdate.astimezone(timezone.utc).year].append(slim)

    def sort_v(d: dict) -> dict:
        return {k: sorted(v, key=lambda x: -(x["latest"]["view"] if x["latest"] else 0))
                for k, v in d.items()}

    curated = {
        "generated_at": iso(utcnow().replace(microsecond=0)),
        "counts": {
            "total": len(entries), "derivative": len(derivatives),
            "source": len(entries) - len(derivatives),
            "scenes": {k: len(v) for k, v in sort_v(by_scene).items()},
        },
        "by-scene": sort_v(by_scene), "by-form": sort_v(by_form),
        "by-tier": sort_v(by_tier), "by-creator": sort_v(by_creator),
        "by-year": sort_v(by_year),
    }
    config.CURATED_DIR.mkdir(parents=True, exist_ok=True)
    (config.CURATED_DIR / "views.json").write_text(
        json.dumps(curated, ensure_ascii=False, indent=2), encoding="utf-8")
    return curated


def build_lists_md(curated: dict) -> None:
    """GitHub 上可直接浏览的多切面链接列表（docs/lists/）。"""
    base = config.ROOT / "docs" / "lists"
    base.mkdir(parents=True, exist_ok=True)

    def fmt(x: dict) -> str:
        v = x["latest"]["view"] if x["latest"] else 0
        return (f"- [{x['title']}]({x['url']}) ｜ {x['owner']['name']} ｜ "
                f"{x['pubdate'][:10]} ｜ 播放 {v:,} ｜ {TIER_ZH[x['tier']]} ｜ "
                f"{FORM_ZH[x['form']]}")

    for slug, zh in SCENE_ZH.items():
        rows = curated["by-scene"].get(slug, [])
        (base / f"scene-{slug}.md").write_text(
            f"# 桥段：{zh}\n\n> 自动生成（zfq build），勿手改。\n\n"
            + "\n".join(fmt(x) for x in rows) + "\n", encoding="utf-8")

    lines = ["# 按 UP 主", "", "> 自动生成（zfq build），勿手改。", ""]
    for mid, rows in sorted(curated["by-creator"].items(),
                            key=lambda kv: -len(kv[1])):
        lines.append(
            f"## [{rows[0]['owner']['name']}]"
            f"(https://space.bilibili.com/{mid})（mid:{mid}，{len(rows)} 条）")
        lines += [fmt(x) for x in rows]
        lines.append("")
    (base / "by-creator.md").write_text("\n".join(lines), encoding="utf-8")

    lines = ["# 按热度分级", "", "> 自动生成（zfq build），勿手改。", ""]
    for t in ("hall", "hot", "rising", "seed"):
        rows = curated["by-tier"].get(t, [])
        lines.append(f"## {TIER_ZH[t]}（{len(rows)}）")
        lines += [fmt(x) for x in rows]
        lines.append("")
    (base / "by-tier.md").write_text("\n".join(lines), encoding="utf-8")


def build_site_data(curated: dict, creators: list[dict]) -> None:
    d = config.SITE_DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / "views.json").write_text(
        json.dumps(curated, ensure_ascii=False), encoding="utf-8")
    (d / "creators.json").write_text(
        json.dumps(creators, ensure_ascii=False), encoding="utf-8")
    deltas_path = config.CURATED_DIR / "deltas.json"
    if deltas_path.exists():
        (d / "deltas.json").write_text(deltas_path.read_text(encoding="utf-8"),
                                       encoding="utf-8")


def _rss_item(parent: ET.Element, title: str, link: str, guid: str,
              pub_iso: str, desc: str) -> None:
    it = ET.SubElement(parent, "item")
    ET.SubElement(it, "title").text = title
    ET.SubElement(it, "link").text = link
    ET.SubElement(it, "guid").text = guid
    ET.SubElement(it, "description").text = desc
    from datetime import datetime
    dt = datetime.fromisoformat(pub_iso)
    ET.SubElement(it, "pubDate").text = format_datetime(dt)


def build_feeds(curated: dict) -> None:
    fd = config.SITE_FEEDS_DIR
    fd.mkdir(parents=True, exist_ok=True)

    def rss(title: str, link: str, desc: str, items: list[tuple]) -> str:
        rss_el = ET.Element("rss", version="2.0")
        ch = ET.SubElement(rss_el, "channel")
        ET.SubElement(ch, "title").text = title
        ET.SubElement(ch, "link").text = link
        ET.SubElement(ch, "description").text = desc
        for t, l, g, p, d in items:
            _rss_item(ch, t, l, g, p, d)
        ET.indent(rss_el, space="  ")
        return ET.tostring(rss_el, encoding="unicode", xml_declaration=False)

    newest = sorted(
        (x for x in _flat_derivative(curated) if x["status"] == "ok"),
        key=lambda x: x["first_seen"], reverse=True)[:30]

    def item_desc(x: dict) -> str:
        s = x["latest"]
        v = f"播放 {s['view']:,}｜赞 {s['like']:,}｜币 {s['coin']:,}" if s else ""
        scenes = "、".join(SCENE_ZH[s] for s in x["scenes"])
        return f"{scenes}｜{FORM_ZH[x['form']]}｜{x['owner']['name']}｜{v}"

    zh_items = [(f"【{TIER_ZH[x['tier']]}】{x['title']}", x["url"], x["bvid"],
                 x["first_seen"], item_desc(x)) for x in newest]
    (fd / "new.rss.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + rss(f"{config.SITE_TITLE_ZH} · 新收录", SITE_URL + "/",
              "《征服》二创宇宙档案：最新入册条目", zh_items), encoding="utf-8")

    en_items = [(f"[{TIER_ZH[x['tier']]}] {x['title']} — {x['owner']['name']}",
                 x["url"], x["bvid"], x["first_seen"],
                 "The Conquest (2003) remix archive · " + item_desc(x))
                for x in newest]
    (fd / "new.en.rss.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + rss(f"{config.SITE_TITLE_EN} · New entries", SITE_URL + "/",
              "Newly catalogued derivative works of The Conquest (2003)", en_items),
        encoding="utf-8")

    # 涨幅榜 feed（数据来自 deltas.json）
    movers = []
    dp = config.CURATED_DIR / "deltas.json"
    if dp.exists():
        movers = json.loads(dp.read_text(encoding="utf-8"))["rows"][:20]
    mv_items = [(f"↑{r.get('growth_7d') or 0:,} 《{r['title'][:38]}》",
                 f"https://www.bilibili.com/video/{r['bvid']}",
                 r["bvid"], curated["generated_at"],
                 f"播放 {r['view']:,}｜7d +{r.get('growth_7d') or 0:,}"
                 f"｜30d +{r.get('growth_30d') or 0:,}") for r in movers]
    (fd / "movers.rss.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + rss(f"{config.SITE_TITLE_ZH} · 周涨幅榜", SITE_URL + "/",
              "7 天播放增量排行（跟踪管线自动生成）", mv_items), encoding="utf-8")

    # Atom
    feed = ET.Element("feed", xmlns="http://www.w3.org/2005/Atom")
    ET.SubElement(feed, "title").text = config.SITE_TITLE_ZH
    ET.SubElement(feed, "id").text = SITE_URL + "/"
    ET.SubElement(feed, "updated").text = curated["generated_at"]
    for t, l, g, p, d in zh_items:
        en = ET.SubElement(feed, "entry")
        ET.SubElement(en, "title").text = t
        ET.SubElement(en, "id").text = g
        ET.SubElement(en, "updated").text = p
        ET.SubElement(en, "link", href=l)
        ET.SubElement(en, "summary").text = d
    ET.indent(feed, space="  ")
    (fd / "atom.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(feed, encoding="unicode"),
        encoding="utf-8")

    # JSON Feed（英文模板）
    jf = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": f"{config.SITE_TITLE_EN} · New entries",
        "home_page_url": SITE_URL + "/",
        "feed_url": SITE_URL + "/feeds/feed.json",
        "language": "zh-CN",
        "items": [
            {"id": x["bvid"], "url": x["url"], "title": x["title"],
             "content_text": "The Conquest (2003) remix · " + item_desc(x),
             "date_published": x["first_seen"]}
            for x in newest],
    }
    (fd / "feed.json").write_text(json.dumps(jf, ensure_ascii=False, indent=2),
                                  encoding="utf-8")


def _flat_derivative(curated: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for rows in curated["by-form"].values():
        for x in rows:
            seen.setdefault(x["bvid"], x)
    return list(seen.values())


# ---- README 生成（榜单必须是数据管线的产物，CI R7 防漂移）----

SCENE_EN = {
    "maigua": "Watermelon scene", "song-laohu-banquet": "Banquet scene",
    "feng-biao": "Feng Biao scenes", "zhengfu-other": "Other scenes",
    "crossover": "Crossover",
}
FORM_EN = {
    "source": "Source clip", "clip": "Fan edit", "guichu": "Guichu", "yinmad": "Yin-MAD",
    "ai-cover": "AI cover", "ai-video": "AI video", "ai-other": "AI (other)", "other": "Other",
}
TIER_EN = {"hall": "Hall of Fame", "hot": "Hot", "rising": "Rising", "seed": "Seed"}
README_MARK_BEGIN = "<!-- zfq:generated:start -->"
README_MARK_END = "<!-- zfq:generated:end -->"
README_TEMPLATES = {
    "zh": config.ROOT / "tools" / "templates" / "README.zh.md",
    "en": config.ROOT / "tools" / "templates" / "README.en.md",
}
README_OUTPUTS = {
    "zh": config.ROOT / "README.md",
    "en": config.ROOT / "README.en.md",
}


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def _readme_table(rows: list[dict], lang: str) -> list[str]:
    zh = lang == "zh"
    head = (["| # | 作品 | UP主 | 发布 | 播放 | 硬币 | 形态 | 桥段 |",
             "|---|---|---|---|---|---|---|---|"] if zh else
            ["| # | Work | Creator | Published | Views | Coins | Form | Scene |",
             "|---|---|---|---|---|---|---|---|"])
    out = []
    for i, x in enumerate(rows, 1):
        s = x["latest"]
        view = f"{s['view']:,}" if s else "—"
        coin = f"{s['coin']:,}" if s else "—"
        form = FORM_ZH[x["form"]] if zh else FORM_EN[x["form"]]
        scenes = "、".join(SCENE_ZH[k] for k in x["scenes"]) if zh else \
            " / ".join(SCENE_EN[k] for k in x["scenes"])
        flag = " ⚠" if x["review"] != "confirmed" else ""
        dead = "（已失效）" if zh and x["status"] != "ok" else (" (gone)" if x["status"] != "ok" else "")
        owner = (f"[{x['owner']['name']}]"
                 f"(https://space.bilibili.com/{x['owner']['mid']})")
        out.append(
            f"| {i} | [{_md_escape(x['title'])}]({x['url']}){flag}{dead} "
            f"| {owner} | {x['pubdate'][:7]} | {view} | {coin} "
            f"| {form} | {scenes} |")
    return head + out


def _readme_block(curated: dict, lang: str) -> str:
    zh = lang == "zh"
    rows = [x for x in _flat_derivative(curated) if x["status"] == "ok"]
    by_view = sorted(rows, key=lambda x: -(x["latest"]["view"] if x["latest"] else 0))
    tiers = curated["counts"].get("scenes", {})
    n = curated["counts"]["derivative"]
    tier_n = {t: len(curated["by-tier"].get(t, [])) for t in ("hall", "hot", "rising", "seed")}
    reviewed = sum(1 for x in rows if x["review"] == "confirmed")
    pending = n - reviewed
    date = curated["generated_at"][:10]

    parts: list[str] = []
    dev = curated.get("development") or {}
    if zh:
        parts.append(
            f"**在册 {n} 条二创**（殿堂 {tier_n['hall']} · 热门 {tier_n['hot']} · "
            f"新晋 {tier_n['rising']} · 种子 {tier_n['seed']}）｜ 人工复核 {reviewed} · "
            f"待复核 {pending}（⚠）｜ 数据快照 {date}（UTC）")
        cap = dev.get("cap") or config.SEARCH_RESULTS_CAP
        if dev.get("ratio_pct") is not None:
            parts.append(
                "> 民间口径：人类对华强的开发不足 0.1%。本档案可复算口径的勘探进度为 "
                f"**{dev['ratio_pct']}%**（在册 {dev['numerator']} 条，检索探明 "
                f"{dev['denominator']:,} 条，"
                "[ADR-0009](docs/decisions/0009-development-metric.md)）")
        elif dev.get("capped"):
            parts.append(
                "> 民间口径：人类对华强的开发不足 0.1%。本档案想算一个可复算的版本，"
                f"结果撞上天花板：平台检索每个关键词最多只给看 {cap:,} 条"
                f"（{dev.get('keywords_observed', 0)} 个关键词实测封顶）。分母不可知，"
                f"账面已入册 {dev['numerator']} 条，照记不误"
                "（[ADR-0009](docs/decisions/0009-development-metric.md)）")
        else:
            parts.append(
                "> 勘探进度：勘探中（检索清单暂缺 numResults，"
                "[ADR-0009](docs/decisions/0009-development-metric.md)）")
        parts.append("")
        parts.append(f"## 🏆 殿堂级总榜（播放 ≥ 1000 万，共 {tier_n['hall']} 条）")
        parts += _readme_table([x for x in by_view if x["tier"] == "hall"], "zh")
        for slug, zh_name, emoji in (("maigua", "华强买瓜", "🍉"),
                                     ("song-laohu-banquet", "宋老虎请客", "🍜"),
                                     ("feng-biao", "封彪桥段", "🔪")):
            scene_rows = curated["by-scene"].get(slug, [])
            top = sorted(scene_rows, key=lambda x: -(x["latest"]["view"] if x["latest"] else 0))[:10]
            label = f"Top 10" if len(scene_rows) > 10 else f"全部 {len(scene_rows)} 条"
            parts.append("")
            parts.append(f"## {emoji} {zh_name} · {label}")
            parts += _readme_table(top, "zh")
            if len(scene_rows) > 10:
                parts.append("")
                parts.append(
                    f"→ 全部 {len(scene_rows)} 条：[docs/lists/scene-{slug}.md](docs/lists/scene-{slug}.md)"
                    f" ｜ [站点切面]({SITE_URL}/scene/{slug}/)")
    else:
        parts.append(
            f"**{n} derivative works catalogued** (Hall {tier_n['hall']} · Hot {tier_n['hot']} · "
            f"Rising {tier_n['rising']} · Seed {tier_n['seed']}) ｜ Human-reviewed {reviewed} · "
            f"Pending {pending} (⚠) ｜ Data snapshot {date} (UTC)")
        cap = dev.get("cap") or config.SEARCH_RESULTS_CAP
        if dev.get("ratio_pct") is not None:
            parts.append(
                "> Folk wisdom: humanity has unlocked less than 0.1% of Huaqiang's "
                "potential. This archive's reproducible progress: "
                f"**{dev['ratio_pct']}%** ({dev['numerator']} catalogued of "
                f"{dev['denominator']:,} search-known, "
                "[ADR-0009](docs/decisions/0009-development-metric.md))")
        elif dev.get("capped"):
            parts.append(
                "> Folk wisdom: humanity has unlocked less than 0.1% of Huaqiang's "
                "potential. This archive tried to compute a reproducible version and hit "
                f"a ceiling: search exposes at most {cap:,} results per keyword "
                f"({dev.get('keywords_observed', 0)} keywords measured, all capped). "
                f"The denominator is unknowable; the ledger holds {dev['numerator']} "
                "entries and keeps counting "
                "([ADR-0009](docs/decisions/0009-development-metric.md))")
        parts.append("")
        parts.append(f"## 🏆 Hall of Fame (≥ 10M views, {tier_n['hall']} works)")
        parts += _readme_table([x for x in by_view if x["tier"] == "hall"], "en")
        for slug, en_name, emoji in (("maigua", "The Watermelon Scene", "🍉"),
                                     ("song-laohu-banquet", "Song Laohu’s Banquet", "🍜"),
                                     ("feng-biao", "Feng Biao Scenes", "🔪")):
            scene_rows = curated["by-scene"].get(slug, [])
            top = sorted(scene_rows, key=lambda x: -(x["latest"]["view"] if x["latest"] else 0))[:10]
            label = "Top 10" if len(scene_rows) > 10 else f"all {len(scene_rows)}"
            parts.append("")
            parts.append(f"## {emoji} {en_name} · {label}")
            parts += _readme_table(top, "en")
            if len(scene_rows) > 10:
                parts.append("")
                parts.append(
                    f"→ Full list ({len(scene_rows)}): [docs/lists/scene-{slug}.md](docs/lists/scene-{slug}.md)"
                    f" ｜ [Site]({SITE_URL}/scene/{slug}/)")

    # 编年速览（两语言共用数据）
    by_year = sorted(curated.get("by-year", {}).items())
    parts.append("")
    parts.append("## 📅 编年速览" if zh else "## 📅 Chronicle at a glance")
    if zh:
        parts += ["| 年份 | 在册 | 形态构成 | 年度之最 |", "|---|---|---|---|"]
    else:
        parts += ["| Year | Works | Forms | Top work |", "|---|---|---|---|"]
    for year, yrows in by_year:
        forms: dict[str, int] = {}
        for r in yrows:
            forms[r["form"]] = forms.get(r["form"], 0) + 1
        if zh:
            fsum = " · ".join(f"{FORM_ZH[k]}×{v}" for k, v in
                              sorted(forms.items(), key=lambda kv: -kv[1]))
        else:
            fsum = " · ".join(f"{FORM_EN[k]}×{v}" for k, v in
                              sorted(forms.items(), key=lambda kv: -kv[1]))
        top = sorted(yrows, key=lambda x: -(x["latest"]["view"] if x["latest"] else 0))[0]
        parts.append(f"| {year} | {len(yrows)} | {fsum} | [{_md_escape(top['title'])}]({top['url']}) |")
    if zh:
        parts.append("")
        parts.append(
            "> 一手 pubdate 已见 **2021-07-16 至 19 四天引爆窗口**（《买瓜大队》《内向顾客》"
            "《萨日朗》密集出现）；2026 样本出现平台「疑似AI合成」标注作品。分期结论待"
            " pubdate 深页补采后定稿：[编年初稿](reports/chronicle-draft.md) · "
            "[方法学](docs/methodology.md)。⚠=待人工复核（[ADR-0006](docs/decisions/0006-review-gate.md)）。")
    else:
        parts.append("")
        parts.append(
            "> First-hand pubdates already show the **ignition window of 2021-07-16 to 19** "
            "(hall-of-fame works clustered within four days); the 2026 sample includes works "
            "carrying Bilibili's official “AI-synthesized” label. Staging conclusions await "
            "deeper pubdate paging: [chronicle draft](reports/chronicle-draft.md) · "
            "[methodology](docs/methodology.md). ⚠ = pending human review "
            "([ADR-0006](docs/decisions/0006-review-gate.md)).")

    # 创作者星图（确定性 SVG，R11 防漂移）
    gm = curated.get("graph_meta") or {}
    if gm:
        roles = "、".join(f"{k} {v}" for k, v in (gm.get("roles") or {}).items())
        if zh:
            parts += [
                "", "## 🕸 创作者星图",
                f"{gm['n_creators']} 位创作者与 {gm['n_works']} 部在册作品，分成 "
                f"{gm['n_components']} 个互不相连的创作单元，其中 {gm['n_serial']} 位 "
                "有 2 部以上在册作品。圆点是作品（大小随播放量、颜色是桥段），菱形是创作者，"
                + (f"虚线是平台标注的合作关系（{roles}）。" if roles
                   else "目前没有平台标注的合作关系。"),
                "",
                '<p align="center"><img src="docs/assets/creator-map.svg" '
                f'alt="创作者星图：{gm["n_creators"]} 位创作者、{gm["n_works"]} 部作品、'
                f'{gm["n_components"]} 个创作单元，按桥段着色" width="880"></p>',
                "",
                f"→ 可筛选、可悬停的交互版：[站点图谱页]({SITE_URL}/graph/)。"
                "边只来自确定性字段，每条带证据"
                "（[ADR-0008](docs/decisions/0008-knowledge-graph.md)）。"]
        else:
            parts += [
                "", "## 🕸 Creator constellation map",
                f"{gm['n_creators']} creators and {gm['n_works']} catalogued works form "
                f"{gm['n_components']} disconnected creative units; {gm['n_serial']} "
                "creators have two or more catalogued works. Dots are works (size follows "
                "views, colour is the scene), diamonds are creators, "
                + (f"dashed lines are platform-labelled collaborations ({roles})."
                   if roles else "with no platform-labelled collaborations so far."),
                "",
                '<p align="center"><img src="docs/assets/creator-map.svg" '
                f'alt="Creator constellation map: {gm["n_creators"]} creators, '
                f'{gm["n_works"]} works, {gm["n_components"]} units, coloured by scene" '
                'width="880"></p>',
                "",
                f"→ Filterable, hoverable version: [the graph page]({SITE_URL}/graph/). "
                "Every edge comes from a deterministic field and carries its evidence "
                "([ADR-0008](docs/decisions/0008-knowledge-graph.md))."]
    return "\n".join(parts)


def readme_file_content(lang: str, curated: dict | None = None,
                        entries: list[Entry] | None = None) -> str:
    """完整 README 内容（模板 + 生成区）。供 build 写盘与 R7 校验共用：两边同一份推导。"""
    import re as _re
    if entries is None:
        entries = load_entries()
    if curated is None:
        curated = build_curated(entries)
    if "development" not in curated:
        curated["development"] = development(curated)
    if "graph_meta" not in curated:
        from .graph import build_graph

        curated["graph_meta"] = build_graph(entries)["meta"]
    tmpl = README_TEMPLATES[lang].read_text(encoding="utf-8")
    block = _readme_block(curated, lang)
    replacement = README_MARK_BEGIN + "\n" + block + "\n" + README_MARK_END
    return _re.sub(README_MARK_BEGIN + r".*?" + README_MARK_END,
                   lambda m: replacement, tmpl, flags=_re.S)


TIMELINE_ASSETS = (
    ("docs/assets/ignition-timeline.svg", "wide", True),      # README hero
    ("site/src/data/generated/timeline-wide.svg", "wide", False),
    ("site/src/data/generated/timeline-compact.svg", "compact", False),
)


def build_timeline_outputs(entries: list[Entry]) -> None:
    """引爆时间线三变体（R10 防漂移）：README hero、站点桌面内联、站点移动端内联。"""
    from .timeline import build_timeline_svg, month_series

    for rel, variant, chrome in TIMELINE_ASSETS:
        p = config.ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(build_timeline_svg(entries, variant=variant, chrome=chrome),
                     encoding="utf-8")
    rows = month_series(entries)
    (config.CURATED_DIR / "timeline.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build] 时间线：{len(rows)} 个月度桶 × {len(TIMELINE_ASSETS)} 变体（R10）")


def build_readme(curated: dict, entries: list[Entry]) -> None:
    for lang, out in README_OUTPUTS.items():
        out.write_text(readme_file_content(lang, curated, entries), encoding="utf-8")
    print("[build] README 生成：README.md / README.en.md")


def build_graph_outputs(entries: list[Entry]) -> dict:
    """图谱产物：graph.json（R9 对象）+ gexf 下载 + 创作者星图 SVG（R11）+ 站点数据。"""
    from .graph import build_graph, to_gexf, to_svg

    g = build_graph(entries)
    (config.CURATED_DIR / "graph.json").write_text(
        json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    (config.CURATED_DIR / "graph.gexf").write_text(to_gexf(g), encoding="utf-8")
    config.SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.SITE_DATA_DIR / "graph.json").write_text(
        json.dumps(g, ensure_ascii=False), encoding="utf-8")
    svg = to_svg(g)
    for rel in ("docs/assets/creator-map.svg", "site/src/data/generated/creator-map.svg"):
        p = config.ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(svg, encoding="utf-8")
    dl = config.ROOT / "site" / "public" / "graph.gexf"
    dl.parent.mkdir(parents=True, exist_ok=True)
    dl.write_text(to_gexf(g), encoding="utf-8")
    m = g["meta"]
    print(f"[build] 图谱：{m['n_nodes']} 节点 / {m['n_edges']} 边（创作单元 "
          f"{m['n_components']} · 合作 {m['n_collaborated']} · 常驻创作者 "
          f"{m['n_serial']}）")
    return g


def _search_manifests() -> list[dict]:
    """全部检索清单（原始响应不入库，清单即证据），按日期、文件名排序。"""
    from urllib.parse import parse_qs, urlparse

    out: list[dict] = []
    for p in sorted(config.SNAPSHOTS_DIR.glob("*/search/*.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        q = parse_qs(urlparse(m.get("url", "")).query)
        out.append({
            "date": str(p.parts[-3]), "file": p.relative_to(config.ROOT).as_posix(),
            "kw": (q.get("keyword") or [p.stem])[0],
            "order": (q.get("order") or [""])[0], "page": (q.get("page") or [""])[0],
            "n": m.get("numResults_total"), "pages": m.get("numPages_total"),
            "parsed": m.get("items_parsed"), "sha": (m.get("sha256") or "")[:12],
        })
    return out


def search_totals() -> dict[str, dict]:
    """各检索清单的 numResults（按 URL 去重，ADR-0009）。"""
    out: dict[str, dict] = {}
    for p in sorted(config.SNAPSHOTS_DIR.glob("*/search/*.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        n = m.get("numResults_total")
        if n:
            out[m.get("url", p.name)] = {"total": int(n), "pages": m.get("numPages_total"),
                                         "date": str(p.parts[-3])}
    return out


def development(curated: dict) -> dict:
    """华强开发度（ADR-0009 及其修订）：在册二创 / 检索面 numResults 最大值。

    分母触及平台封顶（SEARCH_RESULTS_CAP）时**不出比值**：封顶值不是总量，拿它当分母
    算出来的百分比是假精确。此时只报告事实：账面条数、封顶值、实测关键词数。
    """
    totals = search_totals()
    best = max((v["total"] for v in totals.values()), default=0)
    latest = max((v["date"] for v in totals.values()), default=None)
    same_day = [v["total"] for v in totals.values() if v["date"] == latest]
    n = curated["counts"]["derivative"]
    # 封顶判定：最大值恰等于已知封顶值；或同日 ≥2 个关键词的总数完全一致
    # （封顶值以后变了也能识别）。注意不能用 >=：真实总量大于封顶值时并不是封顶。
    capped = bool(best) and (best == config.SEARCH_RESULTS_CAP
                             or (len(same_day) >= 2 and len(set(same_day)) == 1))
    pct = None if (not best or capped) else round(n / best * 100, 2)
    return {"numerator": n, "denominator": best, "cap": config.SEARCH_RESULTS_CAP,
            "capped": capped, "ratio_pct": pct, "keywords_observed": len(totals),
            "denominator_date": latest}


def build_badges(dev: dict, curated: dict) -> None:
    """shields.io Endpoint 徽章 JSON（部署在 Pages，README 动态引用零漂移）。"""
    bd = config.ROOT / "site" / "public" / "badges"
    bd.mkdir(parents=True, exist_ok=True)
    n = curated["counts"]["derivative"]
    (bd / "count.json").write_text(json.dumps({
        "schemaVersion": 1, "label": "在册二创", "message": f"{n}",
        "color": "#b93a32", "cacheSeconds": 21600}, ensure_ascii=False), encoding="utf-8")
    if dev["ratio_pct"] is not None:
        msg = f"{dev['ratio_pct']}%（可复算口径）"
    elif dev.get("capped"):
        msg = f"分母不可知，账面 {n} 条"
    else:
        msg = "勘探中"
    (bd / "development.json").write_text(json.dumps({
        "schemaVersion": 1, "label": "华强开发度",
        "message": msg, "color": "#2f6b4f", "cacheSeconds": 21600},
        ensure_ascii=False), encoding="utf-8")


def build_search_evidence() -> None:
    """检索面观测表（ADR-0009 修订的证据汇总），自动生成。"""
    rows = _search_manifests()
    if not rows:
        return
    latest = rows[-1]["date"]
    today = [r for r in rows if r["date"] == latest]
    parsed = [r for r in today if r["n"] is not None]           # 解析器上线前抓的清单没有总数
    capped = [r for r in parsed if r["n"] == config.SEARCH_RESULTS_CAP]
    lines = [
        "# 检索面观测（自动生成）", "",
        "> 自动生成（`zfq build`），勿手改。数据源：`data/snapshots/<日期>/search/*.json`。",
        "> 原始 HTML 不入库（ADR-0002），清单只留 URL、哈希与解析计数；`numResults` 取自页面",
        "> `searchAllResponse`（`__pinia` 混淆 IIFE 的常量表，形参下标对位解析，见 `zfq.search`）。",
        "> 「未解析」表示该清单在解析器修好之前抓取，当时取不到总数。", "",
        f"- 最近一次观测：{latest}，{len(today)} 份清单，其中 {len(parsed)} 份解析出了总数，"
        f"{len(capped)} 份的 numResults 等于 {config.SEARCH_RESULTS_CAP:,}。", "",
    ]
    if len(capped) == len(parsed) and len(parsed) >= 2:
        lines += [
            f"- **结论**：多个关键词的 numResults 同为 {config.SEARCH_RESULTS_CAP:,}，"
            "与关键词无关、首页候选数各异，只能是平台检索面封顶。检索面无法给出真实总量，"
            "任何以它为分母的「开发度百分比」都不成立（ADR-0009 修订）。", "",
        ]
    lines += ["| 日期 | 关键词 | 排序 | 页 | numResults | numPages | 本页解析 | sha256 前 12 位 |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows[-40:]:
        lines.append(f"| {r['date']} | {r['kw']} | {r['order']} | {r['page']} | "
                     f"{r['n'] if r['n'] is not None else '未解析'} | "
                     f"{r['pages'] if r['pages'] is not None else '未解析'} | {r['parsed']} | "
                     f"{r['sha']} |")
    lines += ["", f"（仅列最近 40 份，共 {len(rows)} 份；完整清单见 `data/snapshots/`。）", ""]
    out = config.ROOT / "docs" / "evidence" / "search-surface.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    entries = load_entries()
    creators = []
    for p in sorted(config.CREATORS_DIR.glob("*.json")):
        creators.append(json.loads(p.read_text(encoding="utf-8")))
    curated = build_curated(entries)
    curated["development"] = development(curated)
    curated["graph_meta"] = build_graph_outputs(entries)["meta"]
    build_lists_md(curated)
    build_site_data(curated, creators)
    build_feeds(curated)
    build_timeline_outputs(entries)
    build_readme(curated, entries)
    build_badges(curated["development"], curated)
    build_search_evidence()
    print(f"[build] entries={len(entries)} creators={len(creators)} → "
          f"curated/lists/README/site-data/feeds 完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
