# -*- coding: utf-8 -*-
"""R1/R2/R6：模型与双通道 schema 行为测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from zfq.schema import DiscoveryInfo, Entry, Owner, Snapshot, utcnow


def _entry(**over):
    base = dict(
        bvid="BV1Ku4y1f7oe", title="华强买瓜速通版。",
        owner=Owner(mid=1, name="某人"),
        pubdate="2021-06-01T00:00:00+00:00",
        kind="derivative", scenes=["maigua"], scene_evidence="测试",
        form="clip", form_status="auto", form_evidence="测试",
        tier="hot", tier_basis="播放≥100万",
        discovered_via=DiscoveryInfo(method="search-html", keyword="华强买瓜",
                                     order="click", captured_at=utcnow()),
        first_seen=utcnow(),
        snapshots=[Snapshot(captured_at=utcnow(), endpoint="api-view", view=1)],
    )
    base.update(over)
    return base


def test_entry_ok():
    e = Entry.model_validate(_entry())
    assert e.bvid == "BV1Ku4y1f7oe"
    assert e.latest.view == 1


def test_entry_bad_bvid():
    with pytest.raises(ValidationError):
        Entry.model_validate(_entry(bvid="AV123"))


def test_entry_bad_scene():
    with pytest.raises(ValidationError):
        Entry.model_validate(_entry(scenes=["nonexistent"]))


def test_seed_requires_basis():
    with pytest.raises(ValidationError):
        Entry.model_validate(_entry(tier="seed", tier_basis=""))


def test_auto_form_requires_evidence():
    with pytest.raises(ValidationError):
        Entry.model_validate(_entry(form_evidence=""))


def test_kind_form_consistency():
    with pytest.raises(ValidationError):
        Entry.model_validate(_entry(kind="source", form="clip"))
    with pytest.raises(ValidationError):
        Entry.model_validate(_entry(kind="derivative", form="source"))
    Entry.model_validate(_entry(kind="source", form="source", scenes=["maigua"]))


def test_json_schema_export():
    js = Entry.model_json_schema()
    assert "properties" in js and "bvid" in js["properties"]
