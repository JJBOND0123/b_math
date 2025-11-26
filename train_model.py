"""文本分类模型训练脚本：基于数据库中的视频标题/标签，训练科目分类器。"""

import jieba
import joblib
import pandas as pd
from sqlalchemy import create_engine
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import make_pipeline

# 数据库配置（固定值）
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "db": "bilibili_math_db",
    "charset": "utf8mb4"
}


def build_db_url() -> str:
    """拼接 MySQL 连接串。"""
    return f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['db']}?charset={DB_CONFIG['charset']}"


def get_training_data() -> pd.DataFrame:
    """从数据库读取标注好的 subject，过滤“其他”与 NULL。"""
    engine = create_engine(build_db_url())
    sql = "SELECT title, tags, subject FROM videos WHERE subject != '其他' AND subject IS NOT NULL"
    return pd.read_sql(sql, engine)


def clean_text(text: str) -> str:
    """jieba 分词 + 去停用词/单字，供 TF-IDF 输入。"""
    if not isinstance(text, str):
        return ""
    words = jieba.cut(text)
    return " ".join([w for w in words if len(w) > 1])


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

    # 2. 中文分词，合并标题 + 标签
    print("2. 正在进行中文分词...")
    df['text'] = df['title'] + " " + df['tags'].fillna('')
    df['cut_text'] = df['text'].apply(clean_text)

    # 3. 过滤样本极少的类别，避免模型偏斜
    subject_counts = df['subject'].value_counts()
    print("类别分布情况:\n", subject_counts)
    valid_subjects = subject_counts[subject_counts > 5].index
    df = df[df['subject'].isin(valid_subjects)]
    print(f"过滤后剩余用于训练的数据量: {len(df)}")
    if len(df) == 0:
        print("[WARN] 过滤后没有足够的数据进行训练。")
        return

    # 4. 划分训练集和测试集（stratify 保证比例一致）
    X = df['cut_text']
    y = df['subject']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # 5. 训练模型：TF-IDF + 互补朴素贝叶斯（对不平衡数据更稳）
    print("3. 开始训练模型...")
    model = make_pipeline(TfidfVectorizer(), ComplementNB())
    model.fit(X_train, y_train)

    # 6. 评估
    print("4. 评估结果:")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))

    # 7. 保存模型
    joblib.dump(model, 'subject_classifier.pkl')
    print("[OK] 模型已保存为 subject_classifier.pkl")

    # 8. 简单测试样例，方便答辩演示
    test_title = "张宇带你刷线代矩阵的本质"
    processed = clean_text(test_title)
    prediction = model.predict([processed])[0]
    print(f"\n测试预测: '{test_title}' -> 【{prediction}】")


if __name__ == "__main__":
    train()
