# Deploying Sentinel to Azure

Two container images — the FastAPI agent (`Dockerfile.fastapi`) and the Next.js
frontend (`frontend/Dockerfile`) — run as two web services. The frontend is the
only public surface; it proxies to the backend server-side, injecting
`X-API-Key`, so the key never reaches the browser.

There are two deploy paths in this repo. **Which one you can use depends on your
subscription's registered resource providers**, not on preference.

---

## Path A — App Service for Containers (what's deployed today)

**Use this when `Microsoft.App` (Azure Container Apps) is not registered** and
your account can't register it — which is the case in the NWD enterprise
subscription. App Service (`Microsoft.Web`) is already registered and in use
there, so this path works with a plain Contributor role.

```bash
az login
# Populate .env (backend, 15 vars) and frontend/.env.local (4 vars) first.
bash scripts/deploy_appservice.sh
```

The script (idempotent — safe to re-run for redeploys):

1. builds both images **remotely in ACR** (`az acr build`, no local Docker),
2. creates/updates two Web Apps on an existing Linux plan,
3. pushes every secret as an app setting (read from the gitignored env files),
4. waits for health and you can then smoke-test the public URL.

**Live resources** (resource group `NWD-GroupFinance`, region East Asia):

| Resource | Name | Notes |
|---|---|---|
| Frontend Web App | `sentinel-cre-web` | **public** — this is the URL |
| Backend Web App | `sentinel-cre-api` | public host, but **X-API-Key gated** |
| Container Registry | `azcr3iywdkfu3u75q` | holds both images |
| App Service Plan | `nwic-ai-service-plan` | existing Linux B3 (shared) |

URL: `https://sentinel-cre-web.azurewebsites.net`

### Operational notes / gotchas

- **`WEBSITES_PORT`** must match each container's listen port (backend `8000`,
  frontend `3000`), or App Service health-checks the wrong port and returns 503.
- **Image path doubling:** set the image with `az webapp config container set`
  using the *bare* `registry/repo:tag`. If you instead pass an image name that
  already includes the registry *and* a `--container-registry-url`, App Service
  concatenates them into `…azurecr.io/…azurecr.io/…` and the pull fails with
  `ImagePullUnauthorizedFailure`. The script uses the safe form.
- **Backend reachability:** App Service has no private app-to-app network, so
  the frontend's `FASTAPI_URL` is the backend's *public* HTTPS URL. The shared
  `API_KEY` (identical on both apps) is what protects it. If you need the
  backend fully private, use Path B or add VNet integration + private endpoints.

### Redeploying

The deploy is two independent steps: **build** an image in ACR, then point a
Web App at it (a restart re-pulls the `:latest` tag). Pick the smallest scope
that covers your change.

**Full redeploy (both services + secrets).** Re-run the script — it is
idempotent and the safest default after a wide change or an env-file edit:

```bash
bash scripts/deploy_appservice.sh
```

**Single service (most common).** A change to only the frontend or only the
backend doesn't need the other image rebuilt or secrets re-pushed. Build that
one image, then restart that one app so it pulls the new `:latest`:

```bash
# Frontend only (e.g. a UI change):
az acr build -r azcr3iywdkfu3u75q -t sentinel-web:latest -f frontend/Dockerfile frontend
az webapp restart -g NWD-GroupFinance -n sentinel-cre-web

# Backend only (e.g. an agent/tool change):
az acr build -r azcr3iywdkfu3u75q -t sentinel-api:latest -f Dockerfile.fastapi .
az webapp restart -g NWD-GroupFinance -n sentinel-cre-api
```

`az acr build` runs the Docker build **remotely in ACR** — no local Docker
daemon needed. It typically takes ~2–3 min and prints the new image digest and
a `Run ID … was successful` line on completion.

**Secrets only (no code change).** When you've only rotated a key or changed an
env value, push just the app settings — no rebuild. Either re-run the full
script, or set the one value directly (it restarts the app automatically):

```bash
az webapp config appsettings set -g NWD-GroupFinance -n sentinel-cre-api \
  --settings TAVILY_API_KEY="$(grep -E '^TAVILY_API_KEY=' .env | cut -d= -f2-)"
```

### Verifying a deploy

```bash
# Health (backend returns JSON; frontend /login returns 200 HTML):
curl -s https://sentinel-cre-api.azurewebsites.net/market_agent/health
curl -s -o /dev/null -w '%{http_code}\n' https://sentinel-cre-web.azurewebsites.net/login

# Confirm a static asset shipped (e.g. the favicon after a frontend deploy):
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' \
  https://sentinel-cre-web.azurewebsites.net/icon.svg
```

A container restart takes ~30–90 s to pull the image and pass App Service's
health check; poll `/login` (frontend) or `/market_agent/health` (backend)
until it returns 200 before declaring success. Browsers cache favicons
aggressively — hard-refresh to see an updated `icon.svg`.

### Inspecting & debugging

```bash
# Live log stream (Ctrl-C to stop) — the fastest way to see a 503's cause:
az webapp log tail -g NWD-GroupFinance -n sentinel-cre-web

# What image/tag a Web App is currently running:
az webapp config container show -g NWD-GroupFinance -n sentinel-cre-web -o table

# Current app settings (KEYS only — values are secret; this lists names):
az webapp config appsettings list -g NWD-GroupFinance -n sentinel-cre-api \
  --query "[].name" -o tsv

# Recent ACR builds (find a failed build's Run ID, then stream its log):
az acr task list-runs -r azcr3iywdkfu3u75q -o table
az acr task logs -r azcr3iywdkfu3u75q --run-id <RUN_ID>
```

> If a restart serves *stale* content, the image didn't actually change: confirm
> `az acr build` printed a **new digest**. App Service pulls `:latest` by digest
> on restart, so a successful rebuild + restart is sufficient — there is no
> separate cache to bust.

---

## Path B — Azure Container Apps (preferred, but blocked here)

This is the cleaner architecture: the backend gets **internal-only** ingress
(never publicly reachable), scale-to-zero, and image pull via a user-assigned
managed identity instead of registry admin creds. The IaC is written and
compiles (`infra/main.bicep`, `infra/main.parameters.json`, `azure.yaml`):

```bash
azd up        # provision + build + deploy, all from the Bicep
```

**Why it isn't used in the NWD subscription:** `azd up` fails at the Container
Apps Environment with
`MissingSubscriptionRegistration: namespace 'Microsoft.App'`, and the deploying
account lacks `Microsoft.App/register/action`. Once a subscription Owner runs:

```bash
az provider register --namespace Microsoft.App
```

…this path provisions cleanly with no other change. Kept in the repo so the
better architecture is one admin action away.

> The Bicep also assigns the `AcrPull` role to a managed identity. The NWD
> account is additionally blocked from creating role assignments (Conditional
> Access on Microsoft Graph), which is the second reason Path A uses ACR admin
> creds. A subscription with normal Owner/Contributor + RBAC rights won't hit
> either wall.

---

## Secrets

Nineteen settings total, none committed:

- **Backend (15)** from `.env`: `OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`,
  `DEPLOYMENT_NAME_GPT54`, `DEPLOYMENT_NAME_GPT54M`, `IMAGE_DEPLOYMENT_NAME`,
  `API_KEY`, `COSMOS_URL`, `COSMOS_KEY`, `AGENT_COSMOS_URL`, `AGENT_COSMOS_KEY`,
  `BLOB_CONNECTION_STRING`, `QDRANT_URL`, `QDRANT_API_KEY`, `JINA_API_KEY`,
  `TAVILY_API_KEY`.
- **Frontend (4)** from `frontend/.env.local`: `API_KEY` (must equal the
  backend's), `COOKIE_SECRET`, `AUTH_USERNAME`, `AUTH_PASSWORD`.

`FASTAPI_URL` (frontend) and `API_SERVER` (backend) are set by the deploy to the
backend's URL — not secrets.

## Teardown

```bash
# Path A — remove just the two apps (leaves the shared plan + registry):
az webapp delete -g NWD-GroupFinance -n sentinel-cre-web
az webapp delete -g NWD-GroupFinance -n sentinel-cre-api
# Path B:
azd down
```
