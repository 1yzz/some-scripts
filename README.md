# Some Scripts

## bsp_prize

### How to Start

```shell
cd bsp_prize

python3 -m venv env
source env/bin/activate

pip install -r requirements.txt

# 抓取
scrapy crawl bsp_item_1


#
scrapy crawl bsp_item_all -O build/bsp_item_all.json

# 部署到scrapyd
scrapyd-deploy 
```