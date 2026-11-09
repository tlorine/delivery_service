# Cafe admin panel (Nuxt SPA served by Nitro with the /v1 pass-through). Build: docker build -f docker/admin/Dockerfile .
FROM node:24-alpine AS base

FROM base AS builder
WORKDIR /app
ENV NODE_OPTIONS=--max-old-space-size=6144
COPY . .
RUN corepack enable pnpm \
    && pnpm install --frozen-lockfile --filter "@delivery/admin..." \
    && pnpm --filter @delivery/admin run build

FROM base AS production
RUN apk add --no-cache curl
WORKDIR /app
COPY --from=builder /app/apps/admin/.output .
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

ARG VERSION=dev
LABEL description="Cafe admin panel" version=${VERSION}
# NUXT_API_INTERNAL_URL: backend address, e.g. http://api:8000
ENV VERSION=${VERSION} NODE_ENV=production PORT=3000 HOST=0.0.0.0
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD ["curl", "-f", "http://localhost:3000/login"]
ENTRYPOINT ["node"]
CMD ["/app/server/index.mjs"]
