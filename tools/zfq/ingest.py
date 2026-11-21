# -*- coding: utf-8 -*-
"""入册流程：候选 → view 端点富化 → 过收录门槛（ADR-0001）→ 写 entries/creators。

自动判定（scene/form/tier）一律标 auto 并留判定依据；人工复核后改 confirmed。
未过门槛的候选写入 data/candidates/ 拒绝日志——「为什么没收录」也是档案的一部分。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .client import PoliteClient
from .schema import DiscoveryInfo, Entry, FollowerSnapshot, NameRecord, Owner, Snapshot, Creator, utcnow
from .search import Candidate, harvest

# 形态初判关键词（按优先级；只产生 auto 判定，不是结论）
# 注：AI 不加 \b ——中文与 AI 相邻时无词边界（实测：「能控制AI」漏判）
AI_PAT = re.compile(r"AI|人工智能|so-?vits|RVC|语音克隆|豆包|SUNO|Suno", re.I)
SING_PAT = re.compile(r"翻唱|唱|歌|念白|朗读|RAP|rap|MV|音乐")
GUICHU_PAT = re.compile(r"鬼畜")
SPACED_TITLE_PAT = re.compile(r"(?:\S\s){4,}\S")  # 「无 伤 反 杀 刘 华 强」式空格标题：鬼畜区文化特征
YINMAD_PAT = re.compile(r"音\s?MAD|音mad", re.I)
CLIP_PAT = re.compile(r"剪辑|混剪|速通|合集|名场面|盘点|重制|修复|字幕|配音")
AIVIDEO_PAT = re.compile(r"AI视频|生成视频|可灵|即梦|Sora|sora|Veo", re.I)
# scene 标题线索
SCENE_TITLE_PAT = [
    (re.compile(r"买瓜|保熟|西瓜|瓜摊|卖瓜|劈瓜"), "maigua"),
    (re.compile(r"宋老虎"), "song-laohu-banquet"),
    (re.compile(r"封彪|疯飙"), "feng-biao"),
]


def guess_form(title: str) -> tuple[str, str]:
    """返回 (form, evidence)。只做标题级初判。"""
    if AIVIDEO_PAT.search(title):
        return "ai-video", f"标题命中生成式视频关键词：{AIVIDEO_PAT.search(title).group(0)}"
    if AI_PAT.search(title):
        if SING_PAT.search(title):
            return "ai-cover", f"标题命中 AI+声音/音乐关键词：{AI_PAT.search(title).group(0)}+{SING_PAT.search(title).group(0)}"
        return "ai-other", f"标题命中 AI 关键词：{AI_PAT.search(title).group(0)}"
    if YINMAD_PAT.search(title):
        return "yinmad", "标题命中 音MAD"
    if GUICHU_PAT.search(title):
        return "guichu", "标题命中 鬼畜"
    if SPACED_TITLE_PAT.search(title):
        return "guichu", "空格标题（鬼畜区命名文化特征，启发式，待复核）"
    if CLIP_PAT.search(title):
        return "clip", f"标题命中剪辑类关键词：{CLIP_PAT.search(title).group(0)}"
    return "clip", "无明确形态线索，默认 clip（待人工复核）"


def title_scene_hits(title: str) -> list[str]:
    return [slug for pat, slug in SCENE_TITLE_PAT if pat.search(title)]


def guess_scenes(cand: Candidate) -> tuple[list[str], str, str]:
    """返回 (scenes, evidence, scene_status)。标题显式命中 → confirmed（标题即一手线索）。"""
    scenes: list[str] = title_scene_hits(cand.title)
    kw_scenes = config.KEYWORD_SCENE_MAP.get(cand.keyword, ())
    for s in kw_scenes:
        if s not in scenes:
            scenes.append(s)
    if not scenes:
        scenes = ["zhengfu-other"]
    if title_scene_hits(cand.title):
        status = "confirmed"
        basis = f"标题显式命中桥段词（{'+'.join(title_scene_hits(cand.title))}）；检索词『{cand.keyword}』补全"
    else:
        status = "auto"
        basis = (f"仅检索词『{cand.keyword}』相关性命中（标题无桥段词），低置信，复核优先")
    return scenes, basis, status


def view_to_snapshot(data: dict, now: datetime) -> Snapshot:
    st = data.get("stat", {})
    return Snapshot(
        captured_at=now, endpoint="api-view",
        view=st.get("view", 0), like=st.get("like", 0), coin=st.get("coin", 0),
        favorite=st.get("favorite", 0), share=st.get("share", 0),
        danmaku=st.get("danmaku", 0), reply=st.get("reply", 0),
    )


def auto_tier(view: int, pubdate: datetime | None, now: datetime) -> tuple[str, str]:
    if view >= config.TIER_VIEW_THRESHOLDS["hall"]:
        return "hall", f"播放 {view:,} ≥ 1000万（ADR-0001 v1 门槛）"
    if view >= config.TIER_VIEW_THRESHOLDS["hot"]:
        return "hot", f"播放 {view:,} ≥ 100万（ADR-0001 v1 门槛）"
    if (pubdate and view >= config.TIER_VIEW_THRESHOLDS["rising"]
            and (now - pubdate).days <= config.RISING_MAX_AGE_DAYS):
        return "rising", f"播放 {view:,} ≥ 10万 且发布 ≤180 天（ADR-0001 v1 门槛）"
    return "", f"播放 {view:,} 低于自动门槛（10万）"


def upsert_creator(client: PoliteClient, mid: int, name: str, now: datetime) -> None:
    path = config.CREATORS_DIR / f"{mid}.json"
    if path.exists():
        creator = Creator.model_validate_json(path.read_text(encoding="utf-8"))
        if not creator.names_history or creator.names_history[-1].name != name:
            creator.names_history.append(NameRecord(name=name, captured_at=now))
    else:
        creator = Creator(mid=mid, names_history=[NameRecord(name=name, captured_at=now)])
    # 粉丝数快照
    try:
        rel = client.get_json(config.URL_RELATION.format(mid=mid))
        if rel.get("code") == 0:
            f = rel.get("data", {}).get("follower")
            if isinstance(f, int):
                creator.follower_snapshots.append(
                    FollowerSnapshot(captured_at=now, follower=f))
    except Exception as e:  # noqa: BLE001 — 粉丝端点失败不阻断入册
        print(f"  [warn] 粉丝端点失败 mid={mid}: {e!r}")
    config.CREATORS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(creator.model_dump_json(indent=2), encoding="utf-8")


def save_raw_view(bvid: str, payload: dict, now: datetime) -> Path:
    day = now.strftime("%Y-%m-%d")
    d = config.SNAPSHOTS_DIR / day / "view"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{bvid}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def ingest_candidates(
    cands: list[Candidate],
    client: PoliteClient,
    *,
    source_label: str = "search-html",
    dry_run: bool = False,
    include_sources: bool = False,
) -> tuple[list[Entry], list[dict]]:
    """富化 + 门槛过滤。返回 (收录, 拒绝记录)。"""
    accepted: list[Entry] = []
    rejected: list[dict] = []
    now = utcnow()
    for cand in cands:
        if (config.ENTRIES_DIR / f"{cand.bvid}.json").exists():
            continue  # 已在册，跟踪归 track.py
        try:
            payload = client.get_json(config.URL_VIEW.format(bvid=cand.bvid))
        except Exception as e:  # noqa: BLE001
            rejected.append({**cand.to_dict(), "reason": f"view 端点失败: {e!r}"})
            continue
        if payload.get("code") != 0:
            rejected.append({**cand.to_dict(),
                             "reason": f"view 返回 code={payload.get('code')}"})
            continue
        data = payload["data"]
        save_raw_view(cand.bvid, payload, now)
        snap = view_to_snapshot(data, now)
        pub_iso = datetime.fromtimestamp(data["pubdate"], tz=timezone.utc)
        tier, tier_basis = auto_tier(snap.view, pub_iso, now)
        form, form_evidence = guess_form(data.get("title", cand.title))
        scenes, scene_evidence, scene_status = guess_scenes(cand)
        if not tier:
            rejected.append({**cand.to_dict(), "view": snap.view,
                             "reason": tier_basis})
            continue
        entry = Entry(
            bvid=cand.bvid, aid=data.get("aid"),
            title=data.get("title", cand.title),
            owner=Owner(mid=data["owner"]["mid"], name=data["owner"]["name"]),
            pubdate=pub_iso,
            duration_s=data.get("duration"),
            tname=data.get("tname"),
            kind="derivative",
            scenes=scenes,  # type: ignore[arg-type]
            scene_evidence=scene_evidence,
            scene_status=scene_status,  # type: ignore[arg-type]
            form=form,  # type: ignore[arg-type]
            form_status="auto", form_evidence=form_evidence,
            tier=tier,  # type: ignore[arg-type]
            tier_basis=tier_basis,
            discovered_via=DiscoveryInfo(
                method="search-html", keyword=cand.keyword, order=cand.order,
                captured_at=now),
            first_seen=now,
            snapshots=[snap],
        )
        accepted.append(entry)
        if not dry_run:
            config.ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
            (config.ENTRIES_DIR / f"{cand.bvid}.json").write_text(
                entry.model_dump_json(indent=2), encoding="utf-8")
            upsert_creator(client, entry.owner.mid, entry.owner.name, now)
    return accepted, rejected


def log_rejected(rejected: list[dict]) -> None:
    if not rejected:
        return
    config.CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).date().isoformat()
    with (config.CANDIDATES_DIR / f"rejected-{day}.jsonl").open("a", encoding="utf-8") as f:
        for r in rejected:
            r["reviewed_at"] = utcnow().isoformat(timespec="seconds")
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zfq.ingest", description="搜索发现→入册")
    ap.add_argument("--keywords", required=True, help="逗号分隔，须已登记 data/vocabulary.md")
    ap.add_argument("--order", default="click", choices=["click", "pubdate"])
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    unknown = [k for k in keywords if k not in config.KEYWORD_SCENE_MAP]
    if unknown:
        print(f"[拒] 关键词未登记词表（vocabulary.md §6）：{unknown}")
        return 2

    client = PoliteClient()
    all_cands: dict[str, Candidate] = {}
    for kw in keywords:
        cands, total = harvest(
            kw, order=args.order, pages=args.pages, client=client,
            save_manifest_dir=config.SNAPSHOTS_DIR / utcnow().strftime("%Y-%m-%d") / "search")
        print(f"[harvest] {kw} ({args.order}) 总数≈{total:,}，本页候选 {len(cands)}")
        for c in cands:
            all_cands.setdefault(c.bvid, c)

    print(f"[ingest] 去重后候选 {len(all_cands)}，开始富化……")
    accepted, rejected = ingest_candidates(list(all_cands.values()), client,
                                           dry_run=args.dry_run)
    for e in accepted:
        v = e.latest.view if e.latest else 0
        print(f"  [+] {e.bvid}  {v:>12,}  {e.tier:<6} {e.form:<8} {e.scenes} {e.title[:40]}")
    for r in rejected[:20]:
        print(f"  [-] {r['bvid']}  {r.get('view', r.get('play', 0)):>12,}  {r['reason'][:50]}"
              f"  {r['title'][:30]}")
    if len(rejected) > 20:
        print(f"  ……拒绝共 {len(rejected)} 条（详见 data/candidates/）")
    if not args.dry_run:
        log_rejected(rejected)
    print(f"[done] 收录 {len(accepted)} / 拒绝 {len(rejected)}"
          f"{'（dry-run 未落盘）' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
