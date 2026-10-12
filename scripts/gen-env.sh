#!/usr/bin/env bash
# Generate engine/.env and web/.env.local from the running local Supabase stack.
# Local-development keys only. Never commit the generated files.
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(supabase status -o env | sed -E 's/^([A-Z_]+)=/SB_\1=/')"

# Keep any manually-added ANTHROPIC_API_KEY across regenerations.
ANTHROPIC_API_KEY_LINE=$(grep -E '^ANTHROPIC_API_KEY=' engine/.env 2>/dev/null || true)

cat > engine/.env <<ENV
SUPABASE_URL=${SB_API_URL}
SUPABASE_SECRET_KEY=${SB_SECRET_KEY}
SUPABASE_PUBLISHABLE_KEY=${SB_PUBLISHABLE_KEY}
SUPABASE_JWT_SECRET=${SB_JWT_SECRET}
DATABASE_URL=postgresql://engine_app:engine_app_local_only@127.0.0.1:54322/postgres
WEB_URL=http://localhost:3000
AI_PROVIDER=anthropic
AI_MODEL=claude-opus-5-5
${ANTHROPIC_API_KEY_LINE}
ENV

cat > web/.env.local <<ENV
NEXT_PUBLIC_SUPABASE_URL=${SB_API_URL}
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${SB_PUBLISHABLE_KEY}
NEXT_PUBLIC_ENGINE_URL=http://localhost:8000
ENV
echo "wrote engine/.env and web/.env.local"
