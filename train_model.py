import jieba
import joblib
import os
from sqlalchemy import create_engine
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# 数据库配置（可用环境变量覆盖）
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "db": os.getenv("DB_NAME", "bilibili_math_db"),
    "charset": os.getenv("DB_CHARSET", "utf8mb4")
}


def build_db_url() -> str:
    env_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if env_url:
        return env_url
    return f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['db']}?charset={DB_CONFIG['charset']}"


def get_training_data():
    """Load labeled video data for training."""
    engine = create_engine(build_db_url())
    sql = "SELECT title, tags, subject FROM videos WHERE subject != '其他' AND subject IS NOT NULL"
    return pd.read_sql(sql, engine)


def train():
    print("1. 正在加载数据...")
    try:
        df = get_training_data()
    except Exception as e:
        print(f"[WARN] 数据库连接失败: {e}")
        return

    if len(df) < 50:
        print(f"[WARN] 数据量太少（只有 {len(df)} 条），无法训练，请先运行爬虫抓取更多数据。")
        return

    # 2. 数据预处理
    print("2. 正在进行中文分词...")
    # 组合文本：标题 + 标签
    df['text'] = df['title'] + " " + df['tags'].fillna('')

    # 使用 jieba 分词
    def clean_text(text):
        if not isinstance(text, str): return ""
        words = jieba.cut(text)
        # 去除停用词和单字
        return " ".join([w for w in words if len(w) > 1])

    df['cut_text'] = df['text'].apply(clean_text)

    # --- 过滤掉样本极少的类别 ---
    subject_counts = df['subject'].value_counts()
    print("类别分布情况：\n", subject_counts)

    # 只保留样本数大于 5 的类别
    valid_subjects = subject_counts[subject_counts > 5].index
    df = df[df['subject'].isin(valid_subjects)]
    print(f"过滤后剩余用于训练的数据量: {len(df)}")

    if len(df) == 0:
        print("[WARN] 过滤后没有足够的数据进行训练。")
        return
    # -------------------------------

    # 3. 划分训练集和测试集
    X = df['cut_text']
    y = df['subject']

    # 这里加个 stratify=y 保证测试集里各种类别的比例和训练集一致
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("3. 开始训练模型（使用互补朴素贝叶斯处理不平衡数据）...")
    # TfidfVectorizer -> ComplementNB (专治数据不平衡)
    model = make_pipeline(TfidfVectorizer(), ComplementNB())
    model.fit(X_train, y_train)

    # 4. 评估模型
    print("4. 评估结果：")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))

    # 5. 保存模型
    joblib.dump(model, 'subject_classifier.pkl')
    print("[OK] 模型已保存为 subject_classifier.pkl")

    # 6. 简单测试
    test_title = "张宇带你刷线代矩阵的秩"
    processed = clean_text(test_title)
    prediction = model.predict([processed])[0]
    print(f"\n测试预测: '{test_title}' -> 【{prediction}】")


if __name__ == "__main__":
    train()
