# Workdoe

Workdoe is a local-first contractor lead board prototype for the DMV area. Clients post simple jobs with photos, contractors search leads and send mini bids, and approved matches open private message threads.

## Local Stack

- Python + Flask for the web app
- Server-rendered HTML templates and CSS
- SQLite for local structured data
- Private local upload storage for job and contractor photos
- Vendored Leaflet 1.9.4 + OpenStreetMap tiles only for the embedded map view
- Leaflet's BSD 2-Clause license is retained at `workdoe/static/vendor/leaflet/LICENSE`
- Deer logo mark from Tabler Icons, an MIT-licensed open-source icon set

## Run Locally

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

## Demo Accounts

These are seeded for local testing only:

- Client: `client@workdoe.local` / `workdoe-client`
- Contractor: `contractor@workdoe.local` / `workdoe-contractor`
- Admin: `admin@workdoe.local` / `workdoe-admin`

New client and contractor accounts can also use `/start`, a local 1-2-3 email-code flow:

1. Choose whether to post a job or find work.
2. Enter email, name, and company/household.
3. Enter the local one-time code shown on screen.

The homepage, `/login`, and `/start` screens show the live open-job map/list so users can see current leads before creating or opening an account. These entry screens support category, search, and sort controls. Public map pins refresh from `/api/jobs/open`, which returns only approximate city/ZIP-level coordinates and lead metadata.

## Optional Turnstile

Set `WORKDOE_TURNSTILE_SITE_KEY` and `WORKDOE_TURNSTILE_SECRET_KEY` to enable Cloudflare Turnstile on account start, login, job posting, mini-bid, and report forms. Without both keys, the local prototype stays widget-free.

## Production Mode

Set `WORKDOE_ENV=production` for Cloudflare deployment. Production mode requires a real `WORKDOE_SECRET_KEY`, secure cookies, disabled demo seeding, and Turnstile keys before the app starts.
Set `WORKDOE_AUTH_PROVIDER=clerk` only when Clerk is configured; Clerk mode also requires `CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk`, `CLERK_PROXY_URL=https://workdoe.com/__clerk`, `CLERK_FAPI=https://frontend-api.clerk.dev`, `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET`, and `CLERK_JWT_KEY`.
When Clerk mode is active, `/login` and `/start` mount Clerk's in-page email-code component on Workdoe pages and keep the local one-time-code form as the local fallback. The Cloudflare Worker proxies `/__clerk/*` so login API traffic also stays on `workdoe.com`. Production deploy checks require a non-secret `clerk-proxy-proof.local.json` confirming Clerk Domains uses `https://workdoe.com/__clerk`.

## Test

```powershell
python -m unittest discover -s tests
```

## Data Separation

- Auth data lives in `users` and `password_reset_tokens`.
- Profile data lives in `client_profiles` and `contractor_profiles`.
- Marketplace data lives in `jobs`, `match_requests`, `threads`, and `messages`; approved-match message permissions are mirrored in the Cloudflare Worker.
- Media metadata lives in `job_photos` and `contractor_photos`.
- Uploaded files are stored under the Flask `instance/` folder and served only through permission-checked routes.
- Moderation data lives in `reports` and `moderation_actions`.

## Cloudflare Migration

See [docs/cloudflare-migration.md](docs/cloudflare-migration.md).
See [docs/cloudflare-automation-auth.md](docs/cloudflare-automation-auth.md) for the same-domain Clerk email-code login plan and Cloudflare automation targets.

Refresh Cloudflare handoff artifacts with:

```powershell
python scripts\prepare_cloudflare_release.py
```

This also writes `cloudflare/wrangler.jsonc` and `cloudflare/.dev.vars.example`.
If `cloudflare/wrangler.jsonc` already has real D1 IDs, release prep preserves them.
The first Cloudflare Worker scaffold is in `cloudflare/worker/entry.py` for health
checks, cron automation, queue consumers, Clerk session/webhook intake, the `/__clerk`
same-origin Clerk Frontend API proxy, the public
jobs map API, the same-domain `/`, `/login`, and `/start` Clerk entry shell, authenticated post-login app shells for dashboard/lead/post-job-with-photos/client-bid-review/job-photo-upload/contractor-profile/message/admin routes, signed-in job detail API with contractor ZIP redaction, contractor profile updates, privacy-safe public contractor profile pages and APIs, contractor lead board data, contractor mini-bid dashboard data, client job dashboard data, client mini-bid review data, client job creation with Turnstile and private photo upload, client close/reopen controls, contractor mini-bid requests
with duplicate checks, client bid approval/rejection with private thread
creation, approved-match message APIs, signed-in moderation report intake, admin
moderation actions, and private R2 media upload/serving routes.

Check the local Cloudflare handoff without deploying:

```powershell
python scripts\cloudflare_preflight.py
```

Check the local deploy-readiness shape:

```powershell
python scripts\cloudflare_readiness.py
```

Print the safe Cloudflare operator plan without running deployment commands:

```powershell
python scripts\cloudflare_launch_plan.py
```

Print the current Cloudflare launch status and next command without running Wrangler:

```powershell
python scripts\cloudflare_launch_status.py
```

Summarize local prototype and Cloudflare launch readiness, or add `--live`
GitHub/DNS checks in one place:

```powershell
npm run launch:doctor
npm run launch:doctor:live
```

Both doctor commands print a `Next Actions` section. The live version adds
GitHub deployment-secret, Wrangler authentication, and DNS checks; all
secret-setting commands use secure interactive prompts and do not print secret
values. Its DNS phase uses the same delegated-nameserver, apex, `www`, and
Wrangler custom-domain checks as `npm run launch:dns`, so partial Cloudflare
setup states are called out directly.

Live Cloudflare steps require the Wrangler CLI on PATH and an authenticated
Cloudflare session. Use a global install, a local `node_modules/.bin` install, or
set `WORKDOE_WRANGLER_BIN` to the Wrangler executable path:

```powershell
npm install
.\\node_modules\\.bin\\wrangler.cmd login
```

Workdoe also includes npm shortcuts for the Cloudflare launch gates, following
the same checked-release pattern used by the PTOwl and NuTs projects:

```powershell
npm run cf:status
npm run cf:resources:plan
npm run cf:resources:apply
npm run cf:secrets:evidence
npm run cf:clerk:proof
npm run cf:deploy:plan
npm run cf:deploy
npm run github:deploy:plan
npm run github:deploy
npm run launch:handoff
npm run launch:handoff:write
npm run launch:dns
npm run launch:dns:strict
npm run launch:smoke
npm run launch:smoke:strict
```

GitHub Actions is wired through `.github/workflows/cloudflare-deploy.yml`.
Pushes to `main` or `master` run tests and preflight only. Production deployment
is manual-only through the `Workdoe Cloudflare Release` workflow and requires:

- repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`;
- workflow dispatch from the `main` branch;
- dispatch input `DEPLOY`;
- Clerk proxy confirmation `https://workdoe.com/__clerk`;
- real D1 IDs committed in `cloudflare/wrangler.jsonc`;
- required Worker secrets already set in Cloudflare.

Set the two GitHub deployment secrets with interactive prompts:

```powershell
gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe
gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe
```

Check the GitHub production environment and deploy-secret names without reading
secret values:

```powershell
npm run github:release:status
```

Preview the final GitHub workflow dispatch without launching, then dispatch it
only after the live launch doctor is ready:

```powershell
npm run github:deploy:plan
npm run github:deploy
```

Generate a redacted launch handoff checklist from the same live gates:

```powershell
npm run launch:handoff
npm run launch:handoff:write
```

The write command saves `docs/workdoe-launch-handoff.local.md`, which is ignored
because it contains live local status and machine paths. The generated checklist
groups both blockers and remaining actions into GitHub secrets, Cloudflare
resources, Worker secrets/Clerk, DNS activation, and final deploy/smoke checks.

Diagnose DNS delegation, apex/www resolution, and checked-in Worker custom
domains before deployment:

```powershell
npm run launch:dns
npm run launch:dns:strict
```

After DNS and deployment, run production smoke checks for `workdoe.com`:

```powershell
npm run launch:smoke
npm run launch:smoke:strict
```

Set each required Worker secret in Cloudflare with Wrangler's secure prompt:

```powershell
.\\node_modules\\.bin\\wrangler.cmd secret put CLERK_JWT_KEY --config cloudflare\\wrangler.jsonc
.\\node_modules\\.bin\\wrangler.cmd secret put CLERK_PUBLISHABLE_KEY --config cloudflare\\wrangler.jsonc
.\\node_modules\\.bin\\wrangler.cmd secret put CLERK_SECRET_KEY --config cloudflare\\wrangler.jsonc
.\\node_modules\\.bin\\wrangler.cmd secret put CLERK_WEBHOOK_SECRET --config cloudflare\\wrangler.jsonc
.\\node_modules\\.bin\\wrangler.cmd secret put WORKDOE_SECRET_KEY --config cloudflare\\wrangler.jsonc
.\\node_modules\\.bin\\wrangler.cmd secret put WORKDOE_TURNSTILE_SECRET_KEY --config cloudflare\\wrangler.jsonc
.\\node_modules\\.bin\\wrangler.cmd secret put WORKDOE_TURNSTILE_SITE_KEY --config cloudflare\\wrangler.jsonc
```

Before a real `workdoe.com` launch, run strict mode after replacing placeholder
Cloudflare resource IDs, exporting the non-secret Cloudflare secret-name list,
and confirming Clerk's Domains page uses the Workdoe same-domain proxy:

```powershell
python scripts\cloudflare_launch_status.py
python scripts\cloudflare_resource_bootstrap.py --json --no-secret-probe
python scripts\cloudflare_resource_bootstrap.py --execute --yes --no-secret-probe
cd cloudflare
python ..\scripts\cloudflare_secret_evidence.py --execute --yes --output ..\cloudflare-secret-list.local.json
cd ..
python scripts\cloudflare_clerk_proxy_proof.py --confirm
python scripts\cloudflare_release_evidence.py --json
python scripts\cloudflare_readiness.py --strict-production --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
python scripts\cloudflare_production_deploy.py --json --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
python scripts\github_deploy_dispatch.py
python scripts\github_deploy_dispatch.py --execute --yes
```
