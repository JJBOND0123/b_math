import secrets


class Config:
    """Flask configuration with static defaults."""

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:123456@localhost/bilibili_math_db?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    SECRET_KEY = secrets.token_hex(32)
