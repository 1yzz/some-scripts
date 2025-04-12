# notify.py
import requests
import json
from scrapy.utils.project import get_project_settings


# notify.py
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