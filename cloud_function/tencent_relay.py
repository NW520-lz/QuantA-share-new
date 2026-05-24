# -*- coding: utf-8 -*-
"""
腾讯云函数（SCF）支付FM回调中转函数
部署地域：香港（ap-hongkong）或国内任意地域

环境变量（在 SCF 控制台配置）：
  OVERSEAS_SERVER_URL  - 海外服务器回调地址，如 https://your-domain.com/api/v1/billing/notify
  ALLOWED_IPS          - 允许的来源 IP（逗号分隔），留空不校验
                         支付FM IP 段：47.94.194.102/24 和 39.107.193.170/24
"""

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OVERSEAS_URL = os.environ.get("OVERSEAS_SERVER_URL", "")
ALLOWED_IPS = [ip.strip() for ip in os.environ.get("ALLOWED_IPS", "").split(",") if ip.strip()]


def _get_client_ip(event: dict) -> str:
    headers = event.get("headers") or {}
    return (
        headers.get("x-forwarded-for", "").split(",")[0].strip()
        or headers.get("x-real-ip", "")
        or event.get("requestContext", {}).get("sourceIp", "")
    )


def _forward_get(query_string: str) -> tuple[int, str]:
    if not OVERSEAS_URL:
        logger.error("OVERSEAS_SERVER_URL not configured")
        return 500, "relay not configured"

    target = f"{OVERSEAS_URL}?{query_string}" if query_string else OVERSEAS_URL
    req = urllib.request.Request(target, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.error("Forward failed: %s", e)
        return 502, str(e)


def main_handler(event, context):
    """腾讯云 SCF API 网关触发器入口。"""
    client_ip = _get_client_ip(event)
    logger.info("Received callback from %s", client_ip)

    if ALLOWED_IPS and client_ip not in ALLOWED_IPS:
        logger.warning("Blocked IP: %s", client_ip)
        return {"statusCode": 403, "headers": {"Content-Type": "text/plain"}, "body": "Forbidden"}

    # 腾讯云 API 网关：queryString 在 event["queryString"] 字典中
    query_params = event.get("queryString") or {}
    query_string = urllib.parse.urlencode(query_params)
    logger.info("Query: %s", query_string[:200])

    status, resp_text = _forward_get(query_string)
    logger.info("Forward result: %d %s", status, resp_text[:100])

    return {"statusCode": 200, "headers": {"Content-Type": "text/plain"}, "body": "success"}
