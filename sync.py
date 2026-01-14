import os
import asyncio
import requests
from bilibili_api import dynamic, Credential, sync
import twscrape
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置
TARGET_X_USERNAME = os.getenv("TARGET_X_USERNAME")
X_USER = os.getenv("X_USER")        # 你的X账号（手机号/用户名）
X_PASS = os.getenv("X_PASS")        # 你的X密码
X_EMAIL = os.getenv("X_EMAIL")      # X绑定的邮箱
X_EMAIL_PASS = os.getenv("X_EMAIL_PASS")  # 邮箱密码/授权码/占位符

# B站认证
def get_bilibili_cred():
    return Credential(
        sessdata=os.getenv("BILIBILI_SESSDATA"),
        bili_jct=os.getenv("BILIBILI_BILI_JCT"),
        buvid3=os.getenv("BILIBILI_BUVID3")
    )

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
        # 清理图片
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)
        return True
    except Exception as e:
        print(f"B站发布失败: {e}")
        return False

# 异步获取X最新1条原创推文
async def get_latest_x_tweet():
    # 初始化twscrape
    api = twscrape.API()
    await api.pool.add_account(X_USER, X_PASS, X_EMAIL, X_EMAIL_PASS)
    await api.pool.login_all()

    # 只获取最新的1条原创推文（limit=1）
    async for tweet in api.user_tweets(TARGET_X_USERNAME, limit=1):
        # 排除转推
        if not hasattr(tweet, 'retweeted_status'):
            return tweet
    return None

# 主逻辑
def main():
    # 获取最新1条原创推文
    tweet = asyncio.run(get_latest_x_tweet())
    
    if not tweet:
        print("无新的原创推文，无需同步")
        return

    # 整理推文内容
    tweet_text = tweet.rawContent if hasattr(tweet, 'rawContent') else tweet.text
    tweet_url = f"https://x.com/{TARGET_X_USERNAME}/status/{tweet.id_str}"
    publish_text = f"{tweet_text}\n\n来源：{tweet_url}\n（自动同步）"

    # 下载图片（如有）
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

if __name__ == "__main__":
    main()
