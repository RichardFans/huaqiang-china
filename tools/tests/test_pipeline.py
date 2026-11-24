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


def test_parse_totals_from_obfuscated_pinia():
    """检索总数在混淆 IIFE 的实参表里；形参映射每次响应重排，必须按下标对位解析。"""
    from zfq.search import parse_totals

    # 形参名故意打乱：numResults 引用 qK、numPages 引用 zz；正文串内含 "}(\\"" 干扰
    html = ('x<script>window.__pinia=(function(a,zz,qK,e){return {searchResponse:{'
            'bmgDefDomain:b},searchAllResponse:{seid:"1",page:a,pagesize:e,next:a,'
            'numResults:qK,numPages:zz,suggest_keyword:b,rqt_type:aK,exp_list:{"5503":e},'
            'list:[{title:"a}(\\"x",bvid:"BV1Ku4y1f7oe"}]}}}(2,57,19235,42))</script>y')
    assert parse_totals(html) == (19235, 57)
    # 未混淆的字面量形态兜底（无 numPages）
    assert parse_totals("numResults:1234,numPages:5") == (1234, None)
    # 都解析不到 → None（ADR-0009：分母缺数时不得编造）
    assert parse_totals("<html>nothing here</html>") == (None, None)


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
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    (tmp_path / "creators").mkdir()

    errors, stats, warnings = V.validate_all(check_readme=False)
    assert stats["entries"] == 2
    r4 = [e for e in errors if e.startswith("R4")]
    assert len(r4) >= 1, f"应检出计数回退：{errors}"


def test_cover_mining_picks_latest_snapshot(tmp_path, monkeypatch):
    """R8 前置：挖掘取最晚日期快照的 pic，无快照返回 (None, '')。"""
    from zfq import config, mine

    snap = tmp_path / "snapshots"
    (snap / "2026-01-01" / "view").mkdir(parents=True)
    (snap / "2026-01-02" / "view").mkdir(parents=True)
    (snap / "2026-01-01" / "view" / "BV1Ku4y1f7oe.json").write_text(
        json.dumps({"code": 0, "data": {"pic": "http://x/old.jpg"}}), encoding="utf-8")
    (snap / "2026-01-02" / "view" / "BV1Ku4y1f7oe.json").write_text(
        json.dumps({"code": 0, "data": {"pic": "http://x/new.jpg"}}), encoding="utf-8")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", snap)

    assert mine.latest_cover_from_snapshots("BV1Ku4y1f7oe") == \
        ("http://x/new.jpg", "mined: api-view@2026-01-02")
    assert mine.latest_cover_from_snapshots("BV2Ku4y1f7oe") == (None, "")


def test_cover_consistency_rule_via_validate(tmp_path, monkeypatch):
    """R8：entries.cover 与快照 pic 不一致必须报错。"""
    from zfq import config

    snap = tmp_path / "snapshots"
    d = snap / "2026-01-02" / "view"
    d.mkdir(parents=True)
    (d / "BV1Ku4y1f7oe.json").write_text(
        json.dumps({"code": 0, "data": {"pic": "http://x/1.jpg"}}), encoding="utf-8")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", snap)

    e = _mk_entry("BV1Ku4y1f7oe", [100])
    raw = json.loads(e.model_dump_json())
    raw["cover"] = "http://x/wrong.jpg"
    raw["cover_evidence"] = "mined: api-view@2026-01-02"
    ed = tmp_path / "entries"
    ed.mkdir(parents=True)
    (ed / "BV1Ku4y1f7oe.json").write_text(
        json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "ENTRIES_DIR", ed)
    monkeypatch.setattr(config, "CREATORS_DIR", tmp_path / "creators")
    (tmp_path / "creators").mkdir()

    errors, stats, warnings = V.validate_all(check_readme=False)
    r8 = [x for x in errors if x.startswith("R8")]
    assert len(r8) == 1, f"应检出封面不一致：{errors}"


def test_readme_table_links_creator_space():
    """README 榜单的 UP主 单元格必须是 mid 主页链接（名字会改，mid 恒定）。"""
    from zfq import build as B

    row = {"title": "t", "url": "https://www.bilibili.com/video/BV1Ku4y1f7oe",
           "owner": {"mid": 42, "name": "u"}, "pubdate": "2021-06-01T00:00:00+00:00",
           "form": "clip", "scenes": ["maigua"], "review": "pending", "status": "ok",
           "latest": {"view": 10, "coin": 1}}
    lines = B._readme_table([row], "zh")
    assert any("https://space.bilibili.com/42" in ln for ln in lines), lines


def test_gexf_wellformed(tmp_path, monkeypatch):
    from zfq import config, graph as G

    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    (tmp_path / "snapshots").mkdir()
    g = G.build_graph([_mk_entry("BV1Ku4y1f7oe", [100])])
    from xml.etree import ElementTree as ET
    root = ET.fromstring(G.to_gexf(g))
    ns = "{http://gexf.net/1.3}"
    assert root.tag == ns + "gexf"
    n_nodes = len(root.findall(f".//{ns}node"))
    n_edges = len(root.findall(f".//{ns}edge"))
    assert n_nodes == g["meta"]["n_nodes"] and n_edges == g["meta"]["n_edges"]


def test_development_metric_formula(tmp_path, monkeypatch):
    """开发度 = 在册 / numResults 最大值；缺数返回 None（ADR-0009）。"""
    from zfq import build as B, config

    snap = tmp_path / "snapshots" / "2026-01-02" / "search"
    snap.mkdir(parents=True)
    (snap / "a.json").write_text(json.dumps(
        {"url": "u1", "numResults_total": 5000}), encoding="utf-8")
    (snap / "b.json").write_text(json.dumps(
        {"url": "u2", "numResults_total": 12000}), encoding="utf-8")
    (snap / "c.json").write_text(json.dumps(
        {"url": "u3", "numResults_total": None}), encoding="utf-8")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")

    curated = {"counts": {"derivative": 171}}
    dev = B.development(curated)
    assert dev["denominator"] == 12000 and dev["ratio_pct"] == round(171 / 12000 * 100, 2)
    # 无清单 -> 分母 0 -> None，不得编造
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    dev2 = B.development(curated)
    assert dev2["ratio_pct"] is None and dev2["denominator"] == 0
    assert dev2["capped"] is False and dev2["cap"] == config.SEARCH_RESULTS_CAP

    # 分母触及平台封顶（2026-11-24 实测：五词 numResults 均为 1000）→ 不出比值
    for f in snap.iterdir():
        f.unlink()
    for name, total in (("d", 1000), ("e", 1000), ("f", 600)):
        (snap / f"{name}.json").write_text(json.dumps(
            {"url": name, "numResults_total": total, "numPages_total": 50}),
            encoding="utf-8")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    dev3 = B.development(curated)
    assert dev3["capped"] is True and dev3["ratio_pct"] is None
    assert dev3["denominator"] == 1000 and dev3["keywords_observed"] == 3


def test_timeline_deterministic_single_hue():
    """时间线 hero：确定性、月度桶展开正确、引爆月有直接标注（R10 前置）。"""
    from datetime import datetime, timezone
    from zfq import timeline as T
    from zfq.schema import DiscoveryInfo, Owner

    def mk(bvid, month):
        n = utcnow()
        return Entry.model_validate(dict(
            bvid=bvid, title="t", owner=Owner(mid=1, name="a"),
            pubdate=f"{month}-10T00:00:00+00:00",
            scenes=["maigua"], scene_evidence="x",
            form="clip", form_status="confirmed", tier="hot", tier_basis="测试",
            discovered_via=DiscoveryInfo(method="manual-issue", captured_at=n),
            first_seen=n, snapshots=[]))

    entries = ([mk("BV1Ku4y1f7oe", "2021-07")] * 5
               + [mk("BV2Ku4y1f7oe", "2021-08")] * 2
               + [mk("BV3Ku4y1f7oe", "2021-10")])
    rows = T.month_series(entries)
    assert [r["month"] for r in rows] == ["2021-07", "2021-08", "2021-09", "2021-10"]
    assert rows[0]["count"] == 5 and rows[0]["ignition"] is True
    assert rows[2]["count"] == 0  # 空月补零桶

    svg1 = T.build_timeline_svg(entries)
    svg2 = T.build_timeline_svg(entries)
    assert svg1 == svg2
    assert "引爆窗口 2021-07-16 至 07-19" in svg1 and ">5 条<" in svg1
    # 单色系：不出现第二身份色（绿色仅存在于站点 CSS，不该进 SVG）
    assert "#2f6b4f" not in svg1
    # 设计规范：图内不出现任何破折号字符
    assert "—" not in svg1 and "–" not in svg1

    wide, bare, compact = (T.build_timeline_svg(entries),
                           T.build_timeline_svg(entries, chrome=False),
                           T.build_timeline_svg(entries, variant="compact"))
    assert "（月度，在册样本 8 条）</text>" in wide       # chrome：带可见标题
    assert "（月度，在册样本 8 条）</text>" not in bare   # bare：标题由页面 HTML 承担
    assert 'viewBox="0 0 920 ' in wide and 'viewBox="0 0 400 ' in compact
    assert "2021-07 引爆" in compact
    # 深色模式回退：README 里作为 <img> 时靠内部媒体查询适配
    assert "@media (prefers-color-scheme: dark)" in wide


def test_graph_staff_semantics_and_evidence(tmp_path, monkeypatch):
    """合作边：排除投稿者本人；role 取平台原字面量；节点用昵称；每条边带证据。"""
    from zfq import config, graph as G

    view = tmp_path / "snapshots" / "2026-01-02" / "view"
    view.mkdir(parents=True)
    (view / "BV1Ku4y1f7oe.json").write_text(json.dumps({
        "code": 0, "data": {"pic": "http://x/1.jpg", "staff": [
            {"mid": 1, "title": "UP主", "name": "投稿者本人"},
            {"mid": 99, "title": "参演", "name": "合作者A"},
            {"mid": 77, "title": "剪辑", "name": "合作者B"}]}}), encoding="utf-8")
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")

    e = _mk_entry("BV1Ku4y1f7oe", [100])            # owner mid = 1
    g1, g2 = G.build_graph([e]), G.build_graph([e])
    assert g1 == g2, "图谱构建必须确定性"
    ids = {n["id"]: n for n in g1["nodes"]}
    assert "scene:maigua" in ids and "bv:BV1Ku4y1f7oe" in ids and "mid:1" in ids
    assert ids["mid:99"]["label"] == "合作者A"       # 用昵称，不是角色字样
    rels = {(x["relation"], x["source"], x["target"]) for x in g1["edges"]}
    assert ("created", "mid:1", "bv:BV1Ku4y1f7oe") in rels
    assert ("in_scene", "bv:BV1Ku4y1f7oe", "scene:maigua") in rels
    collab = [x for x in g1["edges"] if x["relation"] == "collaborated"]
    assert {x["source"] for x in collab} == {"mid:99", "mid:77"}    # 不含投稿者本人
    assert {x["role"] for x in collab} == {"参演", "剪辑"}
    assert all(x["evidence"] for x in g1["edges"]), "边必须带证据"
    assert all("data.staff" in x["evidence"] for x in collab)
    assert g1["meta"]["n_components"] == 1 and g1["meta"]["n_collaborated"] == 2
    assert g1["meta"]["roles"] == {"剪辑": 1, "参演": 1}


def test_creator_map_svg_deterministic_wellformed_no_overlap(tmp_path, monkeypatch):
    """星图：确定性、良构 XML、节点可点、分量外接框互不相交（R11 前置）。"""
    from xml.etree import ElementTree as ET
    from zfq import config, graph as G
    from zfq.schema import DiscoveryInfo, Owner

    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path / "snapshots")
    (tmp_path / "snapshots").mkdir()

    def mk(bvid, mid, view, month, tier="hot", scenes=("maigua",)):
        n = utcnow()
        return Entry.model_validate(dict(
            bvid=bvid, title=f"作品{mid}", owner=Owner(mid=mid, name=f"UP{mid}"),
            pubdate=f"{month}-10T00:00:00+00:00", scenes=list(scenes), scene_evidence="x",
            form="clip", form_status="confirmed", tier=tier, tier_basis="测试",
            discovered_via=DiscoveryInfo(method="manual-issue", captured_at=n),
            first_seen=n, snapshots=[
                Snapshot(captured_at=n, endpoint="api-view", view=view, like=0, coin=0,
                         favorite=0, share=0, danmaku=0, reply=0)]))

    entries = [mk(f"BV1Ku4y1f7{i:02d}", i, 10_000_000 * (i + 1), "2021-07", "hall")
               for i in range(12)]
    entries += [mk("BV2Ku4y1f7o1", 1, 5000, "2021-08"), mk("BV2Ku4y1f7o2", 1, 5000, "2021-09"),
                mk("BV3Ku4y1f7o2", 2, 5000, "2021-10", scenes=("zhengfu-other", "maigua")),
                mk("BV4Ku4y1f7o2", 2, 5000, "2021-11", scenes=("song-laohu-banquet",))]
    g = G.build_graph(entries)
    svg1, svg2 = G.to_svg(g), G.to_svg(g)
    assert svg1 == svg2 and "@media (prefers-color-scheme: dark)" in svg1

    ns = "{http://www.w3.org/2000/svg}"
    root = ET.fromstring(svg1)
    links = root.findall(f".//{ns}a")
    assert links and all(a.get("href", "").startswith("https://") for a in links)
    assert len(root.findall(f".//{ns}circle[@class='cm-ring']")) == 12   # 殿堂级外环

    lay = G.layout_graph(g)
    assert lay["components"] == 12 and len(lay["boxes"]) == 12
    boxes = lay["boxes"]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            apart = (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
            assert apart, f"分量 {i} 与 {j} 外接框相交：{a} {b}"
    xs = [p["x"] for p in lay["pos"].values()]
    ys = [p["y"] for p in lay["pos"].values()]
    assert min(xs) >= 0 and max(xs) <= lay["width"] and max(ys) <= lay["height"]
    # 站点交互依赖的属性：查找文本与桥段筛选（节点、边、标签都要带 data-scene）
    assert 'data-search=' in svg1
    assert svg1.count('<text class="cm-t cm-l') == svg1.count('data-for="')
    import re as _re
    for key in ("maigua", "other", "song-laohu-banquet"):      # 属性是空格分隔的词表
        assert _re.search(rf'data-scene="([^"]* )?{key}( [^"]*)?"', svg1), key


def test_site_graph_palette_in_sync():
    """站点图例/筛选用的色值必须与 graph.SCENE_COLOR 一致（Python 回退值与 CSS 两处，防漂移）。"""
    from zfq import config, graph as G

    css = (config.ROOT / "site" / "src" / "styles" / "global.css").read_text(encoding="utf-8")
    for pair in list(G.SCENE_COLOR.values()) + [G.OTHER_COLOR]:
        for hexv in pair:
            assert hexv.lower() in css.lower(), f"站点样式缺少图谱色值 {hexv}"
    # 图谱色只允许三个色相 + 中性灰（dataviz：任意两点相邻的图形式上限）
    assert set(G.SCENE_COLOR) == {"maigua", "song-laohu-banquet", "feng-biao"}
