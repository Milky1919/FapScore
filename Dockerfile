# ベースイメージとして公式のPython 3.11スリム版を選択
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピーして、先にインストールする
# これにより、ソースコードの変更時に毎回再インストールするのを防ぐ
COPY requirements.txt .

# pipをアップグレードし、依存関係をインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ソースコードをコンテナにコピー
COPY ./src ./src

# ボットの起動コマンド
# python -u: 標準出力/エラーのバッファリングを無効にし、ログがリアルタイムで表示されるようにする
CMD ["python", "-u", "src/main.py"]
