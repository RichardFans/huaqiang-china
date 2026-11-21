# -*- coding: utf-8 -*-
"""作品发现·主路线：搜索结果页 HTML 锚点解析（ADR-0005）。

实测（2026-11-21）：search.bilibili.com 结果页把数据内嵌在混淆的 window.__pinia
IIFE 里，视频条目形如（无引号 key 的 JS 字面量）：

    {type:e,id:bg,author:"普通的瞬",mid:34931...,arcurl:"http:\\u002F\\u002F...",
     bvid:"BV1Ku4y1f7oe",title:"\\u003Cem class=\\"keyword\\"\\u003E华强买瓜...",
     play:123,video_review:...,favorites:...,pubdate:1685...,duration:123}

本解析器只做字段级正则抽取（浏览器等价读取，不涉及任何签名/风控机制）。
原始 HTML 不落库（ADR-0002：不存页面快照内容），只留 manifest（URL/哈希/条数）。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .client import PoliteClient

BVID_RE = re.compile(r'bvid:"(BV[0-9A-Za-z]{10})"')
AUTHOR_RE = re.compile(r'author:"((?:[^"\\]|\\.)*)"')
MID_RE = re.compile(r"mid:(\d+)")
TITLE_RE = re.compile(r'title:"((?:[^"\\]|\\.)*)"')
PLAY_RE = re.compile(r"[,{]play:(\d+)")
PUBDATE_RE = re.compile(r"[,{]pubdate:(\d+)")
DURATION_RE = re.compile(r"[,{]duration:(\d+)")
NUMRESULTS_RE = re.compile(r"numResults:(\d+)")


@dataclass
class Candidate:
    bvid: str
    title: str          # 已去 <em> 高亮、已反转义
    author: str
    mid: int
    play: int | None
    pubdate: datetime | None
    duration_s: int | None
    keyword: str
    order: str

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d["pubdate"] = self.pubdate.isoformat(timespec="seconds") if self.pubdate else None
        return d


def _unescape_js_string(raw: str) -> str:
    """JS 字符串字面量（\\uXXXX、\\" 等）→ Python str，并去检索高亮 <em> 标记。

    注意顺序：原始串中 <em class=\\"keyword\\"> 的引号是转义形态，必须先 json.loads
    反转义、再剥离 <em> 标签（实测教训，见 tests/test_pipeline.py）。
    """
    try:
        out = json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        out = raw
    return re.sub(r'</?em[^>]*>', "", out)


def parse_search_html(html: str, *, keyword: str, order: str) -> list[Candidate]:
    out: dict[str, Candidate] = {}
    for m in BVID_RE.finditer(html):
        bvid = m.group(1)
        if bvid in out:
            continue
        window = html[max(0, m.start() - 500): m.start() + 2600]
        if 'author:"' not in window:
            continue  # 噪声命中（推荐位/trackid 等）
        auth = AUTHOR_RE.search(window)
        mid = MID_RE.search(window)
        title = TITLE_RE.search(window)
        if not (auth and mid and title):
            continue
        play = PLAY_RE.search(window)
        pub = PUBDATE_RE.search(window)
        dur = DURATION_RE.search(window)
        out[bvid] = Candidate(
            bvid=bvid,
            title=_unescape_js_string(title.group(1)),
            author=_unescape_js_string(auth.group(1)),
            mid=int(mid.group(1)),
            play=int(play.group(1)) if play else None,
            pubdate=(
                datetime.fromtimestamp(int(pub.group(1)), tz=timezone.utc)
                if pub else None
            ),
            duration_s=int(dur.group(1)) if dur else None,
            keyword=keyword,
            order=order,
        )
    return list(out.values())


def harvest(
    keyword: str,
    *,
    order: str = "click",
    pages: int = 1,
    client: PoliteClient | None = None,
    save_manifest_dir: Path | None = None,
) -> tuple[list[Candidate], int]:
    """抓取并解析搜索页。返回 (候选, 结果总数)。manifest 记 URL+SHA256+条数（不存页面字节）。"""
    client = client or PoliteClient()
    all_cands: dict[str, Candidate] = {}
    total = 0
    for page in range(1, pages + 1):
        resp = client.get(
            config.URL_SEARCH,
            params={"keyword": keyword, "order": order, "page": page},
        )
        cands = parse_search_html(resp.text, keyword=keyword, order=order)
        for c in cands:
            all_cands.setdefault(c.bvid, c)
        n = NUMRESULTS_RE.search(resp.text)
        if n:
            total = max(total, int(n.group(1)))
        if save_manifest_dir:
            save_manifest_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"\s+", "-", keyword)
            manifest = {
                "url": resp.url,
                "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(resp.text.encode("utf-8")).hexdigest(),
                "bytes": len(resp.text),
                "items_parsed": len(cands),
                "numResults_total": int(n.group(1)) if n else None,
                "note": "原始 HTML 不入库（ADR-0002），仅留哈希与解析计数",
            }
            (save_manifest_dir / f"search_{slug}_{order}_p{page}.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return list(all_cands.values()), total
