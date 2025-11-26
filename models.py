"""数据模型定义：封装所有与数据库表对应的 SQLAlchemy ORM 类。"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import func

db = SQLAlchemy()


class Video(db.Model):
    """采集到的 B 站课程/题解视频，既存储基础播放数据，也存储分类结果。"""

    __tablename__ = 'videos'

    # 主键使用 bvid，方便前后端直链跳转。
    bvid = db.Column(db.String(20), primary_key=True)
    title = db.Column(db.String(255))
    up_name = db.Column(db.String(100), index=True)
    up_mid = db.Column(db.BigInteger)       # UP 主 uid，可拼个人空间链接
    up_face = db.Column(db.String(500))     # 头像链接，前端展示用
    pic_url = db.Column(db.String(500))     # 封面图

    # 播放互动数据
    view_count = db.Column(db.Integer)
    danmaku_count = db.Column(db.Integer)
    reply_count = db.Column(db.Integer)
    favorite_count = db.Column(db.Integer)

    duration = db.Column(db.Integer)        # 视频时长（秒）
    pubdate = db.Column(db.DateTime, index=True)        # 发布时间
    tags = db.Column(db.String(500))        # 搜索关键词或标签

    category = db.Column(db.String(50))     # 旧版分类字段，保留兼容历史数据
    phase = db.Column(db.String(50), index=True)        # 一级分类：阶段（如：校内同步、升学备考）
    subject = db.Column(db.String(50), index=True)      # 二级分类：科目/主题（如：高等数学、线性代数）

    dry_goods_ratio = db.Column(db.Float)   # 干货度指标：收藏/播放*1000 的估算值


class User(UserMixin, db.Model):
    """用户账户表：仅存储基本资料和密码哈希。"""

    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, index=True)
    password = db.Column(db.String(255))
    description = db.Column(db.String(255))
    avatar = db.Column(db.String(200))


class UserAction(db.Model):
    """用户行为表：收藏/待看/历史记录都会落在这里。"""

    __tablename__ = 'user_actions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)         # 关联 users.id（未建外键，避免迁移依赖）
    bvid = db.Column(db.String(20))         # 关联 videos.bvid
    action_type = db.Column(db.String(20))  # fav / todo / history
    status = db.Column(db.Integer, default=0)       # todo 的完成状态；其他类型保持 0
    create_time = db.Column(db.DateTime, default=func.now())

    __table_args__ = (
        db.UniqueConstraint('user_id', 'bvid', 'action_type', name='uq_user_action'),
    )
