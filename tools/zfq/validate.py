# -*- coding: utf-8 -*-
"""质量门禁：CI 上跑的校验规则集（docs/verification.md）。

规则（任一 FAIL → 退出码 1，阻断合并）：
  R1 条目/UP主文件 pydantic 模型校验通过
  R2 同批文件经 JSON Schema（pydantic 导出）第二通道校验通过——双保险
  R3 scenes/form/tier ∈ 受控词表，且 slug 与 data/vocabulary.md 同步
  R4 计数单调性：view/like/coin/favorite/share/danmaku 随时间不减（相等允许）
  R5 快照 (endpoint, date) 唯一
  R6 seed 必填 tier_basis；auto 形态必填 form_evidence（模型层兜底，此处复查）
  R8 cover 与最晚 view 快照的 pic 一致，且有 cover_evidence（ADR-0007；跑 zfq mine 修复）
  R9 data/curated/graph.json 与按当前数据重建的图谱一致（ADR-0008；重跑 zfq build 修复）
  R10 时间线 SVG 三变体与按当前数据重建结果逐字节一致（README hero / 站点桌面 / 站点移动）
  R11 创作者星图 SVG（README 与站点各一份）与重建结果逐字节一致（ADR-0008）
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import jsonschema

from . import config
from .mine import latest_cover_from_snapshots
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


def _readme_drift_errors() -> list[str]:
    """R7：README 生成区必须与当前数据一致（重跑 zfq build 可修复）。"""
    from .build import README_OUTPUTS, readme_file_content

    errs = []
    for lang, path in README_OUTPUTS.items():
        if not path.exists():
            errs.append(f"R7 {path.name} 缺失（跑 zfq build 生成）")
            continue
        current = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        expected = readme_file_content(lang)
        if current != expected:
            errs.append(f"R7 {path.name} 与数据漂移（重跑 zfq build 后提交）")
    return errs


def _generated_svg_errors() -> list[str]:
    """R10/R11：由数据生成的 SVG（时间线三变体、创作者星图两份）必须与按当前数据
    重建的结果逐字节一致（重跑 zfq build 修复）。"""
    from .build import TIMELINE_ASSETS
    from .graph import build_graph, to_svg
    from .timeline import build_timeline_svg
    from .track import load_entries

    entries = load_entries()
    checks = [(f"R10 {rel}", build_timeline_svg(entries, variant=v, chrome=c))
              for rel, v, c in TIMELINE_ASSETS]
    svg = to_svg(build_graph(entries))
    checks += [("R11 docs/assets/creator-map.svg", svg),
               ("R11 site/src/data/generated/creator-map.svg", svg)]
    errs: list[str] = []
    for label, expected in checks:
        path = config.ROOT / label.split(" ", 1)[1]
        if not path.exists():
            errs.append(f"{label} 缺失（跑 zfq build 生成）")
        elif path.read_text(encoding="utf-8") != expected:
            errs.append(f"{label} 与数据漂移（重跑 zfq build 后提交）")
    return errs


def _graph_drift_errors() -> list[str]:
    """R9：graph.json 必须与当前数据+快照重建结果一致。"""
    from .graph import build_graph

    path = config.CURATED_DIR / "graph.json"
    if not path.exists():
        return ["R9 data/curated/graph.json 缺失（跑 zfq build 生成）"]
    import json as _json

    current = _json.loads(path.read_text(encoding="utf-8"))
    expected = build_graph()
    if current != expected:
        return ["R9 graph.json 与数据漂移（重跑 zfq build 后提交）"]
    return []


def validate_all(check_readme: bool = True) -> tuple[list[str], dict, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
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
        # R4 单调性：仅同端点序列内比较（跨端点有时差与口径微差，实测教训）；
        # 小幅回退（≤1% 且 ≤1000）是平台计数回收（如取消赞聚合），降级为警告
        snaps = sorted(e.snapshots, key=lambda s: s.captured_at)
        by_ep: dict[str, list] = {}
        for s in snaps:
            by_ep.setdefault(s.endpoint, []).append(s)
        for ep, series in by_ep.items():
            for prev, cur in zip(series, series[1:]):
                for f in ("view", "like", "coin", "favorite", "share", "danmaku"):
                    pv, cv = getattr(prev, f), getattr(cur, f)
                    if cv < pv:
                        msg = (f"R4 {e.bvid}[{ep}]: {f} 回退 {pv}→{cv} "
                               f"({prev.captured_at}→{cur.captured_at})")
                        if pv > 0 and (pv - cv) <= max(1000, pv * 0.01):
                            warnings.append(msg + "（幅度小，计为警告）")
                        else:
                            errors.append(msg)
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
        # R8 封面一致性（ADR-0007；与 mine.latest_cover_from_snapshots 同源）
        pic, _ = latest_cover_from_snapshots(e.bvid)
        if e.cover != pic:
            errors.append(f"R8 {e.bvid}: cover 应为快照 pic {pic!r}，"
                          f"实际 {e.cover!r}（跑 python -m zfq.mine 修复）")
        elif pic and not e.cover_evidence:
            errors.append(f"R8 {e.bvid}: 有 cover 但缺 cover_evidence")

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
    errors += _graph_drift_errors()
    errors += _generated_svg_errors()
    if check_readme:
        errors += _readme_drift_errors()
    return errors, dict(stats), warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="zfq.validate")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args(argv)
    errors, stats, warnings = validate_all()
    report = {"stats": stats, "errors": errors, "warnings": warnings,
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
