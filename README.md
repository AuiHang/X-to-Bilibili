# X(Twitter) 推文自动同步到B站动态
一个基于 GitHub Actions + twscrape 实现的免费工具，可自动抓取指定 X 账号的原创推文，并同步到你的 B 站动态，无需本地部署，24 小时自动运行。

## 功能说明
- ✅ 自动抓取指定 X 账号的**原创推文**（排除转推/回复）
- ✅ 同步推文文字内容 + 图片到 B 站动态（自动标注来源链接）
- ✅ 基于 GitHub Actions 境外服务器运行，无需翻墙/本地环境
- ✅ 定时检查（默认每 30 分钟一次），无需人工值守

> ⚠️ 注意：X 平台对自动化登录/爬取风控严格，免费方案可能存在临时登录失败，建议作为半自动化补充方案使用。

## 环境准备
1. **GitHub 账号**：用于创建仓库和运行 Actions 脚本（[免费注册](https://github.com/)）
2. **X 账号**：
   - 绑定邮箱（需能查看，用于登录验证）
   - 关闭「两步验证」（X → 设置 → 安全 → 两步验证 → 关闭）
   - 确保能正常登录，无风控限制
3. **B站账号**：提取以下 3 个 Cookie（用于发布动态）：
   - `SESSDATA`
   - `bili_jct`
   - `buvid3`
   提取方法：打开 B 站网页版 → 按 F12 打开开发者工具 → 切换到「Network」标签 → 点击任意请求 → 在「Request Headers」中找到「Cookie」→ 从中提取对应字段。

## 部署步骤
### 步骤 1：创建 GitHub 仓库
1. 打开 [GitHub](https://github.com/)，登录后点击右上角「+」→「New repository」
2. 仓库名：`X-to-Bilibili`（任意名称均可）
3. 勾选「Add a README file」，点击「Create repository」

### 步骤 2：添加仓库 Secret（敏感配置）
1. 进入仓库 → 点击顶部「Settings」→ 左侧「Secrets and variables」→「Actions」→ 右上角「New repository secret」
2. 依次添加以下 Secret（名称严格按要求填写，值替换为自己的信息）：

| Secret 名称          | 填写说明                                                                 |
|----------------------|--------------------------------------------------------------------------|
| `TARGET_X_USERNAME`  | 要同步的 X 账号（不带 @，示例：`elonmusk`）                               |
| `X_USER`             | 你的 X 登录账号（手机号/用户名/邮箱，示例：`13800138000` 或 `xxx@qq.com`）|
| `X_PASS`             | 你的 X 登录密码                                                          |
| `X_EMAIL`            | 你的 X 绑定邮箱（示例：`123456@qq.com`）                                 |
| `X_EMAIL_PASS`       | 邮箱授权码/占位符（QQ 邮箱填 IMAP 授权码，无则填英文半角双引号 `""`）     |
| `BILIBILI_SESSDATA`  | 你的 B 站 SESSDATA Cookie（示例：`abc123xyz`）                            |
| `BILIBILI_BILI_JCT`  | 你的 B 站 bili_jct Cookie（示例：`def456uvw`）                            |
| `BILIBILI_BUVID3`    | 你的 B 站 buvid3 Cookie（示例：`ghi789rst`）                              |

### 步骤 3：上传脚本文件
进入仓库 → 点击顶部「Add file」→「Create new file」，分别创建以下 2 个文件（文件名严格一致）：

#### 文件 1：`sync.py`（核心同步脚本）
```python
import os
import asyncio
import requests
from bilibili_api import dynamic, Credential, sync
import twscrape
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置（从 GitHub Secret 读取）
TARGET_X_USERNAME = os.getenv("TARGET_X_USERNAME")
X_USER = os.getenv("X_USER")
X_PASS = os.getenv("X_PASS")
X_EMAIL = os.getenv("X_EMAIL")
X_EMAIL_PASS = os.getenv("X_EMAIL_PASS")

# B 站认证
def get_bilibili_cred():
    return Credential(
        sessdata=os.getenv("BILIBILI_SESSDATA"),
        bili_jct=os.getenv("BILIBILI_BILI_JCT"),
        buvid3=os.getenv("BILIBILI_BUVID3")
    )

# 下载推文图片
def download_image(url, path):
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, verify=False)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path
    except Exception as e:
        print(f"图片下载失败: {e}")
        return None

# 发布到 B 站动态
def publish_to_bilibili(text, image_paths):
    cred = get_bilibili_cred()
    try:
        content = {"content": text, "pictures": []}
        for img_path in image_paths[:9]:
            if os.path.exists(img_path):
                pic_info = sync(dynamic.upload_image(img_path, cred))
                content["pictures"].append(pic_info)
        sync(dynamic.publish_dynamic(content, cred))
        print("B站动态发布成功 ✅")
        # 清理临时图片
        for p in image_paths:
            if os.path.exists(p):
                os.remove(p)
        return True
    except Exception as e:
        print(f"B站发布失败 ❌: {e}")
        return False

# 异步获取 X 最新原创推文
async def get_latest_x_tweet():
    # 初始化 twscrape
    api = twscrape.API()
    await api.pool.add_account(X_USER, X_PASS, X_EMAIL, X_EMAIL_PASS)
    await api.pool.login_all()

    # 只获取最新 1 条原创推文（排除转推）
    async for tweet in api.user_tweets(TARGET_X_USERNAME, limit=1):
        if not hasattr(tweet, 'retweeted_status'):
            return tweet
    return None

# 主逻辑
def main():
    # 获取最新推文
    tweet = asyncio.run(get_latest_x_tweet())
    
    if not tweet:
        print("无新的原创推文，无需同步 📭")
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

    # 发布到 B 站
    publish_to_bilibili(publish_text, image_paths)

if __name__ == "__main__":
    main()
```
#### 文件 2：.github/workflows/sync.yml（定时运行配置）
```
name: X to Bilibili Sync
on:
  schedule:
    - cron: "*/30 * * * *"  # 每 30 分钟检查一次（降低风控概率）
  workflow_dispatch:        # 允许手动触发

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: 设置 Python 环境
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - name: 安装依赖
        run: |
          python -m pip install --upgrade pip
          pip install twscrape bilibili-api-python requests urllib3
      - name: 运行同步脚本
        env:
          TARGET_X_USERNAME: ${{ secrets.TARGET_X_USERNAME }}
          X_USER: ${{ secrets.X_USER }}
          X_PASS: ${{ secrets.X_PASS }}
          X_EMAIL: ${{ secrets.X_EMAIL }}
          X_EMAIL_PASS: ${{ secrets.X_EMAIL_PASS }}
          BILIBILI_SESSDATA: ${{ secrets.BILIBILI_SESSDATA }}
          BILIBILI_BILI_JCT: ${{ secrets.BILIBILI_BILI_JCT }}
          BILIBILI_BUVID3: ${{ secrets.BILIBILI_BUVID3 }}
        run: python sync.py
```
### 步骤 4：测试运行    
1.每个文件创建后，点击页面底部「Commit changes」保存（无需填写额外信息）；
2.所有文件提交完成后，进入仓库 → 点击顶部「Actions」→ 左侧「X to Bilibili Sync」→ 点击右侧「Run workflow」→ 再次点击「Run workflow」手动触发运行；
3.点击最新的运行记录 → 点击「sync」→ 点击「Run sync script」查看详细日志：
⚪显示「无新的原创推文，无需同步 📭」→ 脚本运行正常；
⚪显示「B 站动态发布成功 ✅」→ 同步流程完全跑通；
⚪显示登录失败相关报错 → 参考「常见问题」排查。

## 使用说明
### 查看运行日志
仓库 → 顶部「Actions」→ 左侧「X to Bilibili Sync」→ 选择最新的运行记录 → 点击「sync」→ 点击「Run sync script」即可查看完整运行日志。

### 修改同步频率
编辑 `.github/workflows/sync.yml` 文件中的 `cron` 字段（按自己需求调整）：
- `*/10 * * * *`：每 10 分钟一次（风控概率较高）；
- `*/30 * * * *`：每 30 分钟一次（推荐，平衡效率与风控）；
- `0 * * * *`：每小时一次（最稳定，风控概率最低）。

### 停止/重启同步
- 停止：仓库 → 顶部「Settings」→ 左侧「Actions」→「General」→ 勾选「Disable actions」→ 点击「Save changes」；
- 重启：按上述路径重新勾选「Enable local and third party Actions for this repository」→ 点击「Save changes」。

## 常见问题
### Q1：登录失败（日志显示「Failed to login: 400」）
- 原因：X 平台风控识别到自动化登录环境，临时限制登录；
- 解决步骤：
  1. 确认 X 账号已关闭「两步验证」；
  2. 用手机流量手动登录 X 网页版/APP（确保账号正常）；
  3. 暂停同步 12-24 小时（让风控解除）；
  4. 将同步频率改为每 30 分钟/每小时一次，降低触发风控的概率。

### Q2：B站发布失败（日志显示「B站发布失败 ❌」）
- 原因：B站 Cookie 失效（SESSDATA 有效期约 1 个月）；
- 解决：重新按「环境准备」步骤提取 B 站的 `SESSDATA`、`bili_jct`、`buvid3`，并更新仓库 Secret 中的对应字段。

### Q3：GitHub Actions 权限错误（日志显示「403 Forbidden」）
- 原因：脚本尝试提交文件到仓库，但 `github-actions[bot]` 无推送权限；
- 解决：本脚本已删除自动提交步骤，无需额外操作，直接忽略该报错即可（不影响核心同步功能）。

### Q4：X 有新推文，但日志显示「无新的原创推文」
- 原因：X 登录失败，脚本未成功获取到推文，并非真的无新内容；
- 解决：参考 Q1 解决 X 登录问题，重新手动触发脚本重试。

## 免责声明
1. 本工具仅用于个人学习和非商业用途，请勿用于批量爬取、违规同步或其他违反平台规则的行为；
2. 同步内容需遵守 X（Twitter）和 B 站的用户协议，若因侵权、违规导致的账号风险，由使用者自行承担；
3. X 平台政策变动（如加强反爬、关闭免费接口）可能导致工具失效，作者不保证长期可用，仅提供技术参考。
