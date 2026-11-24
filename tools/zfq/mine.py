# -*- coding: utf-8 -*-
"""封面回填：从库内 view 快照确定性挖掘 pic → entries.cover（ADR-0007）。

规则（与 validate R8 同源同逻辑）：
  - 取该 BV 最晚日期快照文件的 data.pic 作为 cover；
  - 无快照或 pic 缺失 → cover 必须为 None；
  - cover_evidence 记录来源端点与快照日期，构成证据链；
  - 幂等：无变化不写盘。
封面仅是 URL 引用（B站图床），本仓库不存储任何图片字节。
"""
from __future__ import annotations

import json
import sys

from . import config
from .schema import Entry


def latest_cover_from_snapshots(bvid: str) -> tuple[str | None, str]:
    """返回 (pic, evidence)。快照目录按日期命名，字典序即时间序。"""
    for view_dir in sorted(config.SNAPSHOTS_DIR.glob("*/view"), reverse=True):
        p = view_dir / f"{bvid}.json"
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("code") == 0:
            pic = (payload.get("data") or {}).get("pic")
            if pic:
                return pic, f"mined: api-view@{view_dir.parent.name}"
    return None, ""


def mine_all() -> tuple[int, int, int]:
    """回填全部 entries。返回 (总数, 修改数, 有封面数)。"""
    total = changed = with_cover = 0
    for p in sorted(config.ENTRIES_DIR.glob("BV*.json")):
        total += 1
        raw = json.loads(p.read_text(encoding="utf-8"))
        pic, ev = latest_cover_from_snapshots(p.stem)
        if pic:
            with_cover += 1
        if raw.get("cover") == pic and (not pic or raw.get("cover_evidence")):
            continue
        e = Entry.model_validate(raw)
        e = e.model_copy(update={"cover": pic, "cover_evidence": ev})
        p.write_text(e.model_dump_json(indent=2), encoding="utf-8")
        changed += 1
    return total, changed, with_cover


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    total, changed, with_cover = mine_all()
    print(f"[mine] entries={total} cover={with_cover} "
          f"changed={changed}（无快照的条目 cover 置空）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
