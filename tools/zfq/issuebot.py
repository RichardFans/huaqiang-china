# -*- coding: utf-8 -*-
"""issue 机器人：解析「提交视频」issue → view 端点校验 → 生成 seed 条目 + 评论稿。

用法：python -m zfq.issuebot --issue 42 --body-file body.md
产物：data/entries/BVxxxx.json（method=manual-issue，review=pending）+
      tmp/issuebot-comment.md（供 workflow 回帖）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import config
from .client import PoliteClient
from .ingest import auto_tier, guess_form, save_raw_view, view_to_snapshot
from .schema import DiscoveryInfo, Entry, Owner, utcnow

BVID_RE = re.compile(r"BV[0-9A-Za-z]{10}")
SCENE_HINT_RE = re.compile(r"桥段[:：]?\s*(\S+)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zfq.issuebot")
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--body-file", type=str, required=True)
    args = ap.parse_args(argv)

    body = Path(args.body_file).read_text(encoding="utf-8")
    comment_path = config.ROOT / "tmp" / "issuebot-comment.md"
    comment_path.parent.mkdir(parents=True, exist_ok=True)

    m = BVID_RE.search(body)
    if not m:
        comment_path.write_text(
            "未在 issue 中识别到 BV 号（形如 BV1xx411c7mD）。请补充分享链接或 BV 号后"
            "重新提交。", encoding="utf-8")
        print("[issuebot] 无 BV 号")
        return 1
    bvid = m.group(0)

    if (config.ENTRIES_DIR / f"{bvid}.json").exists():
        comment_path.write_text(
            f"{bvid} 已在册，感谢反馈。如数据有误请改用「纠错」模板。", encoding="utf-8")
        return 0

    client = PoliteClient()
    try:
        payload = client.get_json(config.URL_VIEW.format(bvid=bvid))
    except Exception as e:  # noqa: BLE001
        comment_path.write_text(
            f"view 端点校验失败（{e!r}）。请确认视频公开可见后重试。", encoding="utf-8")
        return 1
    if payload.get("code") != 0:
        comment_path.write_text(
            f"校验失败：API code={payload.get('code')}（视频可能不存在/非公开）。", encoding="utf-8")
        return 1

    data = payload["data"]
    now = utcnow()
    save_raw_view(bvid, payload, now)
    snap = view_to_snapshot(data, now)
    from datetime import datetime, timezone
    pub = datetime.fromtimestamp(data["pubdate"], tz=timezone.utc)
    tier, tier_basis = auto_tier(snap.view, pub, now)
    if not tier:
        tier = "seed"
        tier_basis = f"issue #{args.issue} 提交，播放 {snap.view:,} 低于自动门槛，转人工评审"
    form, form_ev = guess_form(data.get("title", ""))

    scene_hint = SCENE_HINT_RE.search(body)
    scenes = []
    if scene_hint:
        hint = scene_hint.group(1)
        for slug, zh in (("maigua", "买瓜"), ("song-laohu-banquet", "宋老虎"),
                         ("feng-biao", "封彪"), ("crossover", "联动")):
            if zh in hint:
                scenes.append(slug)
    if not scenes:
        scenes = ["zhengfu-other"]

    entry = Entry(
        bvid=bvid, aid=data.get("aid"), title=data.get("title", ""),
        owner=Owner(mid=data["owner"]["mid"], name=data["owner"]["name"]),
        pubdate=pub, duration_s=data.get("duration"), tname=data.get("tname"),
        kind="derivative", scenes=scenes,  # type: ignore[arg-type]
        scene_evidence=f"issue #{args.issue} 提交者指定/默认，待复核",
        scene_status="auto",
        form=form,  # type: ignore[arg-type]
        form_status="auto", form_evidence=form_ev,
        tier=tier,  # type: ignore[arg-type]
        tier_basis=tier_basis,
        discovered_via=DiscoveryInfo(method="manual-issue", captured_at=now),
        first_seen=now, snapshots=[snap],
        notes=f"由 issue #{args.issue} 提交",
    )
    config.ENTRIES_DIR.mkdir(parents=True, exist_ok=True)
    (config.ENTRIES_DIR / f"{bvid}.json").write_text(
        entry.model_dump_json(indent=2), encoding="utf-8")

    lines = [
        f"✅ 校验通过，已生成入册 PR（`review=pending`，待人工评审）：",
        "", f"- **{data.get('title', '')}**",
        f"- UP主：{data['owner']['name']} ｜ 发布：{pub.date().isoformat()}",
        f"- 播放 {snap.view:,} ｜ 点赞 {snap.like:,} ｜ 硬币 {snap.coin:,}",
        f"- 初判：{tier}（{tier_basis}）｜ 形态 {form}（{form_ev}）",
        "", "数据来自 view 端点实时校验（快照时间见条目）。感谢贡献！",
    ]
    comment_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[issuebot] {bvid} 校验通过并生成条目")
    return 0


if __name__ == "__main__":
    sys.exit(main())
