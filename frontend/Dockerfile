# Build from the repository root: docker build -f frontend/Dockerfile .
# vite.config.ts reads data/corpus.json and src/lib/definitions.ts imports
# definitions/definitions.yaml, both from the repo root.
FROM node:24-slim

RUN npm install --global pnpm@12.11.2

WORKDIR /app/frontend

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
COPY data/corpus.json /app/data/corpus.json
COPY definitions/ /app/definitions/

# Public values only. They are baked into the static bundle.
ARG VITE_API_BASE
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
RUN pnpm build

CMD ["sh", "-c", "exec pnpm exec vite preview --host 0.0.0.0 --port ${PORT:-4173} --strictPort"]
