import os
import time
import jieba
from collections import Counter
import re
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from config import Config
from models import db, Video, User, UserAction
from sqlalchemy import func, or_

app = Flask(__name__)
app.config.from_object(Config)

UPLOAD_FOLDER = 'static/avatars'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'your_secret_key_here'

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- 认证路由 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('用户名或密码错误', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'danger')
        else:
            new_user = User(username=username, password=password, description='新同学', avatar='')
            db.session.add(new_user)
            db.session.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
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

    # 预加载每个 UP 的封面作为头像占位
    videos = db.session.query(Video.up_name, Video.pic_url, Video.pubdate) \
        .order_by(Video.up_name, Video.pubdate.desc()).all()
    up_avatars = {}
    for up_name, pic_url, _ in videos:
        if up_name not in up_avatars and pic_url:
            up_avatars[up_name] = pic_url

    return render_template('compare.html', active='compare', up_list=up_list, up_avatars=up_avatars)


@app.route('/recommend')
@login_required
def recommend(): return render_template('recommend.html', active='recommend')


@app.route('/profile')
@login_required
def profile(): return render_template('profile.html', active='profile')


# --- API 接口 ---

@app.route('/api/stats')
def get_stats():
    # 1. 基础计数
    total_videos = Video.query.count()
    total_teachers = db.session.query(func.count(func.distinct(Video.up_name))).scalar()
    total_views = db.session.query(func.sum(Video.view_count)).scalar() or 0
    avg_score = db.session.query(func.avg(Video.dry_goods_ratio)).scalar() or 0

    # 2. 榜单数据 (Top 8)
    top_list = Video.query.order_by(Video.dry_goods_ratio.desc()).limit(8).all()
    rank_titles = [v.title[:15] + '...' if len(v.title) > 15 else v.title for v in top_list][::-1]
    rank_scores = [v.dry_goods_ratio for v in top_list][::-1]
    rank_bvids = [v.bvid for v in top_list][::-1]

    # 3. ✅ 新增：学科分类分布 (玫瑰图数据)
    # 统计每个分类下的视频数量
    cat_stats = db.session.query(Video.category, func.count(Video.bvid)) \
        .filter(Video.category != None, Video.category != '') \
        .group_by(Video.category).all()

    # 构造 ECharts 需要的 [{name: 'xx', value: 10}, ...] 格式
    category_data = [{'name': c[0], 'value': c[1]} for c in cat_stats]

    # 4. 散点图数据
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
        'category_data': category_data  # ✅ 返回分类数据
    })

@app.route('/api/videos')
def get_videos():
    # 获取参数
    page = request.args.get('page', 1, type=int)
    per_page = 12  # 每页显示 12 个
    sort_by = request.args.get('sort', 'dry_goods')
    category = request.args.get('category', 'all')
    keyword = request.args.get('q', '')  # 搜索关键词

    query = Video.query

    # 1. ✅ 核心修改：关键词搜索范围扩大 (标题 OR 标签 OR UP主)
    if keyword:
        query = query.filter(or_(
            Video.title.like(f'%{keyword}%'),
            Video.tags.like(f'%{keyword}%'),
            Video.up_name.like(f'%{keyword}%')  # 新增这一行，支持搜UP主
        ))

    # 2. 分类筛选
    if category != 'all':
        query = query.filter(Video.category == category)

    # 3. 排序
    if sort_by == 'views':
        query = query.order_by(Video.view_count.desc())
    elif sort_by == 'new':
        query = query.order_by(Video.pubdate.desc())
    else:
        query = query.order_by(Video.dry_goods_ratio.desc())

    # 4. 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    videos = pagination.items

    return jsonify({
        'videos': [serialize_video(v) for v in videos],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


@app.route('/api/hot_tags')
def get_hot_tags():
    videos = Video.query.filter(Video.tags != '').limit(200).all()
    all_tags = []
    for v in videos:
        if v.tags: all_tags.extend([t.strip() for t in v.tags.replace('，', ',').split(',') if t.strip()])
    return jsonify([tag for tag, count in Counter(all_tags).most_common(15)])


@app.route('/api/compare_data')
def compare_data():
    up1 = request.args.get('up1')
    up2 = request.args.get('up2')

    def get_up_data(up_name):
        videos = Video.query.filter_by(up_name=up_name).all()
        if not videos:
            return [0] * 5, []

        count = len(videos)
        total_views = sum(v.view_count for v in videos)
        total_reply = sum(v.reply_count for v in videos)
        # 防止除以零
        avg_score = sum(v.dry_goods_ratio for v in videos) / count if count > 0 else 0

        # 计算互动率 (评论/播放)，并在合理范围内归一化
        # 假设 1% 的评论率是极高的 (100分)
        interaction_rate = (total_reply / total_views) if total_views > 0 else 0

        # 归一化逻辑 (调整了权重，使其更符合实际感知)
        score_prod = min(count * 2, 100)  # 产出积累 (量)
        score_pop = min(total_views / 200000 * 100, 100)  # 流量层级 (热度)
        score_rep = min(avg_score * 2, 100)  # 内容质量 (收藏率衍生)
        score_inter = min(interaction_rate * 200 * 100, 100)  # 粉丝粘性 (互动)
        score_hard = avg_score  # 收藏率指标 (原干货率)

        # 调整顺序以匹配前端雷达图顺时针方向：
        # 产出 -> 流量 -> 质量 -> 粘性 -> 收藏率
        stats = [
            round(score_prod, 1),
            round(score_pop, 1),
            round(score_rep, 1),
            round(score_inter, 1),
            round(score_hard, 1)
        ]

        # --- 词云逻辑保持不变 ---
        text = ""
        for v in videos: text += v.title + (v.tags if v.tags else "")

        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很',
                      '到', '说', '去', '你', '会', '着', '没有', '看', '怎么', '视频', '高数', '数学', '考研',
                      '这一', '这个', '那个', '还是', '因为', '所以', '如果', '就是', '什么', '主要', '很多', '非常'}

        words = jieba.cut(text)
        valid_words = []
        for w in words:
            if len(w) > 1 and w not in stop_words and not w.isdigit():
                valid_words.append(w)

        word_counts = Counter(valid_words).most_common(60)
        word_cloud_data = [{'name': k, 'value': v} for k, v in word_counts]

        return stats, word_cloud_data

    stats1, words1 = get_up_data(up1)
    stats2, words2 = get_up_data(up2)

    return jsonify({
        'up1_stats': stats1,
        'up2_stats': stats2,
        'up1_words': words1,
        'up2_words': words2
    })

@app.route('/api/recommend')
def api_recommend():
    scene = request.args.get('scene', 'guess')
    query = Video.query
    if scene == 'exam':
        query = query.filter(Video.duration < 1800).order_by(Video.view_count.desc())
    elif scene == 'basic':
        query = query.filter(Video.duration > 2400).order_by(Video.dry_goods_ratio.desc())
    elif scene == 'exercise':
        query = query.filter(Video.title.like('%习题%')).order_by(Video.favorite_count.desc())
    else:
        query = query.order_by(func.random())
    videos = query.limit(8).all()
    return jsonify([serialize_video(v) for v in videos])


# ✅ 修改：获取用户数据 (增加 history)
@app.route('/api/user_profile')
@login_required
def get_user_profile():
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

    # 3. ✅ 历史记录 (新增)
    history_actions = UserAction.query.filter_by(user_id=user.id, action_type='history').order_by(
        UserAction.create_time.desc()).limit(20).all()
    history_videos = get_videos_from_actions(history_actions)

    todo_total = len(todo_actions)
    todo_done = sum(1 for a in todo_actions if a.status == 1)

    return jsonify({
        'user_info': {'username': user.username, 'description': user.description, 'avatar': avatar_url},
        'favorites': fav_videos,
        'todos': todo_videos,
        'history': history_videos,  # ✅ 返回历史数据
        'todo_stats': {'total': todo_total, 'done': todo_done}
    })


# 辅助函数：从 Action 列表查视频
def get_videos_from_actions(actions, include_status=False):
    if not actions: return []
    bvids = [a.bvid for a in actions]
    video_map = {v.bvid: v for v in Video.query.filter(Video.bvid.in_(bvids)).all()}
    result = []
    for action in actions:
        if action.bvid in video_map:
            v_data = serialize_video(video_map[action.bvid])
            if include_status: v_data['status'] = action.status
            # 增加记录时间，用于前端显示“X分钟前观看”
            v_data['action_time'] = action.create_time.strftime('%Y-%m-%d %H:%M')
            result.append(v_data)
    return result


# ✅ 新增：记录历史接口
@app.route('/api/log_history', methods=['POST'])
@login_required
def log_history():
    bvid = request.json.get('bvid')
    # 检查是否已存在
    exists = UserAction.query.filter_by(user_id=current_user.id, bvid=bvid, action_type='history').first()
    if exists:
        # 如果存在，更新时间到最新
        exists.create_time = func.now()
    else:
        # 不存在则插入
        db.session.add(UserAction(user_id=current_user.id, bvid=bvid, action_type='history'))
    db.session.commit()
    return jsonify({'msg': 'Recorded'})


@app.route('/api/update_profile', methods=['POST'])
@login_required
def update_user_profile():
    user = current_user
    username = request.form.get('username')
    description = request.form.get('description')
    if username: user.username = username
    if description: user.description = description
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"user_{user.id}_{int(time.time())}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.avatar = filename
    db.session.commit()
    return jsonify({'msg': '修改成功', 'code': 200})


@app.route('/api/action', methods=['POST'])
@login_required
def user_action():
    data = request.json
    exists = UserAction.query.filter_by(user_id=current_user.id, bvid=data.get('bvid'),
                                        action_type=data.get('type')).first()
    if not exists:
        db.session.add(UserAction(user_id=current_user.id, bvid=data.get('bvid'), action_type=data.get('type')))
        db.session.commit()
        return jsonify({'msg': '成功'})
    return jsonify({'msg': '已存在'})


@app.route('/api/remove_action', methods=['POST'])
@login_required
def remove_action():
    data = request.json
    action = UserAction.query.filter_by(user_id=current_user.id, bvid=data.get('bvid'),
                                        action_type=data.get('type')).first()
    if action:
        db.session.delete(action)
        db.session.commit()
        return jsonify({'msg': '删除成功'})
    return jsonify({'msg': '失败'}, 404)


@app.route('/api/toggle_todo', methods=['POST'])
@login_required
def toggle_todo():
    bvid = request.json.get('bvid')
    action = UserAction.query.filter_by(user_id=current_user.id, bvid=bvid, action_type='todo').first()
    if action:
        action.status = 1 if action.status == 0 else 0
        db.session.commit()
        return jsonify({'msg': '更新成功'})
    return jsonify({'msg': '失败'}, 404)


def serialize_video(v):
    return {'bvid': v.bvid, 'title': v.title, 'up': v.up_name, 'pic': v.pic_url, 'view': v.view_count,
            'score': v.dry_goods_ratio, 'tag': v.category, 'link': f"https://www.bilibili.com/video/{v.bvid}"}


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)