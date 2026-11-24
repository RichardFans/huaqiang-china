# -*- coding: utf-8 -*-
"""数据模型：pydantic v2 为主，同步导出 JSON Schema 供双通道校验（docs/verification.md）。

设计原则：每条数据自带证据链——发现渠道（discovered_via）、形态/分级判定依据、
带端点与时间戳的快照数组。计数是时点值，不是恒量。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from . import config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


# ---- 受控词表引用（与 data/vocabulary.md 同步，tests 校验）----
Scene = Literal["maigua", "song-laohu-banquet", "feng-biao", "zhengfu-other", "crossover"]
Form = Literal["source", "clip", "guichu", "yinmad", "ai-cover", "ai-video", "ai-other", "other"]
Tier = Literal["hall", "hot", "rising", "seed"]
Kind = Literal["derivative", "source"]
Endpoint = Literal["api-view", "page-state", "search-html", "relation-stat"]
Status = Literal["ok", "deleted", "invisible"]
Method = Literal["search-html", "manual-issue", "external-lead"]


class Owner(BaseModel):
    mid: int
    name: str


class DiscoveryInfo(BaseModel):
    method: Method
    keyword: str | None = None
    order: str | None = None
    captured_at: datetime


class Snapshot(BaseModel):
    captured_at: datetime
    endpoint: Endpoint
    view: int = 0
    like: int = 0
    coin: int = 0
    favorite: int = 0
    share: int = 0
    danmaku: int = 0
    reply: int = 0


class Entry(BaseModel):
    """一条视频 = 一个 JSON 文件（data/entries/BVxxxx.json）。"""

    bvid: str = Field(pattern=r"^BV[0-9A-Za-z]{10}$")
    aid: int | None = None
    title: str
    owner: Owner
    pubdate: datetime
    duration_s: int | None = None
    tname: str | None = None
    platform: Literal["bilibili"] = "bilibili"

    kind: Kind = "derivative"
    scenes: list[Scene]
    scene_evidence: str = ""      # 归属判定依据（auto 阶段必填）
    scene_status: Literal["auto", "confirmed"] = "auto"
    form: Form
    form_status: Literal["auto", "confirmed"] = "auto"
    form_evidence: str = ""       # auto 阶段必填
    tier: Tier
    tier_basis: str = ""          # seed 必填；自动门槛可注明规则版本
    review: Literal["pending", "confirmed"] = "pending"  # 整条人工复核状态（ADR-0006）

    status: Status = "ok"
    archive_url: str | None = None
    original_bvid: str | None = None  # 盗转关系指向原创

    cover: str | None = None           # 封面 URL（B站图床引用，字节不入库；ADR-0007）
    cover_evidence: str = ""           # 如 "mined: api-view@2026-11-21"，与 R8 校验联动

    discovered_via: DiscoveryInfo
    first_seen: datetime
    snapshots: list[Snapshot] = []
    notes: str = ""

    @field_validator("scenes")
    @classmethod
    def _scenes_nonempty(cls, v: list[Scene]) -> list[Scene]:
        if not v:
            raise ValueError("scenes 不能为空（至少归属一个桥段或 crossover）")
        return v

    @model_validator(mode="after")
    def _audit_fields(self) -> "Entry":
        if self.tier == "seed" and not self.tier_basis:
            raise ValueError("seed 分级必须填写 tier_basis")
        if self.form_status == "auto" and not self.form_evidence:
            raise ValueError("auto 形态必须留下 form_evidence 判定依据")
        if self.scene_status == "auto" and not self.scene_evidence:
            raise ValueError("auto 桥段归属必须留下 scene_evidence 判定依据")
        if self.review == "confirmed":
            if self.form_status != "confirmed" or self.scene_status != "confirmed":
                raise ValueError("整条 confirmed 前提：form 与 scene 均须 confirmed")
        if self.kind == "derivative" and self.form == "source":
            raise ValueError("derivative 不能用 source 形态")
        if self.kind == "source" and self.form != "source":
            raise ValueError("source 条目形态必须为 source")
        return self

    # ---- 便捷视图 ----
    @property
    def latest(self) -> Snapshot | None:
        return self.snapshots[-1] if self.snapshots else None

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"


class NameRecord(BaseModel):
    name: str
    captured_at: datetime


class FollowerSnapshot(BaseModel):
    captured_at: datetime
    follower: int


class Creator(BaseModel):
    """一位 UP 主 = 一个 JSON 文件（data/creators/mid.json）。"""

    mid: int
    names_history: list[NameRecord] = []
    follower_snapshots: list[FollowerSnapshot] = []
    role: str = ""                # 开创者/放大器/长青树…（人工评审填写）
    representative: list[str] = []
    notes: str = ""

    @property
    def current_name(self) -> str:
        return self.names_history[-1].name if self.names_history else f"mid:{self.mid}"


# ---- JSON Schema 导出（双通道校验之二，validate.py 使用）----
ENTRY_JSON_SCHEMA: dict = Entry.model_json_schema()
CREATOR_JSON_SCHEMA: dict = Creator.model_json_schema()
