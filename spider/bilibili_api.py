import requests
import time
import random
import pymysql
from datetime import datetime

# ================== 🔴 配置区域 ==================

# 1. B站 Cookie (请确保这里是你最新的 Cookie)
COOKIE = """buvid3=5FE1AD61-24A7-EFF1-ADC1-B601351A64B045266infoc; b_nut=1762067345; _uuid=C10A65D4C-7109E-1018D-B39E-962E5A645310947037infoc; buvid4=5C8A9777-82F4-8E73-D1FB-4562D5C89E2E81922-025101318-YrurpcNiUaxvNzgYzwCyJQ%3D%3D; buvid_fp=71eb915647f3446ab6704685cc0aa13e; rpdid=|(umRY)|JmYl0J'u~Yk|Y~J~u; DedeUserID=288417099; DedeUserID__ckMd5=c6f4cb34e9cb5b5b; theme-tip-show=SHOWED; theme-avatar-tip-show=SHOWED; theme-switch-show=SHOWED; CURRENT_QUALITY=127; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NjM3Mzk2ODIsImlhdCI6MTc2MzQ4MDQyMiwicGx0IjotMX0.zFDPBxxam6zdMQe4ELzrhAYvDbhvqmX0HhiDC2ViZkU; bili_ticket_expires=1763739622; SESSDATA=702fe139%2C1779032482%2Cf346b%2Ab2CjAKa2WIsxDae9veT0e59O9aBJexgkGp675DXcFC5J_Ac7-xVqcL35OjaJBLncMSgGESVkxrQ19KM1FjaW1qbmR2SWJnMXdCcV83LUJQcno3a3FTdFBWMFQxdjdMRHdQbnlucTc1S1lQcWZZV2Y5aU1qcXRfOVBwSUFkbjZwbW5abDZHenlDMzlBIIEC; bili_jct=c6c3fe1e61333978db3a6d650d9f7adf; sid=6t5hrhil; theme_style=dark; bp_t_offset_288417099=1137639001650364416; b_lsid=10A1D93108_19AA5E29422; bmg_af_switch=1; bmg_src_def_domain=i0.hdslb.com; home_feed_column=4; browser_resolution=616-954; CURRENT_FNVAL=4048"""

# 2. 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'db': 'bilibili_math_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 3. ✅ 升级后的搜索映射 (新增了习题、真题等分类)
SEARCH_MAP = {
    # --- 教材同步类 ---
    '宋浩 高等数学': '高数(教材版)',
    '张宇 高等数学': '高数(强化)',
    '汤家凤 高数': '高数(基础)',

    # --- 学科细分类 ---
    '李永乐 线性代数': '线性代数',
    '宋浩 概率论': '概率统计',
    '3Blue1Brown': '数学科普',  # 这种属于扩展视野
    '武忠祥 高数': '高数(强化)',     # 考研三大巨头之一
    '余丙森 概率论': '概率统计',     # 概率论名师
    '姜晓千 高数': '高数(通俗)',     # 适合基础差的
    '周洋鑫 高数': '高数(技巧)',     # 技巧流
    '杨超 高数': '高数(基础)',       # 基础流
    '考研数学 这里的黎明静悄悄': '习题讲解', # 知名UP主
    '王谱 概率论': '概率统计',

    # --- 考试与习题类 (这是学生最关心的！) ---
    '考研数学 真题': '真题实战',
    '接力题典 1800': '刷题特训',
    '考研数学 冲刺': '考前冲刺',
    '专升本 高数': '专升本专区'
}

MAX_PAGES = 5  # 演示用，抓取 5 页

# ==================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': 'https://www.bilibili.com/',
    'Cookie': COOKIE
}


def save_to_mysql(data_list):
    if not data_list: return
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            sql = """
            INSERT INTO videos (
                bvid, title, up_name, pic_url, view_count, danmaku_count, 
                reply_count, favorite_count, coin_count, share_count, 
                duration, pubdate, tags, category, dry_goods_ratio
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                view_count = VALUES(view_count),
                favorite_count = VALUES(favorite_count),
                dry_goods_ratio = VALUES(dry_goods_ratio),
                category = VALUES(category); -- 更新时也更新分类
            """
            values = []
            for item in data_list:
                values.append((
                    item['bvid'], item['title'], item['up_name'], item['pic_url'],
                    item['view_count'], item['danmaku_count'], item['reply_count'],
                    item['favorite_count'], item['coin_count'], item['share_count'],
                    item['duration'], item['pubdate'], item['tags'],
                    item['category'], item['dry_goods_ratio']
                ))
            cursor.executemany(sql, values)
            connection.commit()
            print(f"   ✅ 入库/更新 {len(data_list)} 条 - 分类: {data_list[0]['category']}")
    except Exception as e:
        print(f"   ❌ 数据库错误: {e}")
    finally:
        connection.close()


def parse_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def parse_duration(duration_str):
    try:
        if isinstance(duration_str, int):
            return duration_str
        if isinstance(duration_str, str) and duration_str.isdigit():
            return int(duration_str)

        parts = duration_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except:
        return 0


def run_spider():
    print("🚀 爬虫启动...")
    for keyword, category in SEARCH_MAP.items():
        print(f"\n🔍 正在抓取: {keyword} -> [{category}]")
        for page in range(1, MAX_PAGES + 1):
            try:
                url = 'https://api.bilibili.com/x/web-interface/search/type'
                params = {'search_type': 'video', 'keyword': keyword, 'page': page, 'order': 'click'}
                resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
                res_json = resp.json()

                if res_json['code'] != 0:
                    print(f"   ⚠️ 接口报错: {res_json.get('message')}")
                    break

                items = res_json['data']['result']
                if not items: break

                batch_data = []
                for item in items:
                    view = item.get('play', 0)
                    fav = item.get('favorites', 0)
                    ratio = round((fav / view * 1000), 2) if view > 0 else 0

                    video_data = {
                        'bvid': item['bvid'],
                        'title': item['title'].replace('<em class="keyword">', '').replace('</em>', ''),
                        'up_name': item['author'],
                        'pic_url': item.get('pic', ''),
                        'view_count': view,
                        'danmaku_count': item.get('video_review', 0),
                        'reply_count': item.get('review', 0),
                        'favorite_count': fav,
                        'coin_count': 0, 'share_count': 0,
                        'duration': parse_duration(item.get('duration', '0')),
                        'pubdate': parse_time(item.get('pubdate', time.time())),
                        'tags': keyword,
                        'category': category,
                        'dry_goods_ratio': ratio
                    }
                    batch_data.append(video_data)
                save_to_mysql(batch_data)
                time.sleep(random.uniform(2, 3))
            except Exception as e:
                print(f"   ❌ 异常: {e}")
    print("\n🎉 全部完成！")


if __name__ == '__main__':
    run_spider()