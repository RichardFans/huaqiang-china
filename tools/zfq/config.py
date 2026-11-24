# -*- coding: utf-8 -*-
"""zfq（征服档案）全局配置：路径、采集礼仪参数、收录门槛。

代号只存在于代码层（包名 zfq / 仓库名 huaqiang-china），界面名见 ADR-0003。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ---- 数据目录 ----
DATA_DIR = ROOT / "data"
ENTRIES_DIR = DATA_DIR / "entries"          # 每视频一文件：BVxxxx.json
CREATORS_DIR = DATA_DIR / "creators"        # 每 UP 主一文件：mid.json
SNAPSHOTS_DIR = DATA_DIR / "snapshots"      # 原始 API 响应（仅元数据 JSON）
CANDIDATES_DIR = DATA_DIR / "candidates"    # 未过门槛候选与拒绝记录
CURATED_DIR = DATA_DIR / "curated"          # 管线生成的切面视图（禁止手改）
REPORTS_DIR = ROOT / "reports"
SITE_DATA_DIR = ROOT / "site" / "src" / "data" / "generated"
SITE_FEEDS_DIR = ROOT / "site" / "public" / "feeds"

# ---- 采集礼仪（ADR-0002）----
RATE_LIMIT_S = 1.0        # 请求间隔下限（秒）
RATE_JITTER_S = 0.4       # 随机抖动上限（秒）
MAX_REQUESTS_PER_RUN = 400
RETRY_BACKOFF_BASE_S = 5  # 指数退避基数

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BASE_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# ---- 收录门槛（ADR-0001）----
TIER_VIEW_THRESHOLDS = {
    "hall": 10_000_000,
    "hot": 1_000_000,
    "rising": 100_000,   # 另须发布 ≤180 天
}
RISING_MAX_AGE_DAYS = 180

# ---- 端点（全部为无登录浏览器可直接打开的公开地址，ADR-0005）----
URL_HOME = "https://www.bilibili.com/"
URL_SEARCH = "https://search.bilibili.com/all"
URL_VIEW = "https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
URL_RELATION = "https://api.bilibili.com/x/relation/stat?vmid={mid}"
URL_VIDEO_PAGE = "https://www.bilibili.com/video/{bvid}"

# ---- 词表常量（与 data/vocabulary.md 同步，tests 校验一致性）----
SCENES = ("maigua", "song-laohu-banquet", "feng-biao", "zhengfu-other", "crossover")
FORMS = ("source", "clip", "guichu", "yinmad", "ai-cover", "ai-video", "ai-other", "other")
TIERS = ("hall", "hot", "rising", "seed")
KINDS = ("derivative", "source")

# 检索关键词 → scene 归属（用于候选的 scene 初判，条目仍须记录判定依据）
KEYWORD_SCENE_MAP = {
    "华强买瓜": ("maigua",),
    "刘华强": ("maigua",),
    "孙红雷 买瓜": ("maigua",),
    "你这瓜保熟吗": ("maigua",),
    "宋老虎": ("song-laohu-banquet",),
    "封彪": ("feng-biao",),
    "疯飙": ("feng-biao",),          # 谐音错写，词表实证
    "征服 鬼畜": ("zhengfu-other",),
    "征服 名场面": ("zhengfu-other",),
    "保熟": ("maigua",),
}

SITE_TITLE_ZH = "征服二创宇宙档案"
SITE_TITLE_EN = "The Conquest Remix Archive"

# ---- 检索面观测上限（ADR-0009 修订）----
# 2026-11-24 实测：五个关键词 searchAllResponse.numResults 均为 1000、numPages 均为 50
# （50 页 × 20 条），与关键词无关、首页候选数各异 → 平台检索面封顶，真实总量不可知。
# 证据：data/snapshots/2026-11-24/search/*.json；汇总：docs/evidence/search-surface.md
SEARCH_RESULTS_CAP = 1000
