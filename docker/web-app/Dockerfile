# Storefront (Nuxt SSR). Build: docker build -f docker/web-app/Dockerfile .
FROM node:24-alpine AS base

FROM base AS builder
WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=6144
# Whole workspace (see .dockerignore): pnpm resolves workspace packages from the lockfile.
COPY . .
RUN corepack enable pnpm \
    && pnpm install --frozen-lockfile --filter "@nextorders/web-app..." \
    && pnpm --filter @nextorders/web-app run build

FROM base AS production
RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/apps/web-app/.output .
COPY docker/web-app/health-check.sh ./
RUN addgroup -S appgroup && adduser -S appuser -G appgroup && chmod +x ./health-check.sh
USER appuser

ARG VERSION=dev
LABEL description="Storefront: web and Telegram Mini App" version=${VERSION}
# NUXT_API_INTERNAL_URL: backend address for SSR, e.g. http://api:8000
ENV VERSION=${VERSION} NODE_ENV=production PORT=3000 HOST=0.0.0.0
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD ["/app/health-check.sh"]
ENTRYPOINT ["node"]
CMD ["/app/server/index.mjs"]
