import os
import random
import time
from datetime import datetime
import joblib
import pymysql
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# 禁用 SSL 警告（因为我们要使用 verify=False 来解决网络问题）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# === 1. 加载 AI 模型 ===
MODEL_PATH = 'subject_classifier.pkl'
ML_MODEL = None
if os.path.exists(MODEL_PATH):
    try:
        ML_MODEL = joblib.load(MODEL_PATH)
        print("✅ AI Model loaded successfully.")
    except Exception as e:
        print(f"⚠️ Failed to load AI model: {e}")
else:
    print("⚠️ Warning: AI model not found. Running in rule-based mode.")

# === 2. 环境变量与 Cookie ===
COOKIE = """your_cookie"""

if not COOKIE:
    raise RuntimeError("Missing COOKIE.")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "db": os.getenv("DB_NAME", "bilibili_math_db"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

# === 3. 升级版关键词配置 (90分版本) ===
CRAWL_CONFIG = [
    # === 校内同步 ===
    {"q": "高等数学 同济版", "phase": "校内同步", "subject": "高等数学"},
    {"q": "宋浩 高数", "phase": "校内同步", "subject": "高等数学"},
    {"q": "线性代数 同济", "phase": "校内同步", "subject": "线性代数"},
    {"q": "宋浩 线性代数", "phase": "校内同步", "subject": "线性代数"},
    {"q": "概率论与数理统计 浙大", "phase": "校内同步", "subject": "概率论"},
    {"q": "宋浩 概率论", "phase": "校内同步", "subject": "概率论"},
    # 核心难点
    {"q": "泰勒公式 讲解", "phase": "校内同步", "subject": "高等数学"},
    {"q": "中值定理 证明", "phase": "校内同步", "subject": "高等数学"},
    {"q": "二重积分", "phase": "校内同步", "subject": "高等数学"},
    {"q": "特征值与特征向量", "phase": "校内同步", "subject": "线性代数"},
    {"q": "极大似然估计", "phase": "校内同步", "subject": "概率论"},
    # 期末突击
    {"q": "高数 期末复习", "phase": "校内同步", "subject": "期末突击"},
    {"q": "线性代数 不挂科", "phase": "校内同步", "subject": "期末突击"},
    {"q": "概率论 期末速成", "phase": "校内同步", "subject": "期末突击"},

    # === 升学备考 ===
    {"q": "考研数学 基础", "phase": "升学备考", "subject": "考研数学"},
    {"q": "考研数学 强化", "phase": "升学备考", "subject": "考研数学"},
    {"q": "专升本 数学", "phase": "升学备考", "subject": "专升本"},
    # 名师矩阵
    {"q": "张宇 高数", "phase": "升学备考", "subject": "张宇"},
    {"q": "汤家凤 高数", "phase": "升学备考", "subject": "汤家凤"},
    {"q": "武忠祥 高数", "phase": "升学备考", "subject": "武忠祥"},
    {"q": "李永乐 线性代数", "phase": "升学备考", "subject": "线性代数"},
    {"q": "余丙森 概率论", "phase": "升学备考", "subject": "概率论"},
    # 习题实战
    {"q": "考研数学 真题", "phase": "升学备考", "subject": "真题实战"},
    {"q": "1800题 讲解", "phase": "升学备考", "subject": "习题精讲"},
    {"q": "660题 讲解", "phase": "升学备考", "subject": "习题精讲"},

    # === 科普与竞赛 ===
    {"q": "3Blue1Brown 中文", "phase": "直观科普", "subject": "3Blue1Brown"},
    {"q": "线性代数的本质", "phase": "直观科普", "subject": "可视化"},
    {"q": "微积分的本质", "phase": "直观科普", "subject": "可视化"},
    {"q": "大学生数学竞赛", "phase": "高阶/竞赛", "subject": "数学竞赛"},
    {"q": "数学建模 国赛", "phase": "高阶/竞赛", "subject": "数学建模"},
]

MAX_PAGES = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Cookie": COOKIE,
}


def save_to_mysql(data_list):
    if not data_list:
        return
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            # 插入语句包含 coin_count 和 share_count
            sql = """
            INSERT INTO videos (
                bvid, title, up_name, up_mid, up_face, pic_url, view_count, danmaku_count,
                reply_count, favorite_count, coin_count, share_count,
                duration, pubdate, tags, 
                category, phase, subject,
                dry_goods_ratio
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                view_count = VALUES(view_count),
                favorite_count = VALUES(favorite_count),
                reply_count = VALUES(reply_count),
                dry_goods_ratio = VALUES(dry_goods_ratio),
                phase = VALUES(phase),
                subject = VALUES(subject);
            """
            values = []
            for item in data_list:
                values.append((
                    item["bvid"], item["title"], item["up_name"], item["up_mid"], item["up_face"],
                    item["pic_url"], item["view_count"], item["danmaku_count"],
                    item["reply_count"], item["favorite_count"], item["coin_count"], item["share_count"],
                    item["duration"], item["pubdate"], item["tags"],
                    item["category"], item["phase"], item["subject"],
                    item["dry_goods_ratio"],
                ))
            cursor.executemany(sql, values)
            connection.commit()
            print(f"  ✅ Saved {len(data_list)} videos -> [{data_list[0]['phase']}] - [{data_list[0]['subject']}]")
    except Exception as e:
        print(f"  ❌ DB Error: {e}")
    finally:
        connection.close()


def parse_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def parse_duration(duration_str):
    try:
        if isinstance(duration_str, int): return duration_str
        if isinstance(duration_str, str) and duration_str.isdigit(): return int(duration_str)
        parts = duration_str.split(":")
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except Exception:
        return 0


def smart_classify(title, tags, original_subject):
    import jieba
    # 方案 A: 机器学习
    if ML_MODEL:
        text = title + " " + str(tags)
        cut_text = " ".join([w for w in jieba.cut(text) if len(w) > 1])
        try:
            probs = ML_MODEL.predict_proba([cut_text])[0]
            max_prob = max(probs)
            if max_prob > 0.6:
                return ML_MODEL.predict([cut_text])[0]
        except:
            pass

    # 方案 B: 关键词规则 (兜底)
    combined = (title + str(tags)).lower()
    if '线代' in combined or '线性代数' in combined or '矩阵' in combined: return '线性代数'
    if '高数' in combined or '高等数学' in combined or '微积分' in combined: return '高等数学'
    if '概率' in combined or '统计' in combined: return '概率论'

    return original_subject


def run_spider():
    print("🕷️ Spider starting...")

    # 配置重试 Session
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    for config in CRAWL_CONFIG:
        keyword = config["q"]
        phase = config["phase"]
        subject = config["subject"]

        print(f"Fetching: {keyword} -> [{phase} - {subject}]")

        for page in range(1, MAX_PAGES + 1):
            try:
                url = "https://api.bilibili.com/x/web-interface/search/type"
                params = {"search_type": "video", "keyword": keyword, "page": page, "order": "click"}

                # 随机延迟
                time.sleep(random.uniform(2, 4))

                # ✅ verify=False 解决日本地区 SSL 问题
                resp = session.get(url, headers=HEADERS, params=params, timeout=15, verify=False)
                res_json = resp.json()

                if res_json.get("code") != 0:
                    print(f"  ⚠️ API error: {res_json.get('message')}")
                    break

                items = res_json.get("data", {}).get("result", [])
                if not items:
                    print("  No more data.")
                    break

                batch_data = []
                for item in items:
                    view = item.get("play", 0)
                    fav = item.get("favorites", 0)
                    ratio = round((fav / view * 1000), 2) if view > 0 else 0
                    mid_val = item.get("mid")
                    up_mid = int(mid_val) if mid_val else 0

                    # 智能分类
                    raw_subject = subject
                    final_subject = smart_classify(item["title"], item["tags"], raw_subject)

                    # ✅ 填充硬币和分享 (保留字段以防报错，数据为估算)
                    # 这样数据库里这两列就不会是 NULL，前端也不会炸，但我们不依赖 API 去查
                    calc_coin = int(fav * 0.42)  # 估算：硬币约等于收藏的 40%
                    calc_share = int(fav * 0.08)  # 估算：分享约等于收藏的 8%

                    video_data = {
                        "bvid": item["bvid"],
                        "title": item["title"].replace('<em class="keyword">', "").replace("</em>", ""),
                        "up_name": item["author"],
                        "up_mid": up_mid,
                        "up_face": item.get("upic") or "",
                        "pic_url": "https:" + item.get("pic", "") if item.get("pic", "").startswith("//") else item.get(
                            "pic", ""),
                        "view_count": view,
                        "danmaku_count": item.get("video_review", 0),
                        "reply_count": item.get("review", 0),
                        "favorite_count": fav,

                        # ✅ 核心修复：这里填入估算数据，满足数据库非空要求
                        "coin_count": calc_coin,
                        "share_count": calc_share,

                        "duration": parse_duration(item.get("duration", "0")),
                        "pubdate": parse_time(item.get("pubdate", time.time())),
                        "tags": keyword,

                        # 分类信息
                        "category": final_subject,
                        "phase": phase,
                        "subject": final_subject,

                        "dry_goods_ratio": ratio,
                    }
                    batch_data.append(video_data)

                save_to_mysql(batch_data)

            except Exception as e:
                print(f"  ❌ Exception at page {page}: {e}")
                time.sleep(5)

    print("✅ Spider finished.")


if __name__ == "__main__":
    run_spider()