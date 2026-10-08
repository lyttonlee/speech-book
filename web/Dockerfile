# ============================================================
# 前端镜像：多阶段构建（node 编译 → nginx 静态服务）
# 构建上下文：web/（必须在 web/ 目录下执行 docker build ..）
# ============================================================

# ------------------------------------------------------------ 阶段 1：编译
FROM node:22-alpine AS build

WORKDIR /app

# pnpm 全局安装（比 corepack 少一层不确定性，锁文件版本已固定）
RUN npm install -g pnpm

# 先复制依赖清单安装，再复制源码：源码改动不触发重装依赖
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src

# 产物在 dist/，交给下面的 nginx 提供
RUN pnpm run build

# ------------------------------------------------------------ 阶段 2：运行
FROM nginx:alpine AS web

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# 前台常驻，docker stop 才能正常停掉容器
CMD ["nginx", "-g", "daemon off;"]
