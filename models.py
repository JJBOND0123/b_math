from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import func

db = SQLAlchemy()


class Video(db.Model):
    __tablename__ = 'videos'
    bvid = db.Column(db.String(20), primary_key=True)
    title = db.Column(db.String(255))
    up_name = db.Column(db.String(100))
    up_mid = db.Column(db.BigInteger)
    up_face = db.Column(db.String(500))
    pic_url = db.Column(db.String(500))

    view_count = db.Column(db.Integer)
    danmaku_count = db.Column(db.Integer)
    reply_count = db.Column(db.Integer)
    favorite_count = db.Column(db.Integer)
    coin_count = db.Column(db.Integer)
    share_count = db.Column(db.Integer)

    duration = db.Column(db.Integer)
    pubdate = db.Column(db.DateTime)
    tags = db.Column(db.String(500))

    category = db.Column(db.String(50))  # 旧分类字段(保留作为备用)

    # ✅ 新增以下两行，与数据库保持一致
    phase = db.Column(db.String(50))  # 一级分类：阶段 (如：校内同步)
    subject = db.Column(db.String(50))  # 二级分类：科目 (如：高等数学)

    dry_goods_ratio = db.Column(db.Float)


# 2. 用户表 (保持不变)
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(255))
    description = db.Column(db.String(255))
    avatar = db.Column(db.String(200))


# 3. 用户行为表 (保持不变)
class UserAction(db.Model):
    __tablename__ = 'user_actions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    bvid = db.Column(db.String(20))
    action_type = db.Column(db.String(20))
    status = db.Column(db.Integer, default=0)
    create_time = db.Column(db.DateTime, default=func.now())
