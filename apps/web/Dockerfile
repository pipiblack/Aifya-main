FROM node:22-alpine AS base
RUN corepack enable

FROM base AS deps
WORKDIR /app
# Copy root workspace files
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml ./
# Copy package.json of workspaces to install dependencies
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared/package.json ./packages/shared/package.json
RUN pnpm install --no-frozen-lockfile --ignore-scripts --prefer-offline

FROM base AS builder
WORKDIR /app
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