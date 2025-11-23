# Bilibili 数学课代表
面向大学生的数学学习聚合系统，汇集 B 站热门课程与刷题视频，提供数据可视化、个性化推荐和学习资产管理，帮助快速找到合适的老师、题库与复习路径。

## 功能亮点
- 数据仪表盘：总视频量、播放量、收藏率榜单、学科分布玫瑰图、时长-干货度散点。
- 视频检索筛选：按收藏率/播放量/发布时间排序，标题/标签/UP 主关键字搜索，支持学科分类过滤与分页。
- UP 主对比：雷达图对比传播/质量/热度/硬核度/活跃度，并附带真实词云。
- 场景推荐：冲刺基础/刷题/猜你喜欢四类短列表推荐。
- 个人中心：收藏、待看、历史记录、头像上传与个人简介维护。
- 数据采集脚本：`spider/bilibili_api.py` 按关键词抓取 B 站数据写入 MySQL，可配置分类映射与翻页上限。

## 目录速览
- `app.py`：路由、API 与业务逻辑（仪表盘、搜索、对比、推荐、用户中心）。
- `models.py`：`videos`、`users`、`user_actions` 的 SQLAlchemy 模型。
- `config.py`：数据库与 SecretKey 配置（支持环境变量覆盖）。
- `spider/bilibili_api.py`：B 站搜索采集脚本，含分类映射与翻页配置。
- `templates/`、`static/`：前端模板与静态资源（头像位于 `static/avatars`）。
- `force_fix.py`：从 npm 镜像下载 ECharts/WordCloud 离线包到 `static/js`。
- `requirements.txt`：Python 依赖清单（安装入口见下）。

## 快速开始
1) 环境：Python 3.10+，MySQL 5.7/8.0；创建数据库（默认 `bilibili_math_db`）并确保有写权限。  
2) 安装依赖：
```bash
pip install -r requirements.txt
```
3) 配置（环境变量优先于文件配置）：
- `DATABASE_URL` / `DB_URL` 如 `mysql+pymysql://user:pwd@localhost:3306/bilibili_math_db`
- `SECRET_KEY` / `FLASK_SECRET_KEY`
- 爬虫：`DB_HOST`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`、`DB_PORT`、`BILI_COOKIE`（请用环境变量保存真实 Cookie，不要写入仓库）
4) 初始化数据库：`flask --app app run` 成功连接时会自动 `create_all()`；生产环境建议改用迁移工具。  
5) 拉取示例数据（可选）：`python spider/bilibili_api.py`  
6) 启动应用：
```bash
flask --app app run --debug
```
访问 `http://127.0.0.1:5000/`，在注册页创建账号后登录体验。  
7) 训练分类模型（可选）：`python train_model.py`，依赖数据库中的 `videos` 标注数据。  
8) 运行测试（如添加后）：`pytest`

## 数据库表结构
- 默认库：`bilibili_math_db`（可用 `DATABASE_URL` / `DB_URL` 覆盖），推荐字符集 `utf8mb4`。
- MySQL 建表语句（与 `models.py` 中的 SQLAlchemy 模型保持一致，可直接执行）：

```sql
-- 采集到的课程/题解视频
CREATE TABLE IF NOT EXISTS `videos` (
  `bvid` varchar(20) NOT NULL,
  `title` varchar(255),
  `up_name` varchar(100),
  `up_mid` bigint,
  `up_face` varchar(500),
  `pic_url` varchar(500),
  `view_count` int,
  `danmaku_count` int,
  `reply_count` int,
  `favorite_count` int,
  `coin_count` int,
  `share_count` int,
  `duration` int,
  `pubdate` datetime,
  `tags` varchar(500),
  `category` varchar(50),
  `phase` varchar(50),
  `subject` varchar(50),
  `dry_goods_ratio` float,
  PRIMARY KEY (`bvid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 登录用户信息
CREATE TABLE IF NOT EXISTS `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50),
  `password` varchar(255),
  `description` varchar(255),
  `avatar` varchar(200),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 用户行为（收藏/待看/历史）
CREATE TABLE IF NOT EXISTS `user_actions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int,
  `bvid` varchar(20),
  `action_type` varchar(20),
  `status` int DEFAULT 0,
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

## 页面效果图
- 仪表盘（数据总览、玫瑰图、散点）：`docs/screenshots/仪表盘（数据总览、玫瑰图、散点）.png`
- 视频检索/筛选页（排序/分页/分类）：`docs/screenshots/视频检索筛选页（排序分页分类）.png`
- UP 主对比页（雷达图 + 词云）：`docs/screenshots/UP 主对比页（雷达图 + 词云）.png`
- 场景推荐页（冲刺/刷题/猜你喜欢）：`docs/screenshots/场景推荐页（冲刺刷题猜你喜欢）.png`
- 个人中心（收藏/待看/历史/头像上传）：`docs/screenshots/个人中心（收藏待看历史头像上传）.png`

![仪表盘](docs/screenshots/仪表盘（数据总览、玫瑰图、散点）.png)
![视频检索/筛选页](docs/screenshots/视频检索筛选页（排序分页分类）.png)
![UP 主对比页](docs/screenshots/UP 主对比页（雷达图 + 词云）.png)
![场景推荐页](docs/screenshots/场景推荐页（冲刺刷题猜你喜欢）.png)
![个人中心](docs/screenshots/个人中心（收藏待看历史头像上传）.png)

## 依赖说明
- 安装入口：`pip install -r requirements.txt`
- 关键运行依赖：Flask、Flask-Login、Flask-SQLAlchemy、SQLAlchemy、PyMySQL、requests、jieba
- 开发/测试：pytest

## 开发提示
- 避免提交真实数据库凭据、SECRET_KEY 与 B 站 Cookie，统一用环境变量。
- 若 CDN 访问受限，可运行 `python force_fix.py` 重新下载 ECharts/WordCloud 静态文件。
- 收藏/待看/历史、个人信息更新等接口均在 `app.py`（`/api/action`、`/api/log_history`、`/api/user_profile` 等），便于按需扩展。
