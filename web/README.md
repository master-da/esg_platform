# Web app

Next.js 16 (App Router) front end for the ESG / carbon accounting platform. See the
[root README](../README.md) for setup, architecture and commands.

```bash
npm install
npm run dev        # http://localhost:3000 (needs local Supabase and the engine)
npx tsc --noEmit   # type-check
npm run lint
npx playwright test  # golden-path E2E; cleans up its own projects afterwards
```

`src/proxy.ts` refreshes the Supabase session. Pages read customer data through Supabase (RLS) and
send every action that leads to a number (uploads, categorization, calculations, exports) to the engine.
