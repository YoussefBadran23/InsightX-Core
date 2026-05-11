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
# --ignore-scripts skips postinstall hooks that may fail in CI/Docker.
RUN npm install

# Copy application source AFTER npm ci (avoids cache busting on source changes)
COPY . .

# Disable Next.js telemetry in the container
ENV NEXT_TELEMETRY_DISABLED=1

# Tell Next.js NOT to attempt lockfile patching at runtime.
# The lockfile was generated on a different OS; patching is handled by
# the clean npm ci above, not at dev-server startup.
ENV NEXT_IGNORE_INCORRECT_LOCKFILE=1

# Expose dev server port
EXPOSE 3000

# Start Next.js dev server bound to all interfaces for Docker networking
CMD ["npm", "run", "dev"]
