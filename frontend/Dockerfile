FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error

COPY tsconfig.json tsconfig.node.json vite.config.ts ./
COPY postcss.config.js tailwind.config.js ./
COPY index.html ./
COPY public ./public
COPY src ./src

RUN npm run build
