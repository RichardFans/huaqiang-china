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
# 混淆/压缩变体：numResults":123、numResults :123 等（2026-11 实测页面形态）
NUMRESULTS_LOOSE_RE = re.compile(r'numResults"?\s*[:：]\s*"?(\d{1,12})"')
# 2026-11-24 实测主形态：数据在混淆 IIFE 里，常量以形参名引用，真实值在尾部实参表。
#     window.__pinia=(function(a,b,...,eZ){return {searchAllResponse:{...,numResults:K,numPages:aJ,...}}} (实参1,实参2,...))
# 形参↔名称的映射**每次响应都会重排**（同一次会话里 numResults 先是 J 后是 K），
# 所以必须按下标对位解析，不能写死变量名。
_PINIA_HEAD_RE = re.compile(r"window\.__pinia\s*=\s*\(function\s*\(([^)]*)\)\s*\{")
_ALL_RESPONSE_RE = re.compile(
    r"searchAllResponse:\{[^{}]*?numResults:(\w+),numPages:(\w+)")


def _pinia_constants(html: str) -> dict[str, str]:
    """混淆 __pinia IIFE 的常量表：形参名 → 实参字面量。解析不到返回空 dict。

    只做括号/字符串状态的线性扫描，不执行任何脚本（浏览器等价读取，ADR-0002）。
    """
    m = _PINIA_HEAD_RE.search(html)
    if not m:
        return {}
    params = [p.strip() for p in m.group(1).split(",") if p.strip()]
    i, n = m.end(), len(html)          # i：函数体 '{' 之后
    depth, in_str, quote = 1, False, ""
    while i < n and depth > 0:         # 跳过函数体，定位到 "}("
        ch = html[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                in_str = False
        elif ch in "\"'":
            in_str, quote = True, ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    while i < n and html[i] in " \n\r\t":
        i += 1
    if i >= n or html[i] != "(":
        return {}
    i += 1
    args: list[str] = []
    cur: list[str] = []
    depth, in_str, quote = 0, False, ""
    while i < n:                       # 逐字读实参表，顶层逗号切分
        ch = html[i]
        if in_str:
            cur.append(ch)
            if ch == "\\" and i + 1 < n:
                cur.append(html[i + 1])
                i += 2
                continue
            if ch == quote:
                in_str = False
        elif ch in "\"'":
            in_str, quote = True, ch
            cur.append(ch)
        elif ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            if ch == ")" and depth == 0:
                args.append("".join(cur).strip())
                break
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    return dict(zip(params, args))


def parse_totals(html: str) -> tuple[int | None, int | None]:
    """检索页的结果总数与总页数。解析不到一律 None（不编造，ADR-0009 依赖此语义）。"""
    lit = NUMRESULTS_RE.search(html) or NUMRESULTS_LOOSE_RE.search(html)
    if lit:
        return int(lit.group(1)), None
    consts = _pinia_constants(html)
    if not consts:
        return None, None
    m = _ALL_RESPONSE_RE.search(html)
    if not m:
        return None, None

    def to_int(name: str) -> int | None:
        v = consts.get(name)
        return int(v) if v is not None and re.fullmatch(r"\d+", v) else None

    return to_int(m.group(1)), to_int(m.group(2))


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
        num_results, num_pages = parse_totals(resp.text)
        if num_results:
            total = max(total, num_results)
        if save_manifest_dir:
            save_manifest_dir.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"\s+", "-", keyword)
            manifest = {
                "url": resp.url,
                "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(resp.text.encode("utf-8")).hexdigest(),
                "bytes": len(resp.text),
                "items_parsed": len(cands),
                "numResults_total": num_results,
                "numPages_total": num_pages,
                "numResults_source": ("searchAllResponse.numResults"
                                      "（__pinia IIFE 常量表，形参下标对位）"
                                      if num_results else None),
                "note": "原始 HTML 不入库（ADR-0002），仅留哈希与解析计数",
            }
            (save_manifest_dir / f"search_{slug}_{order}_p{page}.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return list(all_cands.values()), total
