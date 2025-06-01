# notify.py
import requests
import json
import time
from threading import Lock
from scrapy.utils.project import get_project_settings


class RateLimiter:
    def __init__(self, max_tokens, refill_rate):
        """
        Initialize rate limiter
        :param max_tokens: Maximum number of tokens (messages) allowed
        :param refill_rate: Number of tokens to add per second
        """
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.tokens = max_tokens
        self.last_refill_time = time.time()
        self.lock = Lock()

    def acquire(self):
        """
        Try to acquire a token. Returns True if successful, False if rate limit exceeded.
        """
        with self.lock:
            now = time.time()
            time_passed = now - self.last_refill_time
            new_tokens = time_passed * self.refill_rate
            self.tokens = min(self.max_tokens, self.tokens + new_tokens)
            self.last_refill_time = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    def wait_for_token(self):
        """
        Wait until a token becomes available
        """
        while not self.acquire():
            time.sleep(0.1)


# 全局限流器实例
rate_limiter = RateLimiter(max_tokens=20, refill_rate=1/3)


def notify_all(title, content, is_important=False):
    """统一通知入口"""
    wecom_msg = f"【{title}】\n{content}"
    wecom_notify(wecom_msg)
    # if is_important:
    #     email_notify(
    #         subject=f"重要更新：{title}",
    #         body=content
    #     )


def wecom_notify(text):
    """
    企业微信推送
    """
    settings = get_project_settings()
    if not settings.getbool('WECOM_NOTIFY_ENABLED'):
        return

    # 等待令牌
    rate_limiter.wait_for_token()

    headers = {'Content-Type': 'application/json'}
    payload = {
        "msgtype": "text",
        "text": {
            "content": text,
            "mentioned_mobile_list": ["@all"]
        }
    }

    try:
        resp = requests.post(
            settings['WECOM_WEBHOOK'],
            data=json.dumps(payload),
            headers=headers,
            timeout=10
        )
        return resp.json()
    except Exception as e:
        print(f"企业微信通知失败: {str(e)}")


def wecom_nofity_image_text(title, description, image_url, url):
    """
    企业微信图文推送
    """
    settings = get_project_settings()
    if not settings.getbool('WECOM_NOTIFY_ENABLED'):
        return

    # 等待令牌
    rate_limiter.wait_for_token()

    headers = {'Content-Type': 'application/json'}
    payload = {
        "msgtype": "news",
        "news": {
            "articles": [
                {
                    "title": title,
                    "description": description,
                    "url": url,
                    "picurl": image_url
                }
            ]
        }
    }

    try:
        resp = requests.post(
            settings['WECOM_WEBHOOK'],
            data=json.dumps(payload),
            headers=headers,
            timeout=10
        )
        return resp.json()
    except Exception as e:
        print(f"企业微信通知失败: {str(e)}")