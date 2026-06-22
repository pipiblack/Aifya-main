FROM node:22-alpine@sha256:9385cd9f3001dfc3431e8ead12c43e9e1f87cc1b9b5c6cfd0f73865d405b27c4 AS base
ENV npm_config_fetch_timeout=600000 \
    npm_config_fetch_retries=10 \
    npm_config_network_timeout=600000
RUN corepack enable

FROM base AS deps
WORKDIR /app
# Copy root workspace files
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
# Copy package.json of workspaces to install dependencies
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared/package.json ./packages/shared/package.json
RUN pnpm config set fetch-timeout 600000 \
  && pnpm config set fetch-retries 10 \
  && pnpm install --ignore-scripts --prefer-offline

FROM base AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_KNOWLEDGE_API_URL=http://localhost:8025/api/v1
ARG NEXT_PUBLIC_SCRIBE_API_URL=http://localhost:8005
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
ARG NEXT_PUBLIC_DEFAULT_LICENSE_TIER=professional
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_KNOWLEDGE_API_URL=$NEXT_PUBLIC_KNOWLEDGE_API_URL \
    NEXT_PUBLIC_SCRIBE_API_URL=$NEXT_PUBLIC_SCRIBE_API_URL \
    NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL \
    NEXT_PUBLIC_DEFAULT_LICENSE_TIER=$NEXT_PUBLIC_DEFAULT_LICENSE_TIER
COPY --from=deps /app /app
COPY . .

WORKDIR /app/apps/web
# Securely handle monorepo configuration fallback files if missing in context
RUN if [ ! -f tsconfig.base.json ]; then echo '{}' > tsconfig.base.json; fi
RUN pnpm build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Set correct paths for Next.js standalone monorepo output
COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
CMD ["node", "apps/web/server.js"]
