# Build context is the repository root (see docker-compose.yml).
FROM node:20-slim AS build
WORKDIR /app
COPY services/web/package.json ./
# Serialize downloads: on VPN / constrained networks npm's parallel tarball fetches stall
# (single downloads work, the parallel batch hangs). maxsockets=1 fixes it (~3 min install).
# On a fast network build with --build-arg NPM_MAXSOCKETS=15 for full parallelism.
ARG NPM_MAXSOCKETS=1
ENV npm_config_maxsockets=${NPM_MAXSOCKETS} \
    npm_config_fetch_timeout=60000 \
    npm_config_fetch_retries=5 \
    npm_config_fetch_retry_mintimeout=2000 \
    npm_config_fetch_retry_maxtimeout=60000
RUN npm install --no-audit --no-fund
COPY services/web/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY services/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
