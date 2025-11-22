# config.py
import os

class Config:
    # 替换你的数据库密码
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/bilibili_math_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    SECRET_KEY = 'bilibili_math_secret_key' # 用于Session