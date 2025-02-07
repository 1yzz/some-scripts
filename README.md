# Some Scripts

## bsp_prize

howto

```shell
cd bsp_prize

python3 -m venv env
source env/bin/activate

pip install -r requirements.txt

# 抓取
scrapy crawl bsp_item_1


# 部署到scrapyd
scrapyd-deploy
```