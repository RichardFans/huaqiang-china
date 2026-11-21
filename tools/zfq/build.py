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
SITE_URL = "https://huaqiang-china.github.io"  # 占位：启用 Pages 后以实际域名为准


def _slim(e: Entry) -> dict:
    s = e.latest
    return {
        "bvid": e.bvid, "title": e.title, "url": e.url,
        "owner": {"mid": e.owner.mid, "name": e.owner.name},
        "pubdate": iso(e.pubdate),
        "kind": e.kind, "scenes": e.scenes, "form": e.form, "tier": e.tier,
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
        lines.append(f"## {rows[0]['owner']['name']}（mid:{mid}，{len(rows)} 条）")
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


def main() -> int:
    entries = load_entries()
    creators = []
    for p in sorted(config.CREATORS_DIR.glob("*.json")):
        creators.append(json.loads(p.read_text(encoding="utf-8")))
    curated = build_curated(entries)
    build_lists_md(curated)
    build_site_data(curated, creators)
    build_feeds(curated)
    print(f"[build] entries={len(entries)} creators={len(creators)} → "
          f"curated/lists/site-data/feeds 完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
