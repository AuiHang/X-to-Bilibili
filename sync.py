import os
import json
import requests
from bilibili_api import dynamic, Credential, sync
from snscrape.modules.twitter import TwitterUserScraper
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # 忽略SSL警告

# 配置
TARGET_X_USERNAME = os.getenv("TARGET_X_USERNAME")
LAST_TWEET_ID_FILE = "last_tweet_id.json"
X_COOKIE = os.getenv("X_COOKIE")  # 你的X账号Cookie


# B站认证
def get_bilibili_cred():
    return Credential(
        sessdata=os.getenv("BILIBILI_SESSDATA"),
        bili_jct=os.getenv("BILIBILI_BILI_JCT"),
        buvid3=os.getenv("BILIBILI_BUVID3")
    )


# 加载/保存最后推文ID
def load_last_tweet_id():
    if os.path.exists(LAST_TWEET_ID_FILE):
        with open(LAST_TWEET_ID_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_id", "")
    return ""

def save_last_tweet_id(tweet_id):
    with open(LAST_TWEET_ID_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_id": tweet_id}, f)


# 下载图片
def download_image(url, path):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Cookie": X_COOKIE}
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
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
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)
        return True
    except Exception as e:
        print(f"B站发布失败: {e}")
        return False


# 主逻辑（带Cookie模拟登录）
def main():
    last_id = load_last_tweet_id()
    # 初始化scraper并添加X Cookie
    scraper = TwitterUserScraper(TARGET_X_USERNAME)
    scraper._session.headers.update({
        "Cookie": X_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    # 遍历推文并过滤转推
    new_tweets = []
    try:
        for tweet in scraper.get_items():
            if tweet.id == last_id:
                break
            if not tweet.retweetedTweet:  # 只同步原创推文
                new_tweets.append(tweet)
    except Exception as e:
        print(f"获取推文失败: {e}")
        return

    # 处理最新一条新推文
    if new_tweets:
        tweet = new_tweets[0]
        # 整理内容
        publish_text = f"{tweet.content}\n\n来源：https://x.com/{TARGET_X_USERNAME}/status/{tweet.id}\n（自动同步）"
        # 下载图片
        image_paths = []
        if tweet.media:
            for idx, media in enumerate(tweet.media):
                if media.type == "photo":
                    img_path = download_image(media.url, f"temp_{idx}.jpg")
                    if img_path:
                        image_paths.append(img_path)
        # 发布到B站
        publish_to_bilibili(publish_text, image_paths)
        save_last_tweet_id(tweet.id)
    else:
        print("无新原创推文")


if __name__ == "__main__":
    main()
