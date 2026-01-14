import os
import time
import json
import requests
from bilibili_api import dynamic, Credential, sync
from snscrape.modules.twitter import TwitterUserScraper

# 配置
TARGET_X_USERNAME = os.getenv("TARGET_X_USERNAME")  # 目标X账号（不带@）
LAST_TWEET_ID_FILE = "last_tweet_id.json"

# B站认证
def get_bilibili_cred():
    return Credential(
        sessdata=os.getenv("BILIBILI_SESSDATA"),
        bili_jct=os.getenv("BILIBILI_BILI_JCT"),
        buvid3=os.getenv("BILIBILI_BUVID3")
    )

# 加载最后推文ID
def load_last_tweet_id():
    if os.path.exists(LAST_TWEET_ID_FILE):
        with open(LAST_TWEET_ID_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_id", "")
    return ""

# 保存最后推文ID
def save_last_tweet_id(tweet_id):
    with open(LAST_TWEET_ID_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_id": tweet_id}, f)

# 下载图片
def download_image(url, path):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path
    except Exception as e:
        print(f"图片下载失败: {e}")
        return None

# 发布B站动态
def publish_to_bilibili(text, image_paths):
    cred = get_bilibili_cred()
    try:
        content = {"content": text, "pictures": []}
        for img_path in image_paths[:9]:
            if os.path.exists(img_path):
                pic_info = sync(dynamic.upload_image(img_path, cred))
                content["pictures"].append(pic_info)
        sync(dynamic.publish_dynamic(content, cred))
        print("B站发布成功")
        # 删除临时图片
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)
        return True
    except Exception as e:
        print(f"B站发布失败: {e}")
        return False

# 主逻辑
def main():
    last_id = load_last_tweet_id()
    # 初始化scraper（移除include_retweets参数）
    scraper = TwitterUserScraper(TARGET_X_USERNAME)
    
    # 遍历推文并过滤转推
    new_tweets = []
    for tweet in scraper.get_items():
        # 过滤条件：1. 是新推文（ID≠last_id） 2. 不是转推（retweetedTweet为空）
        if tweet.id == last_id:
            break
        if not tweet.retweetedTweet:  # 只保留原创推文，排除转推
            new_tweets.append(tweet)
    
    # 只处理最新的一条原创新推文
    if new_tweets:
        tweet = new_tweets[0]
        # 整理内容
        tweet_text = tweet.content
        tweet_url = f"https://x.com/{TARGET_X_USERNAME}/status/{tweet.id}"
        publish_text = f"{tweet_text}\n\n来源：{tweet_url}\n（自动同步）"
        
        # 处理图片
        image_paths = []
        if tweet.media:
            for idx, media in enumerate(tweet.media):
                if media.type == "photo":
                    img_path = download_image(media.url, f"temp_{idx}.jpg")
                    if img_path:
                        image_paths.append(img_path)
        
        # 发布到B站
        publish_to_bilibili(publish_text, image_paths)
        # 保存最后推文ID
        save_last_tweet_id(tweet.id)
    else:
        print("无新的原创推文，无需同步")

if __name__ == "__main__":
    main()
