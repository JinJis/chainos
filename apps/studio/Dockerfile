# Chainos Studio — Next.js admin. Build context: repo root (needs the workspace).
FROM node:18-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /app

FROM base AS build
COPY . .
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @chainos/studio build

FROM base AS run
ENV NODE_ENV=production \
    PORT=3001 \
    HOSTNAME=0.0.0.0
COPY --from=build /app/apps/studio/.next/standalone ./
COPY --from=build /app/apps/studio/.next/static ./apps/studio/.next/static
EXPOSE 3001
CMD ["node", "apps/studio/server.js"]
