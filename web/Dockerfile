# -------- deps --------
FROM node:20-bullseye AS deps
WORKDIR /app

ENV NEXT_DISABLE_ESLINT=1
ENV NEXT_TELEMETRY_DISABLED=1

# Si usás package-docker.json, mantenelo. Si no, renombralo a package.json y listo.
COPY package-docker.json ./package.json
COPY package-lock.json ./package-lock.json

# ⚠️ Usamos npm install (tolerante con lock desincronizado)
#   Tip: podés sumar --legacy-peer-deps si hiciera falta.
RUN npm install --no-audit --no-fund

# -------- builder --------
FROM node:20-bullseye AS builder
WORKDIR /app

ENV NEXT_DISABLE_ESLINT=1
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

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
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/public ./public

EXPOSE 3000
# bind explícito a 0.0.0.0
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000", "-H", "0.0.0.0"]
