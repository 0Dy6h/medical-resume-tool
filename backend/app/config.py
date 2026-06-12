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


config = Config()
