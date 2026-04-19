FROM node:20-alpine

WORKDIR /app

# 複製 package.json
COPY package.json package-lock.json* ./

# 安裝依賴
RUN npm install

# 複製程式碼
COPY . .

# 暴露端口
EXPOSE 3000