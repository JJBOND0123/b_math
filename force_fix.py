import requests
import os

# 定义文件路径
js_dir = "static/js"
os.makedirs(js_dir, exist_ok=True)

# ✅ 使用阿里云 NPM 镜像源 (国内速度最快、最稳)
# ECharts 5.4.3 + WordCloud 2.1.0 是绝配
files = {
    "echarts.min.js": "https://registry.npmmirror.com/echarts/5.4.3/files/dist/echarts.min.js",
    "echarts-wordcloud.min.js": "https://registry.npmmirror.com/echarts-wordcloud/2.1.0/files/dist/echarts-wordcloud.min.js"
}

print("🚀 开始从阿里云镜像强制修复文件...")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

for filename, url in files.items():
    save_path = os.path.join(js_dir, filename)
    print(f"\n正在下载: {filename} ...")

    try:
        # 1. 下载
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()  # 检查是否 404/500 报错

        content = resp.content

        # 2. 关键检查：确保下载的不是 HTML 报错页
        if b"<!DOCTYPE html>" in content or len(content) < 1000:
            print(f"   ❌ 错误：下载到了网页而非代码，请检查网络！")
            continue

        # 3. 写入文件
        with open(save_path, "wb") as f:
            f.write(content)

        # 4. 显示文件大小
        kb_size = len(content) / 1024
        print(f"   ✅ 成功！文件大小: {kb_size:.2f} KB")

    except Exception as e:
        print(f"   ❌ 下载异常: {e}")

print("\n✨ 修复完成！请务必去浏览器按 Ctrl + F5 强制刷新！")