# -------- deps --------
FROM node:20-bullseye AS deps
WORKDIR /app

# Evita que ESLint frene el build dentro del contenedor
ENV NEXT_DISABLE_ESLINT=1
ENV NEXT_TELEMETRY_DISABLED=1

# Copiamos solo lo mínimo para instalar deps
COPY package-docker.json ./package.json
COPY package-lock.json ./package-lock.json
# forzamos reinstall limpio
RUN rm -f package-lock.json && npm install

# -------- builder --------
FROM node:20-bullseye AS builder
WORKDIR /app

ENV NEXT_DISABLE_ESLINT=1
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .
# usar configs “docker-safe”
COPY tailwind-docker.config.js ./tailwind.config.js
COPY postcss-docker.config.js ./postcss.config.js
COPY src/app/globals-docker.css ./src/app/globals.css

# build
RUN node node_modules/next/dist/bin/next build

# -------- runner --------
FROM node:20-bullseye AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000"]
