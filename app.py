"""Flask 入口：处理页面路由、API 接口、用户登录与推荐逻辑。"""

import os
import time
import jieba
import math
from collections import Counter
import re
from io import BytesIO
from PIL import Image
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from config import Config
from models import db, Video, User, UserAction
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config.from_object(Config)

# ---- 全局配置与安全限制 ----
UPLOAD_FOLDER = 'static/avatars'
ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 MB per avatar
PASSWORD_HASH_METHOD = "pbkdf2:sha256:260000"
PASSWORD_SALT_LENGTH = 8  # keep hash length within DB column limits
SUPPORTED_ACTIONS = {'fav', 'todo', 'history'}
HISTORY_LIMIT = 200  # 返回给前端的学习足迹条数上限，避免过大响应

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

# Ensure core tables exist when running via `flask run` (tolerate missing DB in dev)
try:
    with app.app_context():
        db.create_all()
except Exception as exc:
    app.logger.warning("Skipping db.create_all during startup: %s", exc)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login 回调：根据 user_id 取出用户对象。"""
    return db.session.get(User, int(user_id))


def is_hashed_password(value: str) -> bool:
    """简单校验字符串是否看起来是 Werkzeug 生成的哈希（含多段 $）。"""
    return isinstance(value, str) and value.count("$") >= 2


def hash_password(password: str) -> str:
    """生成密码哈希；统一算法和盐长度，避免超出字段长度。"""
    return generate_password_hash(password, method=PASSWORD_HASH_METHOD, salt_length=PASSWORD_SALT_LENGTH)


def verify_password(stored: str, candidate: str) -> bool:
    """安全校验密码，遇到坏数据返回 False 而不是抛异常。"""
    if not stored or not candidate or not is_hashed_password(stored):
        return False
    try:
        return check_password_hash(stored, candidate)
    except ValueError:
        return False


def username_exists(username: str, exclude_user_id: int | None = None) -> bool:
    """用户名查重，支持排除当前用户（更新资料时使用）。"""
    if not username:
        return False
    query = User.query.filter_by(username=username)
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    return db.session.query(query.exists()).scalar()


def allowed_avatar(filename: str) -> bool:
    """文件名后缀白名单校验。"""
    return bool(filename) and '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


def get_action_record(user_id: int, bvid: str, action_type: str):
    """获取某个用户对某个视频的指定动作记录。"""
    return UserAction.query.filter_by(user_id=user_id, bvid=bvid, action_type=action_type).first()


def ensure_action_allowed(action_type: str) -> bool:
    """限制可写入的动作类型，避免乱写表。"""
    return action_type in SUPPORTED_ACTIONS


def create_action(user_id: int, bvid: str, action_type: str) -> bool:
    """创建收藏/待看/历史记录；去重后写库。"""
    if not ensure_action_allowed(action_type) or not bvid:
        return False
    if get_action_record(user_id, bvid, action_type):
        return False
    db.session.add(UserAction(user_id=user_id, bvid=bvid, action_type=action_type))
    db.session.commit()
    return True


def delete_action(user_id: int, bvid: str, action_type: str) -> bool:
    """删除对应动作记录。"""
    action = get_action_record(user_id, bvid, action_type)
    if not action:
        return False
    db.session.delete(action)
    db.session.commit()
    return True


def bump_history(user_id: int, bvid: str) -> None:
    """记录观看历史：若存在则更新时间，否则新增。"""
    history = get_action_record(user_id, bvid, 'history')
    if history:
        history.create_time = func.now()
    else:
        db.session.add(UserAction(user_id=user_id, bvid=bvid, action_type='history'))
    db.session.commit()


# --- 认证路由 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user:
            authenticated = False
            # 历史数据可能存明文；如果是明文且校验通过，会同步升级为哈希。
            if is_hashed_password(user.password):
                authenticated = verify_password(user.password, password)
            elif user.password == password:
                user.password = hash_password(password)
                db.session.commit()
                authenticated = True
            if authenticated:
                login_user(user)
                return redirect(url_for('dashboard'))
        flash('用户名或密码错误', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('请输入用户名和密码', 'danger')
        elif username_exists(username):
            flash('用户名已存在', 'danger')
        else:
            try:
                new_user = User(
                    username=username,
                    password=hash_password(password),
                    description='这个人很懒，还没有填写个人介绍',
                    avatar=''
                )
                db.session.add(new_user)
                db.session.commit()
                flash('注册成功，请登录', 'success')
                return redirect(url_for('login'))
            except IntegrityError:
                db.session.rollback()
                flash('用户名已存在', 'danger')
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- 页面路由 ---
@app.route('/')
@login_required
def dashboard(): return render_template('dashboard.html', active='dashboard')


@app.route('/resources')
@login_required
def resources(): return render_template('resources.html', active='resources')


@app.route('/compare')
@login_required
def compare():
    ups = db.session.query(Video.up_name).distinct().all()
    up_list = [u[0] for u in ups]
    return render_template('compare.html', active='compare', up_list=up_list)

@app.route('/recommend')
@login_required
def recommend(): return render_template('recommend.html', active='recommend')


@app.route('/profile')
@login_required
def profile(): return render_template('profile.html', active='profile')


# --- API 接口 ---

@app.route('/api/stats')
def get_stats():
    """仪表盘数据：全局统计 + 玫瑰图 + 干货度散点图。"""

    # 1) 基础计数
    total_videos = Video.query.count()
    total_teachers = db.session.query(func.count(func.distinct(Video.up_name))).scalar()
    total_views = db.session.query(func.sum(Video.view_count)).scalar() or 0
    avg_score = db.session.query(func.avg(Video.dry_goods_ratio)).scalar() or 0

    # 2) 干货度榜单 (Top 8)
    top_list = Video.query.order_by(Video.dry_goods_ratio.desc()).limit(8).all()
    rank_titles = [v.title[:15] + '...' if len(v.title) > 15 else v.title for v in top_list][::-1]
    rank_scores = [v.dry_goods_ratio for v in top_list][::-1]
    rank_bvids = [v.bvid for v in top_list][::-1]

    # 3) 学科分类分布（玫瑰图数据）：phase/subject 都写进 category 以兼容旧字段
    cat_stats = db.session.query(Video.category, func.count(Video.bvid)) \
        .filter(Video.category != None, Video.category != '') \
        .group_by(Video.category).all()

    # 构造 ECharts 需要的 [{name: 'xx', value: 10}, ...] 格式
    category_data = [{'name': c[0], 'value': c[1]} for c in cat_stats]

    # 4) 散点图数据：过滤掉超短或超长视频，按播放量取 Top 150
    scatter_data = []
    hot_videos = Video.query.filter(Video.duration > 300, Video.duration < 10800).order_by(
        Video.view_count.desc()).limit(150).all()
    for v in hot_videos:
        duration_min = round(v.duration / 60, 1)
        scatter_data.append([duration_min, v.dry_goods_ratio, v.title, v.up_name, v.bvid])

    return jsonify({
        'total_videos': total_videos,
        'total_teachers': total_teachers,
        'total_views': total_views,
        'avg_score': round(avg_score, 1),
        'rank_titles': rank_titles,
        'rank_scores': rank_scores,
        'rank_bvids': rank_bvids,
        'scatter_data': scatter_data,
        'category_data': category_data  # 返回分类数据
    })

@app.route('/api/videos')
def get_videos():
    """视频列表：支持关键词、分类筛选与播放量/时间/干货度排序。"""

    # 获取参数
    page = request.args.get('page', 1, type=int)
    per_page = 12
    sort_by = request.args.get('sort', 'dry_goods')
    category = request.args.get('category', 'all')
    keyword = request.args.get('q', '')

    query = Video.query

    # 1) 关键词搜索 (标题 OR 标签 OR UP主)
    if keyword:
        query = query.filter(or_(
            Video.title.like(f'%{keyword}%'),
            Video.tags.like(f'%{keyword}%'),
            Video.up_name.like(f'%{keyword}%')
        ))

    # 2) 分类筛选（兼容 phase/subject/category）
    # 前端传来的 category 可能是 "升学备考"(phase)，也可能是 "考研数学"(subject)
    if category != 'all':
        query = query.filter(or_(
            Video.phase == category,    # 匹配一级分类（阶段）
            Video.subject == category,  # 匹配二级分类（科目）
            Video.category == category  # 兼容旧数据
        ))

    # 3) 排序逻辑：播放量/最新/干货度（默认）
    if sort_by == 'views':
        query = query.order_by(Video.view_count.desc())
    elif sort_by == 'new':
        query = query.order_by(Video.pubdate.desc())
    else:
        query = query.order_by(Video.dry_goods_ratio.desc())

    # 4. 分页
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    videos = pagination.items

    return jsonify({
        'videos': [serialize_video(v) for v in videos],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })


@app.route('/api/hot_tags')
def get_hot_tags():
    """热门标签词频：取前 200 条视频的 tags 聚合后返回 Top 15。"""
    videos = Video.query.filter(Video.tags != '').limit(200).all()
    all_tags = []
    for v in videos:
        if v.tags:
            parts = re.split(r'[\,\uFF0C\u3001\s]+', v.tags)
            all_tags.extend([t for t in parts if t])
    return jsonify([tag for tag, count in Counter(all_tags).most_common(15)])


@app.route('/api/compare_data')
def compare_data():
    """UP 主对比：聚合播放/收藏/互动等指标，归一化后输出雷达图与词云。"""
    up1 = request.args.get('up1')
    up2 = request.args.get('up2')
    if not up1 or not up2:
        return jsonify({'msg': '缺少 up 参数'}), 400

    # 计算各 UP 真实数据的聚合，避免模拟占位
    summaries = db.session.query(
        Video.up_name,
        func.count(Video.bvid).label('video_count'),
        func.sum(Video.view_count).label('total_views'),
        func.sum(Video.favorite_count).label('total_fav'),
        func.sum(Video.reply_count).label('total_reply'),
        func.sum(Video.danmaku_count).label('total_danmaku'),
        func.sum(Video.duration).label('total_duration'),
        func.min(Video.pubdate).label('first_pub')
    ).group_by(Video.up_name).all()

    summary_map = {s.up_name: s for s in summaries}
    stat_cache = {}
    def safe_rate(numerator, denominator):
        """分母为 0 时返回 0，避免抛异常。"""
        return round((numerator / denominator) * 100, 2) if denominator else 0

    def normalize(value, max_value):
        """将指标压缩到 0-100：用对数平滑缩小极端差距。"""
        if not max_value or max_value <= 0:
            return 0
        val_log = math.log(value + 1) if value > 0 else 0
        max_log = math.log(max_value + 1)
        if max_log == 0: return 0
        score = (val_log / max_log) * 100
        if score < 5 and value > 0: score = 5
        return round(min(score, 100), 1)

    # 预计算每个 UP 的原始指标，避免重复计算
    from datetime import datetime
    now_dt = datetime.utcnow()
    for s in summaries:
        video_count = s.video_count or 0
        total_views = s.total_views or 0
        total_fav = s.total_fav or 0
        total_interact = (s.total_reply or 0) + (s.total_danmaku or 0)
        fav_rate = safe_rate(total_fav, total_views)
        interact_avg = total_interact / max(video_count, 1) / 2  # (弹幕+评论)/视频数/2
        duration_hours = (s.total_duration or 0) / 3600 or 0
        depth_score = total_fav / max(duration_hours, 1)  # 收藏/时长(小时)
        if s.first_pub:
            days_span = max((now_dt - s.first_pub).total_seconds() / 86400, 1)
        else:
            days_span = 30  # 无发布时间数据时给一个平滑基准
        activity_per_week = (video_count / days_span) * 7  # 每周发片数

        stat_cache[s.up_name] = {
            'video_count': video_count,
            'views': total_views,
            'fav': total_fav,
            'fav_rate': fav_rate,
            'interact_avg': interact_avg,
            'depth_score': depth_score,
            'activity': activity_per_week,
            'total_interact': total_interact,
            'total_duration_hours': duration_hours,
        }

    # 评分归一化基准
    if stat_cache:
        max_views = max(c['views'] for c in stat_cache.values()) or 1
        max_fav_rate = max(c['fav_rate'] for c in stat_cache.values()) or 1
        max_interact = max(c['interact_avg'] for c in stat_cache.values()) or 1
        max_depth = max(c['depth_score'] for c in stat_cache.values()) or 1
        max_activity = max(c['activity'] for c in stat_cache.values()) or 1
    else:
        max_views = max_fav_rate = max_interact = max_depth = max_activity = 1

    missing = [u for u in (up1, up2) if u not in stat_cache]
    if missing:
        return jsonify({'msg': "未找到 UP：" + ", ".join(missing)}), 404

    def get_up_data(up_name):
        summary = stat_cache.get(up_name)
        if not summary:
            return {'radar': [0] * 5, 'metrics': {}, 'words': []}

        total_views = summary['views']
        fav_rate = summary['fav_rate']
        inter_avg = summary['interact_avg']
        depth_score = summary['depth_score']
        activity = summary['activity']
        video_count = summary['video_count']
        total_fav = summary['fav']
        total_interact = summary['total_interact']

        # 构造雷达图数据（归一化到 0-100）
        # 顺序：传播力, 质量(收藏率), 互动热度, 深度收藏, 创作活跃
        stats = [
            normalize(total_views, max_views),
            normalize(fav_rate, max_fav_rate),
            normalize(inter_avg, max_interact),
            normalize(depth_score, max_depth),
            normalize(activity, max_activity)
        ]

        # 词云逻辑 (保持不变)
        videos = Video.query.filter_by(up_name=up_name).all()
        text = "".join([v.title + (v.tags or "") for v in videos])
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很',
                      '到', '说', '去', '你', '会', '着', '没有', '看', '怎么', '视频', '高数', '数学', '考研',
                      '这一', '这个', '那个', '还是', '因为', '所以', '如果', '就是', '什么', '主要', '很多', '非常',
                      '大家'}

        words = jieba.cut(text)
        valid_words = []
        for w in words:
            if len(w) > 1 and w not in stop_words and not w.isdigit():
                valid_words.append(w)

        word_counts = Counter(valid_words).most_common(150)
        word_cloud_data = [{'name': k, 'value': v} for k, v in word_counts] or [{'name': up_name, 'value': 1}]

        # 前端表格展示指标（Key 必须与前端一致）
        metrics = {
            'view': {'value': total_views, 'unit': '次播放'},
            'rate': {'value': fav_rate, 'unit': '%'},
            'inter': {'value': round(inter_avg, 2), 'unit': '次/视频'},
            'depth': {'value': round(depth_score, 2), 'unit': '收藏/小时'},
            'active': {'value': round(activity, 2), 'unit': '视频/周'}
        }

        return {'radar': stats, 'metrics': metrics, 'words': word_cloud_data}

    # === 评分归一化基准结束 ===

    data1 = get_up_data(up1)
    data2 = get_up_data(up2)

    return jsonify({
        'up1': data1,
        'up2': data2
    })


@app.route('/api/recommend')
def api_recommend():
    """推荐接口：按场景（期末/基础/习题/猜你喜欢）返回 8 个视频。"""
    scene = request.args.get('scene', 'guess')
    query = Video.query

    # 1. 【期末突击】场景：看考试关键词 + 阶段=期末突击，按播放量取热门
    if scene == 'exam':
        query = query.filter(or_(
            Video.phase == '期末突击',
            Video.title.like('%期末%'),
            Video.title.like('%突击%'),
            Video.title.like('%速成%')
        ))
        query = query.order_by(Video.view_count.desc())

    # 2. 【考研基础】场景：限定升学备考 + 核心科目，过滤掉过短视频
    elif scene == 'basic':
        query = query.filter(
            Video.phase == '升学备考',
            Video.subject.in_(['高等数学', '线性代数', '概率论'])
        )
        query = query.filter(Video.duration > 1800)
        query = query.order_by(Video.dry_goods_ratio.desc())

    # 3. 【习题冲刺】场景：按“习题/真题”标签筛选，收藏量越高排序越前
    elif scene == 'exercise':
        query = query.filter(or_(
            Video.subject == '习题精讲',
            Video.subject == '真题实战',
            Video.title.like('%习题%'),
            Video.title.like('%真题%')
        ))
        query = query.order_by(Video.favorite_count.desc())

    # 4. 【猜你喜欢】：有登录态就基于最近观看科目做冷启动；否则随机打散
    else:
        if current_user.is_authenticated:
            last_action = UserAction.query.filter_by(
                user_id=current_user.id, action_type='history'
            ).order_by(UserAction.create_time.desc()).first()

            if last_action:
                last_video = Video.query.get(last_action.bvid)
                if last_video and last_video.subject:
                    query = query.filter(
                        Video.subject == last_video.subject,
                        Video.bvid != last_video.bvid
                    ).order_by(func.rand())
                else:
                    query = query.order_by(func.rand())
            else:
                query = query.order_by(func.rand())
        else:
            query = query.order_by(func.rand())

    # 取前 8 个返回
    videos = query.limit(8).all()
    return jsonify([serialize_video(v) for v in videos])


@app.route('/api/user_profile')
@login_required
def get_user_profile():
    """个人中心数据：返回收藏/待办/历史及头像/简介。"""
    user = current_user
    avatar_url = f"/static/avatars/{user.avatar}" if user.avatar else "https://placehold.co/100x100/00A1D6/FFFFFF?text=User"

    # 1. 收藏
    fav_actions = UserAction.query.filter_by(user_id=user.id, action_type='fav').order_by(
        UserAction.create_time.desc()).all()
    fav_videos = get_videos_from_actions(fav_actions)

    # 2. 待办
    todo_actions = UserAction.query.filter_by(user_id=user.id, action_type='todo').order_by(
        UserAction.create_time.desc()).all()
    todo_videos = get_videos_from_actions(todo_actions, include_status=True)

    # 3. 历史记录（限制返回条数，避免响应过大）
    history_query = UserAction.query.filter_by(user_id=user.id, action_type='history').order_by(
        UserAction.create_time.desc())
    history_total = history_query.count()
    history_actions = history_query.limit(HISTORY_LIMIT).all()
    history_videos = get_videos_from_actions(history_actions)

    # 只统计能在视频库匹配到的待办；total 用未完成数量，done 用已完成数量，避免出现“列表空但计数>0”
    pending_todos = [v for v in todo_videos if v.get('status') == 0]
    done_todos = [v for v in todo_videos if v.get('status') == 1]
    todo_pending = len(pending_todos)
    todo_done = len(done_todos)
    todo_total = todo_pending + todo_done

    return jsonify({
        'user_info': {'username': user.username, 'description': user.description, 'avatar': avatar_url},
        'favorites': fav_videos,
        'todos': todo_videos,
        'history': history_videos,  # 返回历史数据
        'history_total': history_total,
        'todo_stats': {'total': todo_total, 'pending': todo_pending, 'done': todo_done}
    })


def get_videos_from_actions(actions, include_status=False):
    """辅助：根据用户动作列表批量取回视频详情，必要时携带状态/时间。"""
    if not actions: return []
    bvids = [a.bvid for a in actions]
    video_map = {v.bvid: v for v in Video.query.filter(Video.bvid.in_(bvids)).all()}
    result = []
    for action in actions:
        if action.bvid in video_map:
            v_data = serialize_video(video_map[action.bvid])
        else:
            # fallback：视频不在库里时也返回占位，避免前端列表空白
            v_data = {
                'bvid': action.bvid,
                'title': '视频不存在或未收录',
                'pic_url': 'https://placehold.co/320x200/eee/999?text=Missing',
                'link': f"https://www.bilibili.com/video/{action.bvid}"
            }
        if include_status:
            v_data['status'] = getattr(action, 'status', None)
        # 增加记录时间，用于前端显示“X分钟前观看”
        v_data['action_time'] = action.create_time.strftime('%Y-%m-%d %H:%M')
        result.append(v_data)
    return result


@app.route('/api/log_history', methods=['POST'])
@login_required
def log_history():
    """记录观看历史：前端在进入详情页时调用。"""
    data = request.get_json(silent=True) or {}
    bvid = data.get('bvid') or request.form.get('bvid')
    if not bvid:
        return jsonify({'msg': '缺少 bvid'}), 400
    bump_history(current_user.id, bvid)
    return jsonify({'msg': '记录成功'})


@app.route('/go/<bvid>')
@login_required
def go_bvid(bvid):
    """跳转前记录足迹，确保所有从站内点击的视频都会留痕。"""
    bump_history(current_user.id, bvid)
    return redirect(f"https://www.bilibili.com/video/{bvid}")


@app.route('/api/update_profile', methods=['POST'])
@login_required
def update_user_profile():
    """更新用户名/签名/头像，包含文件大小、类型及图像重采样校验。"""
    user = current_user
    username = request.form.get('username')
    description = request.form.get('description')
    if username and username != user.username:
        if username_exists(username, exclude_user_id=user.id):
            return jsonify({'msg': '用户名已存在', 'code': 400}), 400
        user.username = username
    if description is not None:
        user.description = description
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename:
            if not allowed_avatar(file.filename):
                return jsonify({'msg': '头像格式不支持', 'code': 400}), 400
            if file.mimetype and not file.mimetype.startswith('image/'):
                return jsonify({'msg': '仅支持图片上传', 'code': 400}), 400
            file.stream.seek(0, os.SEEK_END)
            size = file.stream.tell()
            file.stream.seek(0)
            if size > MAX_AVATAR_SIZE:
                return jsonify({'msg': '头像文件过大', 'code': 400}), 400
            try:
                img = Image.open(file.stream).convert('RGB')
            except Exception:
                return jsonify({'msg': '无效的图片文件', 'code': 400}), 400
            img.thumbnail((256, 256))
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)
            filename = f"user_{user.id}_{int(time.time())}.jpg"
            with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as out:
                out.write(buffer.read())
            user.avatar = filename
    db.session.commit()
    return jsonify({'msg': '更新成功', 'code': 200})


@app.route('/api/action', methods=['POST'])
@login_required
def user_action():
    """新增收藏/待看/历史动作（历史在 log_history 也会写入）。"""
    data = request.json or {}
    bvid = data.get('bvid')
    action_type = data.get('type')
    if not bvid or not action_type:
        return jsonify({'msg': '缺少参数'}), 400
    if not ensure_action_allowed(action_type):
        return jsonify({'msg': '非法操作'}), 400
    created = create_action(current_user.id, bvid, action_type)
    if created:
        return jsonify({'msg': '操作成功'})
    return jsonify({'msg': '已存在'})


@app.route('/api/remove_action', methods=['POST'])
@login_required
def remove_action():
    """删除收藏/待看记录。"""
    data = request.json or {}
    bvid = data.get('bvid')
    action_type = data.get('type')
    if not bvid or not action_type:
        return jsonify({'msg': '缺少参数'}), 400
    if not ensure_action_allowed(action_type):
        return jsonify({'msg': '非法操作'}), 400
    if delete_action(current_user.id, bvid, action_type):
        return jsonify({'msg': '删除成功'})
    return jsonify({'msg': '失败'}), 404


@app.route('/api/toggle_todo', methods=['POST'])
@login_required
def toggle_todo():
    """切换待看状态：0<->1。"""
    data = request.json or {}
    bvid = data.get('bvid')
    if not bvid:
        return jsonify({'msg': '缺少参数'}), 400
    action = get_action_record(current_user.id, bvid, 'todo')
    if not action:
        return jsonify({'msg': '失败'}), 404
    action.status = 1 if action.status == 0 else 0
    db.session.commit()
    return jsonify({'msg': '更新成功', 'status': action.status})


def serialize_video(v):
    """统一的前端视频字典结构，避免重复模板拼装。"""
    up_mid = getattr(v, 'up_mid', None)
    up_face = getattr(v, 'up_face', '') or ''
    duration = v.duration or 0
    category = v.category or ''
    return {
        'bvid': v.bvid,
        'title': v.title,
        'up_name': v.up_name,
        'up_mid': up_mid,
        'up_face': up_face,
        'pic_url': v.pic_url,
        'view_count': v.view_count or 0,
        'favorite_count': v.favorite_count or 0,
        'reply_count': v.reply_count or 0,
        'danmaku_count': v.danmaku_count or 0,
        'dry_goods_ratio': v.dry_goods_ratio,
        'category': category,
        'duration': duration,
        'pubdate': v.pubdate.isoformat() if v.pubdate else None,
        'link': f"https://www.bilibili.com/video/{v.bvid}",
        'up_space': f"https://space.bilibili.com/{up_mid}" if up_mid else None
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
