# -*- coding: utf-8 -*-
"""评审命令（ADR-0006 评审门控的人工/半自动侧）。

- --auto-confirm-scenes：标题显式命中桥段词的条目，scene 升 confirmed（标题即一手线索）
- --set-review BVxxxx [--status confirmed|pending] [--note ...]：整条复核状态翻转
- --set-form BVxxxx --form guichu --note ...：人工定形态（form_status→confirmed）
"""
from __future__ import annotations

import argparse
import sys

from .ingest import title_scene_hits
from .track import load_entries, save_entry


def auto_confirm_scenes() -> int:
    entries = load_entries()
    n = 0
    for e in entries:
        if e.scene_status == "confirmed":
            continue
        hits = title_scene_hits(e.title)
        if hits:
            e.scene_status = "confirmed"
            e.scene_evidence = (
                f"标题显式命中桥段词（{'+'.join(hits)}）——"
                f"review --auto-confirm-scenes 于存量迁移")
            save_entry(e)
            n += 1
    print(f"[review] scene 升 confirmed：{n} 条（标题显式命中）")
    return 0


def set_review(bvid: str, status: str, note: str) -> int:
    entries = load_entries()
    for e in entries:
        if e.bvid == bvid:
            e.review = status  # type: ignore[assignment]
            if note:
                e.notes = (e.notes + " | " + note).strip(" |")
            save_entry(e)
            print(f"[review] {bvid} → review={status}")
            return 0
    print(f"[review] 未找到 {bvid}")
    return 1


def set_form(bvid: str, form: str, note: str) -> int:
    entries = load_entries()
    for e in entries:
        if e.bvid == bvid:
            e.form = form  # type: ignore[assignment]
            e.form_status = "confirmed"
            e.form_evidence = f"人工复核：{note or '（未填依据）'}"
            if e.review == "confirmed":
                pass  # 保持；form 与 scene 均 confirmed 才允许整条 confirmed
            save_entry(e)
            print(f"[review] {bvid} → form={form} (confirmed)")
            return 0
    print(f"[review] 未找到 {bvid}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zfq.review")
    ap.add_argument("--auto-confirm-scenes", action="store_true")
    ap.add_argument("--set-review", metavar="BVID")
    ap.add_argument("--status", default="confirmed",
                    choices=["confirmed", "pending"])
    ap.add_argument("--set-form", metavar="BVID")
    ap.add_argument("--form", choices=["source", "clip", "guichu", "yinmad",
                                       "ai-cover", "ai-video", "ai-other", "other"])
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)
    if args.auto_confirm_scenes:
        return auto_confirm_scenes()
    if args.set_review:
        return set_review(args.set_review, args.status, args.note)
    if args.set_form and args.form:
        return set_form(args.set_form, args.form, args.note)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
