# Chainos Terminal — Next.js + R3F. Build context: repo root (needs the workspace).
FROM node:18-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /app

FROM base AS build
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @chainos/terminal build

FROM base AS run
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
# Standalone server bundle + static assets (outputFileTracingRoot = repo root).
COPY --from=build /app/apps/terminal/.next/standalone ./
COPY --from=build /app/apps/terminal/.next/static ./apps/terminal/.next/static
EXPOSE 3000
CMD ["node", "apps/terminal/server.js"]
