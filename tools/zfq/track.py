# -*- coding: utf-8 -*-
"""跟踪管线（项目心跳）：存量条目增量快照 + 涨幅计算 + 活性检查 + 双面交叉验证。

交叉验证面（docs/verification.md）：
  A 面 = api-view JSON 端点；B 面 = 视频页 HTML 内嵌状态（正则抽取 stat）。
两面对同一 bvid 同日取数，计数应一致（允许 0 差异；>0 记 mismatch 待人工核）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

from . import config
from .client import PoliteClient
from .ingest import save_raw_view, view_to_snapshot
from .schema import Entry, Snapshot, utcnow

# 视频页内嵌 stat：块捕获 + 逐键解析（键序无关；实测 share 与 like 之间夹
# now_rank/his_rank，且不同块用 favorite/fav 两种键名）
STAT_BLOCK = re.compile(r'"stat":\{("aid":[^{}]*)\}')
AI_LABEL = "疑似使用AI技术合成"   # 平台官方 AI 合成标注（argue_msg）


def load_entries() -> list[Entry]:
    out = []
    for p in sorted(config.ENTRIES_DIR.glob("BV*.json")):
        out.append(Entry.model_validate_json(p.read_text(encoding="utf-8")))
    return out


def save_entry(e: Entry) -> None:
    (config.ENTRIES_DIR / f"{e.bvid}.json").write_text(
        e.model_dump_json(indent=2), encoding="utf-8")


def append_snapshot(e: Entry, snap: Snapshot) -> bool:
    """同端点同日幂等替换，跨日追加；返回是否变化。"""
    day = snap.captured_at.date()
    kept = [s for s in e.snapshots
            if not (s.endpoint == snap.endpoint and s.captured_at.date() == day)]
    kept.append(snap)
    kept.sort(key=lambda s: s.captured_at)
    changed = kept != e.snapshots
    e.snapshots = kept
    return changed


def fetch_view(client: PoliteClient, bvid: str) -> dict | None:
    try:
        payload = client.get_json(config.URL_VIEW.format(bvid=bvid))
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {bvid} view 失败: {e!r}")
        return None
    if payload.get("code") != 0:
        return {"__code": payload.get("code"), "__message": payload.get("message")}
    return payload


def fetch_page_state(client: PoliteClient, bvid: str) -> tuple[Snapshot | None, bool]:
    """返回 (快照, 平台AI标注)。页面为 B 面证据；AI 标注是平台官方 form 判定线索。"""
    try:
        resp = client.get(config.URL_VIDEO_PAGE.format(bvid=bvid))
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {bvid} 页面失败: {e!r}")
        return None, False
    m = next((m for m in STAT_BLOCK.finditer(resp.text) if '"view":' in m.group(1)),
             None)
    if not m:
        return None, False
    pairs = dict(re.findall(r'"(\w+)":(-?\d+)', m.group(1)))
    try:
        snap = Snapshot(
            captured_at=utcnow(), endpoint="page-state",
            view=int(pairs["view"]), like=int(pairs.get("like", 0)),
            coin=int(pairs.get("coin", 0)),
            favorite=int(pairs.get("favorite", pairs.get("fav", 0))),
            share=int(pairs.get("share", 0)),
            danmaku=int(pairs.get("danmaku", 0)), reply=int(pairs.get("reply", 0)))
    except KeyError:
        return None, False
    return snap, AI_LABEL in resp.text


def cross_check(client: PoliteClient, entries: list[Entry], n: int) -> list[dict]:
    results = []
    for e in entries[:n]:
        if e.status != "ok":
            continue
        api = fetch_view(client, e.bvid)
        if not api or api.get("__code") is not None:
            results.append({"bvid": e.bvid, "result": "api-failed"})
            continue
        a = view_to_snapshot(api["data"], utcnow())
        b, ai_flag = fetch_page_state(client, e.bvid)
        if b is None:
            results.append({"bvid": e.bvid, "result": "page-unparseable"})
            continue
        # B 面快照也入条目（同端点同日幂等替换），留双面证据链
        if append_snapshot(e, b):
            save_entry(e)
        # 平台 AI 合成标注 → form 判定升级（平台官方标注，可信度高于标题启发）
        if ai_flag and e.form_status != "confirmed":
            import re as _re
            sing = _re.search(r"翻唱|唱|歌|念白|朗读|RAP|MV|音乐", e.title)
            new_form = "ai-cover" if sing else "ai-other"
            e.form = new_form  # type: ignore[assignment]
            e.form_status = "confirmed"
            e.form_evidence = ("平台页面标注「该内容疑似使用AI技术合成」（cross-check "
                              f"B 面捕获）→ {new_form}")
            save_entry(e)
        diff = {f: getattr(a, f) - getattr(b, f)
                for f in ("view", "like", "coin", "favorite", "share", "danmaku", "reply")}
        consistent = all(d == 0 for d in diff.values())
        results.append({
            "bvid": e.bvid,
            "result": "consistent" if consistent else "mismatch",
            "ai_label": ai_flag,
            "api": a.model_dump(mode="json"), "page": b.model_dump(mode="json"),
            "diff": diff,
        })
    return results


def compute_deltas(entries: list[Entry], now: datetime) -> list[dict]:
    """近 7/30 天播放增量（对照最近一次 ≥N 天前的快照）。"""
    out = []
    for e in entries:
        if e.status != "ok" or len(e.snapshots) < 2:
            continue
        cur = e.snapshots[-1]
        row = {"bvid": e.bvid, "title": e.title, "view": cur.view,
               "tier": e.tier, "form": e.form, "scenes": e.scenes}
        for days in (7, 30):
            ref = None
            for s in reversed(e.snapshots[:-1]):
                if (cur.captured_at - s.captured_at).days >= days:
                    ref = s
                    break
            row[f"growth_{days}d"] = (cur.view - ref.view) if ref else None
        out.append(row)
    out.sort(key=lambda r: r.get("growth_7d") or 0, reverse=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zfq.track", description="跟踪刷新")
    ap.add_argument("--cross-check", type=int, default=5,
                    help="双面交叉验证条数（0 关闭）")
    ap.add_argument("--max", type=int, default=0, help="最多处理条数（0=全部）")
    args = ap.parse_args(argv)

    entries = load_entries()
    if args.max:
        entries = entries[:args.max]
    client = PoliteClient()
    now = utcnow()
    changed = 0
    for e in entries:
        if e.status != "ok":
            continue
        payload = fetch_view(client, e.bvid)
        if payload is None:
            continue
        code = payload.get("__code")
        if code == -404:
            e.status = "deleted"
            e.notes = (e.notes + f" | {now.date().isoformat()} API -404 判失效").strip(" |")
            save_entry(e)
            print(f"  [deleted] {e.bvid} {e.title[:36]}")
            continue
        if code is not None:
            e.status = "invisible"
            print(f"  [invisible?] {e.bvid} code={code}")
            continue
        save_raw_view(e.bvid, payload, now)
        if append_snapshot(e, view_to_snapshot(payload["data"], now)):
            changed += 1
            save_entry(e)
    print(f"[track] 刷新 {len(entries)} 条，变化 {changed} 条")

    cc = cross_check(client, entries, args.cross_check) if args.cross_check else []
    n_ok = sum(1 for r in cc if r["result"] == "consistent")
    n_bad = sum(1 for r in cc if r["result"] == "mismatch")
    n_unp = sum(1 for r in cc if r["result"] == "page-unparseable")
    n_api = sum(1 for r in cc if r["result"] == "api-failed")
    print(f"[cross-check] 一致 {n_ok}/{len(cc)}"
          + (f"｜不一致 {n_bad} ← 人工核！" if n_bad else "")
          + (f"｜页面不可解析 {n_unp}" if n_unp else "")
          + (f"｜API失败 {n_api}" if n_api else ""))

    deltas = compute_deltas(load_entries(), now)
    config.CURATED_DIR.mkdir(parents=True, exist_ok=True)
    (config.CURATED_DIR / "deltas.json").write_text(
        json.dumps({"generated_at": now.isoformat(timespec="seconds"),
                    "rows": deltas}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # 人类可读跟踪报告
    lines = [
        "# 跟踪报告（自动生成）", "",
        f"- 生成时间：{now.isoformat(timespec='seconds')}",
        f"- 刷新条目：{len(entries)}（变化 {changed}）",
        f"- 双面交叉验证：一致 {n_ok}/{len(cc)}"
        + (f"，不一致 {n_bad}（人工核），页面不可解析 {n_unp}，API 失败 {n_api}"
           if (n_bad or n_unp or n_api) else ""), "",
        "## 7 天播放涨幅榜（Top 20）", "",
        "| # | 播放 | 7d增量 | 30d增量 | 分级 | 形态 | 标题 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(deltas[:20], 1):
        g7 = r.get("growth_7d")
        g30 = r.get("growth_30d")
        lines.append(
            f"| {i} | {r['view']:,} | {g7 if g7 is not None else '—':,} "
            f"| {g30 if g30 is not None else '—':,} | {r['tier']} | {r['form']} "
            f"| [{r['title'][:40]}]({config.URL_VIDEO_PAGE.format(bvid=r['bvid'])}) |"
            if g7 is not None else
            f"| {i} | {r['view']:,} | — | — | {r['tier']} | {r['form']} "
            f"| [{r['title'][:40]}]({config.URL_VIDEO_PAGE.format(bvid=r['bvid'])}) |")
    cc_dir = config.REPORTS_DIR
    cc_dir.mkdir(parents=True, exist_ok=True)
    (cc_dir / "tracking-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (cc_dir / "cross-check.json").write_text(
        json.dumps(cc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[out] reports/tracking-report.md, reports/cross-check.json, data/curated/deltas.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
