FROM python:3.10-slim

WORKDIR /app

# 安裝系統依賴 (如果有需要編譯的套件)
RUN apt-get update && apt-get install -y gcc

# 複製並安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 暴露端口
EXPOSE 8000