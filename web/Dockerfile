# ----- Deps -----
FROM node:20-bullseye AS deps
WORKDIR /app
# Use Docker-compatible package.json with Tailwind v3
COPY package-docker.json ./package.json
COPY package-lock.json ./package-lock.json
RUN rm -rf package-lock.json && npm install

# ----- Builder -----
FROM node:20-bullseye AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Use Docker-compatible configs
COPY tailwind-docker.config.js ./tailwind.config.js
COPY postcss-docker.config.js ./postcss.config.js
COPY package-docker.json ./package.json
# Use Docker-compatible CSS (Tailwind v3 syntax)
COPY src/app/globals-docker.css ./src/app/globals.css
ENV NEXT_TELEMETRY_DISABLED=1
# Evitamos invocar el script para que nadie meta --turbopack sin querer
RUN node node_modules/next/dist/bin/next build

# ----- Runner -----
FROM node:20-bullseye AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Solo lo necesario para runtime
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "start", "-p", "3000"]
