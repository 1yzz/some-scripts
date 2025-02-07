import requests
proxies = {
  "https": "scraperapi.screenshot=true:ae49c416b12727ee24b05c1412d62596@proxy-server.scraperapi.com:8001"
}
r = requests.get('https://bsp-prize.jp/files/%E5%85%B1%E6%9C%89%E3%83%95%E3%82%A9%E3%83%AB%E3%83%80/item/-2021_onepiece_wcf/0039848.jpg', proxies=proxies, verify=False)
print(r.text)
