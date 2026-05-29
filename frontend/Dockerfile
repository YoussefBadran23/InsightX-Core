# ── Frontend Dockerfile ─────────────────────────────────────────────────────
# Using node:20-alpine for a lean Linux-native environment.
# IMPORTANT: node_modules are installed INSIDE the image layer and kept
# isolated from the host volume mount using an anonymous volume trick in
# docker-compose.yml (`/app/node_modules`). This prevents Windows/macOS
# node_modules (with platform-specific SWC binaries) from overwriting the
# Linux-native ones installed here.
FROM node:20-alpine

# Install libc compat layer — required by some SWC/sharp native binaries on Alpine
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy manifests first so this layer is cached unless deps change
COPY package.json package-lock.json ./

# Install Linux-native dependencies.
RUN npm install

# Copy application source AFTER npm install (avoids cache busting on source changes)
COPY . .

# Disable Next.js telemetry in the container
ENV NEXT_TELEMETRY_DISABLED=1

# Tell Next.js NOT to attempt lockfile patching at runtime.
ENV NEXT_IGNORE_INCORRECT_LOCKFILE=1

# ── Build-time public API URL ─────────────────────────────────────────────────
# NEXT_PUBLIC_* vars are baked into the JS bundle at build time — they CANNOT
# be injected at container start. Pass the real backend URL via docker-compose
# build.args (prod) or leave blank for local dev (hot-reload skips this build).
# Example:
#   docker compose -f docker-compose.prod.yml build \
#     --build-arg NEXT_PUBLIC_API_URL=https://api.yourdomain.com
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Build the production bundle so `npm start` (next start) works.
# In dev docker-compose the command is overridden to `npm run dev`, so the
# dev server runs from source and this built output is never used for dev.
RUN npm run build

# Expose port
EXPOSE 3000

# Production default — dev docker-compose overrides this to `npm run dev`
CMD ["npm", "start"]
