"""应用配置集中管理。"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    """应用配置。"""

    # 爬虫配置
    crawl_retries: int = int(os.getenv("CRAWL_RETRIES", "3"))
    crawl_timeout: int = int(os.getenv("CRAWL_TIMEOUT", "30"))
    crawl_delay_seconds: float = float(os.getenv("CRAWL_DELAY_SECONDS", "1"))
    crawl_retry_base_seconds: float = float(os.getenv("CRAWL_RETRY_BASE_SECONDS", "1"))

    # 数据配置
    job_list_default_limit: int = int(os.getenv("JOB_LIST_DEFAULT_LIMIT", "100"))
    job_list_max_limit: int = int(os.getenv("JOB_LIST_MAX_LIMIT", "500"))

    # 分析配置
    low_confidence_threshold: float = 0.65

    # 订阅推送调度配置
    subscription_scan_enabled: bool = os.getenv("SUBSCRIPTION_SCAN_ENABLED", "true").lower() == "true"
    subscription_scan_hour: int = int(os.getenv("SUBSCRIPTION_SCAN_HOUR", "9"))
    subscription_scan_minute: int = int(os.getenv("SUBSCRIPTION_SCAN_MINUTE", "0"))

    # 每日自动抓取（A3）：与订阅扫描同一时钟点，先抓取后扫描
    auto_crawl_enabled: bool = os.getenv("AUTO_CRAWL_ENABLED", "true").lower() == "true"


config = Config()
