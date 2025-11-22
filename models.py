from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import func

db = SQLAlchemy()

# 1. 视频表
class Video(db.Model):
    __tablename__ = 'videos'
    bvid = db.Column(db.String(20), primary_key=True)
    title = db.Column(db.String(255))
    up_name = db.Column(db.String(100))
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
    category = db.Column(db.String(50))
    dry_goods_ratio = db.Column(db.Float)

# 2. 用户表 (✅ description 在这里)
class User(UserMixin,db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(100))
    description = db.Column(db.String(255))
    avatar = db.Column(db.String(200))

# 3. 用户行为表 (✅ create_time 在这里)
class UserAction(db.Model):
    __tablename__ = 'user_actions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    bvid = db.Column(db.String(20))
    action_type = db.Column(db.String(20)) # 'fav'、'todo' 或 'history'
    status = db.Column(db.Integer, default=0)
    create_time = db.Column(db.DateTime, default=func.now())