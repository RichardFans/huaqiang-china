# -*- coding: utf-8 -*-
"""R3（词表同步）/ R4（单调性）/ 搜索解析 / 构建确定性 测试。"""
from __future__ import annotations

import json

from zfq import validate as V
from zfq.schema import DiscoveryInfo, Entry, Owner, Snapshot, utcnow


def _mk_entry(bvid: str, views: list[int]):
    n = utcnow()
    # 快照时间戳按天拉开：避免 R5 同日重复；也模拟真实跟踪节奏
    from datetime import timedelta
    snaps = [
        Snapshot(captured_at=n - timedelta(days=len(views) - i),
                 endpoint="api-view", view=v,
                 like=v // 10, coin=v // 20, favorite=v // 5,
                 share=v // 30, danmaku=v // 50, reply=v // 40)
        for i, v in enumerate(views)]
    return Entry.model_validate(dict(
        bvid=bvid, title="t", owner=Owner(mid=1, name="a"),
        pubdate="2021-06-01T00:00:00+00:00",
        scenes=["maigua"], scene_evidence="x",
        form="clip", form_status="confirmed",
        tier="hot", tier_basis="测试",
        discovered_via=DiscoveryInfo(method="manual-issue", captured_at=n),
        first_seen=n,
        snapshots=snaps,
    ))


def test_vocab_slug_sync():
    assert V._slug_sync_ok() == [], "受控词表与 vocabulary.md 失同步"


def test_search_parser_on_real_shape():
    """用与线上实测同形的（脱敏）样本验证解析器。"""
    from zfq.search import parse_search_html
    html = (
        'x{result_type:e,data:[{type:e,id:bg,author:"\\u666e\\u901a\\u7684\\u77ac",'
        'mid:34931,typeid:i,typename:h,'
        'arcurl:"http:\\u002F\\u002Fwww.bilibili.com\\u002Fvideo\\u002Fav826559388",'
        'aid:bg,bvid:"BV1Ku4y1f7oe",'
        'title:"\\u003Cem class=\\"keyword\\"\\u003E\\u534e\\u5f3a\\u4e70\\u74dc\\u003C\\u002Fem\\u003E'
        '\\u901f\\u901a\\u7248\\u3002",'
        'description:z,pic:"x",play:25000000,video_review:1,favorites:2,tag:"\\u9b3c\\u755c",'
        'review:3,pubdate:1685126400,duration:180}]}y'
    )
    cands = parse_search_html(html, keyword="华强买瓜", order="click")
    assert len(cands) == 1
    c = cands[0]
    assert c.bvid == "BV1Ku4y1f7oe"
    assert c.title == "华强买瓜速通版。"
    assert c.author == "普通的瞬"
    assert c.play == 25_000_000
    assert c.pubdate is not None and c.pubdate.year == 2023
    assert c.duration_s == 180


def test_search_parser_ignores_noise():
    from zfq.search import parse_search_html
    html = 'jump_url:"https://x/video/BV1DgyszmEQr?trackid=abc"}'
    assert parse_search_html(html, keyword="k", order="click") == []


def test_build_deterministic(tmp_path, monkeypatch):
    """构建必须是 data 的纯函数：同输入两次构建，curated 内容一致。"""
    from zfq import build as B
    from zfq import config

    e = _mk_entry("BV1Ku4y1f7oe", [100, 200])
    data_dir = tmp_path / "data"
    (data_dir / "entries").mkdir(parents=True)
    (data_dir / "entries" / "BV1Ku4y1f7oe.json").write_text(
        e.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(config, "ENTRIES_DIR", data_dir / "entries")
    monkeypatch.setattr(config, "CREATORS_DIR", data_dir / "creators")
    monkeypatch.setattr(config, "CURATED_DIR", tmp_path / "curated")
    (data_dir / "creators").mkdir()

    import zfq.track as T
    monkeypatch.setattr(T, "config", config)

    B.build_curated(T.load_entries())
    v1 = (tmp_path / "curated" / "views.json").read_text(encoding="utf-8")
    B.build_curated(T.load_entries())
    v2 = (tmp_path / "curated" / "views.json").read_text(encoding="utf-8")
    j1 = json.loads(v1)
    j2 = json.loads(v2)
    j1.pop("generated_at")
    j2.pop("generated_at")
    assert j1 == j2


def test_monotonicity_detector_via_validate(tmp_path, monkeypatch):
    from zfq import config

    bad = _mk_entry("BV1Ku4y1f7oe", [200000, 100000])   # 大幅回退 → R4 错误
    good = _mk_entry("BV2Ku4y1f7oe", [100000, 200000])
    ed = tmp_path / "entries"
    ed.mkdir(parents=True)
    (ed / "BV1Ku4y1f7oe.json").write_text(bad.model_dump_json(), encoding="utf-8")
    (ed / "BV2Ku4y1f7oe.json").write_text(good.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(config, "ENTRIES_DIR", ed)
    monkeypatch.setattr(config, "CREATORS_DIR", tmp_path / "creators")
    (tmp_path / "creators").mkdir()

    errors, stats, warnings = V.validate_all(check_readme=False)
    assert stats["entries"] == 2
    r4 = [e for e in errors if e.startswith("R4")]
    assert len(r4) >= 1, f"应检出计数回退：{errors}"
