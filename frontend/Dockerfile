# ── Frontend Dockerfile ─────────────────────────────────────────────────────
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Install dependencies first (layer cache)
COPY package*.json ./
RUN npm install

# Copy application source
COPY . .

# Expose dev server port
EXPOSE 3000

# Start Next.js dev server with hot-reload
CMD ["npm", "run", "dev"]
