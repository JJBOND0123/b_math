import os

class Config:
    """Flask configuration. Override with env vars in non-local environments."""
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        os.getenv("DB_URL", "mysql+pymysql://root:123456@localhost/bilibili_math_db?charset=utf8mb4"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("FLASK_SECRET_KEY", "bilibili_math_secret_key"))
