import os
import json
import asyncio
import requests
from bilibili_api import dynamic, Credential, sync
import twscrape  # 替换snscrape为twscrape
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置
TARGET_X_USERNAME = os.getenv("TARGET_X_USERNAME")
X_USER = os.getenv("X_USER")  # 你的X账号（手机号/邮箱/用户名）
X_PASS = os.getenv("X_PASS")  # 你的X账号密码
LAST_TWEET_ID_FILE = "last_tweet_id.json"

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
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, verify=False)
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

# 异步获取X推文
async def get_x_tweets():
    last_id = load_last_tweet_id()
    # 初始化twscrape
    api = twscrape.API()
    # 添加X账号（模拟登录）
    await api.pool.add_account(X_USER, X_PASS)
    await api.pool.login_all()

    # 获取目标账号的原创推文（排除转推）
    tweets = []
    async for tweet in api.user_tweets(TARGET_X_USERNAME, limit=10):
        # 过滤条件：1. 新推文 2. 原创（无retweetedTweet）
        if tweet.id_str == last_id:
            break
        if not hasattr(tweet, 'retweeted_status'):  # 排除转推
            tweets.append(tweet)
    return tweets

# 主逻辑
def main():
    last_id = load_last_tweet_id()
    # 运行异步函数
    tweets = asyncio.run(get_x_tweets())
    
    if not tweets:
        print("无新原创推文")
        return

    # 处理最新一条新推文
    tweet = tweets[0]
    # 整理内容
    tweet_text = tweet.rawContent if hasattr(tweet, 'rawContent') else tweet.text
    tweet_url = f"https://x.com/{TARGET_X_USERNAME}/status/{tweet.id_str}"
    publish_text = f"{tweet_text}\n\n来源：{tweet_url}\n（自动同步）"

    # 下载图片
    image_paths = []
    if hasattr(tweet, 'media') and tweet.media:
        for idx, media in enumerate(tweet.media):
            if media.type == "photo":
                img_url = media.fullUrl
                img_path = download_image(img_url, f"temp_{idx}.jpg")
                if img_path:
                    image_paths.append(img_path)

    # 发布到B站
    publish_to_bilibili(publish_text, image_paths)
    save_last_tweet_id(tweet.id_str)

if __name__ == "__main__":
    main()
