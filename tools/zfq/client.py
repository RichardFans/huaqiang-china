# -*- coding: utf-8 -*-
"""礼貌 HTTP 客户端：限速、抖动、预算、退避、风控即降级。

合规要点（ADR-0002）：不实现任何签名/风控绕过；遇风控信号（非 200、JSON 端点返回非
JSON、-412）指数退避重试，仍失败则抛 RiskControlError 由上层终止当日任务。
"""
from __future__ import annotations

import random
import time
from typing import Any

import requests

from . import config


class BudgetExceeded(RuntimeError):
    """单次运行请求预算耗尽——防失控的硬闸门。"""


class RiskControlError(RuntimeError):
    """疑似风控：重试后仍不可用。调用方应中止而非对抗。"""


class PoliteClient:
    def __init__(
        self,
        *,
        rate_s: float = config.RATE_LIMIT_S,
        jitter_s: float = config.RATE_JITTER_S,
        max_requests: int = config.MAX_REQUESTS_PER_RUN,
        warmup: bool = True,
    ) -> None:
        self.rate_s = rate_s
        self.jitter_s = jitter_s
        self.max_requests = max_requests
        self._count = 0
        self._last_ts = 0.0
        self.session = requests.Session()
        self.session.headers.update(config.BASE_HEADERS)
        if warmup:
            # 浏览器等价：访问首页取得游客 cookie（buvid3 等），不登录
            try:
                self.session.get(config.URL_HOME, timeout=15)
            except requests.RequestException:
                pass  # 预热失败不致命，后续请求自会暴露问题

    # -- 礼貌节流 --
    def _throttle(self) -> None:
        wait = self.rate_s + random.uniform(0, self.jitter_s)
        elapsed = time.monotonic() - self._last_ts
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_ts = time.monotonic()

    def _budget(self) -> None:
        if self._count >= self.max_requests:
            raise BudgetExceeded(
                f"请求预算 {self.max_requests} 已耗尽（防失控硬闸门，见 ADR-0002）")
        self._count += 1

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        expect_json: bool = False,
        retries: int = 3,
        timeout: int = 20,
    ) -> requests.Response:
        """带限速/预算/退避的 GET。expect_json=True 时校验响应确为 JSON。"""
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            self._budget()
            self._throttle()
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
                if resp.status_code == 200:
                    if not expect_json or self._looks_json(resp):
                        return resp
                    last_err = RiskControlError(
                        f"JSON 端点返回非 JSON（疑似风控页）：{url}")
                else:
                    last_err = RiskControlError(f"HTTP {resp.status_code}: {url}")
            except requests.RequestException as e:  # 网络/超时
                last_err = e
            if attempt < retries:
                time.sleep(config.RETRY_BACKOFF_BASE_S * (2 ** attempt))
        assert last_err is not None
        raise last_err

    @staticmethod
    def _looks_json(resp: requests.Response) -> bool:
        ct = resp.headers.get("Content-Type", "")
        if "json" in ct:
            return True
        head = resp.text[:1].lstrip()
        return head.startswith("{") or head.startswith("[")

    def get_json(self, url: str, **kw: Any) -> dict[str, Any]:
        resp = self.get(url, expect_json=True, **kw)
        return resp.json()  # type: ignore[no-any-return]
