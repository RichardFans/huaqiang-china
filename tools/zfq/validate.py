# -*- coding: utf-8 -*-
"""质量门禁：CI 上跑的校验规则集（docs/verification.md）。

规则（任一 FAIL → 退出码 1，阻断合并）：
  R1 条目/UP主文件 pydantic 模型校验通过
  R2 同批文件经 JSON Schema（pydantic 导出）第二通道校验通过——双保险
  R3 scenes/form/tier ∈ 受控词表，且 slug 与 data/vocabulary.md 同步
  R4 计数单调性：view/like/coin/favorite/share/danmaku 随时间不减（相等允许）
  R5 快照 (endpoint, date) 唯一
  R6 seed 必填 tier_basis；auto 形态必填 form_evidence（模型层兜底，此处复查）
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import jsonschema

from . import config
from .schema import CREATOR_JSON_SCHEMA, ENTRY_JSON_SCHEMA, Creator, Entry


def _slug_sync_ok() -> list[str]:
    vocab = (config.ROOT / "data" / "vocabulary.md").read_text(encoding="utf-8")
    errs = []
    for group, values in (("scenes", config.SCENES), ("form", config.FORMS),
                          ("tier", config.TIERS)):
        for v in values:
            if f"`{v}`" not in vocab:
                errs.append(f"R3 词表失同步：{group} 值 `{v}` 未出现在 vocabulary.md")
    return errs


def validate_all() -> tuple[list[str], dict]:
    errors: list[str] = []
    stats: Counter = Counter()
    entries = sorted(config.ENTRIES_DIR.glob("BV*.json"))
    creators = sorted(config.CREATORS_DIR.glob("*.json"))
    stats["entries"] = len(entries)
    stats["creators"] = len(creators)

    for p in entries:
        raw = json.loads(p.read_text(encoding="utf-8"))
        try:  # R1
            e = Entry.model_validate(raw)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"R1 {p.name}: {ex}")
            continue
        try:  # R2
            jsonschema.validate(raw, ENTRY_JSON_SCHEMA)
        except jsonschema.ValidationError as ex:
            errors.append(f"R2 {p.name}: {ex.message}")
        # R4 单调性
        snaps = sorted(e.snapshots, key=lambda s: s.captured_at)
        for prev, cur in zip(snaps, snaps[1:]):
            for f in ("view", "like", "coin", "favorite", "share", "danmaku"):
                if getattr(cur, f) < getattr(prev, f):
                    errors.append(
                        f"R4 {e.bvid}: {f} 回退 {getattr(prev, f)}→{getattr(cur, f)} "
                        f"({prev.captured_at}→{cur.captured_at})")
        # R5 快照唯一
        keys = [(s.endpoint, s.captured_at.date().isoformat()) for s in snaps]
        dup = [k for k, n in Counter(keys).items() if n > 1]
        if dup:
            errors.append(f"R5 {e.bvid}: 快照重复 {dup}")
        # R6
        if e.tier == "seed" and not e.tier_basis:
            errors.append(f"R6 {e.bvid}: seed 缺 tier_basis")
        if e.form_status == "auto" and not e.form_evidence:
            errors.append(f"R6 {e.bvid}: auto 形态缺 form_evidence")

    for p in creators:
        raw = json.loads(p.read_text(encoding="utf-8"))
        try:  # R1
            Creator.model_validate(raw)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"R1 {p.name}: {ex}")
            continue
        try:  # R2
            jsonschema.validate(raw, CREATOR_JSON_SCHEMA)
        except jsonschema.ValidationError as ex:
            errors.append(f"R2 {p.name}: {ex.message}")

    errors += _slug_sync_ok()
    return errors, dict(stats)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zfq.validate")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args(argv)
    errors, stats = validate_all()
    report = {"stats": stats, "errors": errors,
              "pass": not errors}
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    print(f"[validate] entries={stats.get('entries', 0)} "
          f"creators={stats.get('creators', 0)} errors={len(errors)}")
    for e in errors[:40]:
        print("  FAIL", e)
    if len(errors) > 40:
        print(f"  ……共 {len(errors)} 条")
    print("[validate] PASS" if not errors else "[validate] FAIL")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
