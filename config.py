import os
import secrets


class Config:
    """Flask configuration. Override with env vars in non-local environments."""
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        os.getenv("DB_URL", "mysql+pymysql://root:123456@localhost/bilibili_math_db?charset=utf8mb4"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    # 避免固定秘钥：优先取环境变量，否则每次启动随机生成（生产环境务必配置环境变量）
    SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("FLASK_SECRET_KEY")) or secrets.token_hex(32)
