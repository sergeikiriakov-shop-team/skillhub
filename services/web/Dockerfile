# Build context is the repository root (see docker-compose.yml).
FROM node:20-slim AS build
WORKDIR /app
COPY services/web/package.json ./
# fetch timeouts/retries so a stalled socket fails fast instead of hanging forever on flaky
# or VPN networks. If installs still hang, it is an MTU black hole — see README → Troubleshooting.
ENV npm_config_fetch_timeout=60000 \
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
