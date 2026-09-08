FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
ENV NEXT_TELEMETRY_DISABLED=1
ENV PNPM_CONFIG_DANGEROUSLY_ALLOW_ALL_BUILDS=true

RUN corepack enable

WORKDIR /app

ARG INNGEST_URL=http://lang3s_inngest:8288
ARG INNGEST_SIGNING_KEY=A1B2C3
ARG REDIS_HOST=lang3s_redis
ARG REDIS_PORT=6379
ARG REDIS_DB=0
ARG ADMIN_PASSPHRASE=build-time-admin-passphrase
ARG SYSTEM_KEY=build-time-system-key
ARG BETTER_AUTH_SECRET=V7n4qK9zR2mP8xL5cT1wH6yD3sF0aJ4uN9eB2gQ7rM1kC8vX5pL3tH6yR0dW2nZ
ARG BETTER_AUTH_URL=http://localhost:3000
ARG DATABASE_URL=/frontend_data/users.db
ARG FILESTORE_ROOT=/filestore
ARG NEXT_PUBLIC_APP_URL=http://localhost:3000
ARG NEXT_PUBLIC_BACKEND_URL=http://lang3s_caddy:8003

ENV INNGEST_URL=$INNGEST_URL \
    INNGEST_SIGNING_KEY=$INNGEST_SIGNING_KEY \
    REDIS_HOST=$REDIS_HOST \
    REDIS_PORT=$REDIS_PORT \
    REDIS_DB=$REDIS_DB \
    ADMIN_PASSPHRASE=$ADMIN_PASSPHRASE \
    SYSTEM_KEY=$SYSTEM_KEY \
    BETTER_AUTH_SECRET=$BETTER_AUTH_SECRET \
    BETTER_AUTH_URL=$BETTER_AUTH_URL \
    DATABASE_URL=$DATABASE_URL \
    FILESTORE_ROOT=$FILESTORE_ROOT \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --no-frozen-lockfile

COPY . ./
RUN mkdir -p /frontend_data \
    && pnpm auth:bootstrap-db \
    && pnpm build

EXPOSE 3000

CMD ["pnpm", "start", "-p", "3000"]
