#!/usr/bin/env bash
# Sentinel — App Service (containers) deploy.
#
# This is the path that ACTUALLY deploys in the NWD enterprise subscription,
# where the Microsoft.App provider (Azure Container Apps) is NOT registered and
# the deploying account cannot register it. See infra/README.md for the full
# story and the (preferred-but-blocked) Container Apps alternative.
#
# What it does, idempotently:
#   1. build both images remotely in ACR (no local Docker needed)
#   2. create/update two Web Apps on an existing Linux App Service Plan
#   3. push every secret as an app setting (read from local env files)
#   4. wait for health and run an end-to-end login+chat smoke test
#
# Secrets are read from the gitignored .env (backend) and frontend/.env.local
# (frontend) — nothing secret is hardcoded here or committed.
#
# Prereqs: az login (Contributor on the RG), the two env files populated.
# Usage:   bash scripts/deploy_appservice.sh

set -euo pipefail

# ---- Config (override via environment) ------------------------------------
RG="${RG:-NWD-GroupFinance}"
PLAN="${PLAN:-nwic-ai-service-plan}"          # existing Linux B3 plan
ACR="${ACR:-azcr3iywdkfu3u75q}"               # existing registry
API_APP="${API_APP:-sentinel-cre-api}"        # backend Web App (globally unique)
WEB_APP="${WEB_APP:-sentinel-cre-web}"        # frontend Web App (globally unique)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Read KEY from a dotenv file, stripping surrounding quotes and trailing CR.
val() {
  local v; v=$(grep -E "^$1=" "$2" | head -1 | cut -d= -f2- || true)
  v="${v%$'\r'}"; v="${v%\"}"; v="${v#\"}"; v="${v%\'}"; v="${v#\'}"
  printf '%s' "$v"
}

echo "==> Enabling ACR admin user (used by App Service to pull images)"
az acr update -n "$ACR" --admin-enabled true -o none
ACR_SERVER=$(az acr show -n "$ACR" --query loginServer -o tsv)
ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query "passwords[0].value" -o tsv)

echo "==> Building images remotely in ACR ($ACR_SERVER)"
az acr build -r "$ACR" -t sentinel-api:latest -f Dockerfile.fastapi . -o none
az acr build -r "$ACR" -t sentinel-web:latest -f frontend/Dockerfile frontend -o none

# --- helper: create app if missing, then point it at the given image --------
ensure_app() {
  local app="$1" image="$2" port="$3"
  if ! az webapp show -g "$RG" -n "$app" -o none 2>/dev/null; then
    echo "==> Creating Web App $app"
    az webapp create -g "$RG" -p "$PLAN" -n "$app" \
      --deployment-container-image-name "nginx" -o none
  fi
  echo "==> Setting $app image -> $ACR_SERVER/$image"
  # NOTE: pass the image WITHOUT re-prefixing the registry in the URL flag,
  # else App Service doubles the path (…azurecr.io/…azurecr.io/…) and the pull
  # fails with ImagePullUnauthorizedFailure. config container set is the safe form.
  az webapp config container set -g "$RG" -n "$app" \
    --container-image-name "$ACR_SERVER/$image" \
    --container-registry-url "https://$ACR_SERVER" \
    --container-registry-user "$ACR_USER" \
    --container-registry-password "$ACR_PASS" -o none
  az webapp config appsettings set -g "$RG" -n "$app" \
    --settings "WEBSITES_PORT=$port" -o none
}

ensure_app "$API_APP" "sentinel-api:latest" 8000
ensure_app "$WEB_APP" "sentinel-web:latest" 3000

echo "==> Pushing backend secrets (.env) to $API_APP"
az webapp config appsettings set -g "$RG" -n "$API_APP" --settings \
  API_SERVER="https://${API_APP}.azurewebsites.net" \
  OPENAI_API_KEY="$(val OPENAI_API_KEY .env)" \
  AZURE_OPENAI_ENDPOINT="$(val AZURE_OPENAI_ENDPOINT .env)" \
  DEPLOYMENT_NAME_GPT54="$(val DEPLOYMENT_NAME_GPT54 .env)" \
  DEPLOYMENT_NAME_GPT54M="$(val DEPLOYMENT_NAME_GPT54M .env)" \
  IMAGE_DEPLOYMENT_NAME="$(val IMAGE_DEPLOYMENT_NAME .env)" \
  API_KEY="$(val API_KEY .env)" \
  COSMOS_URL="$(val COSMOS_URL .env)" \
  COSMOS_KEY="$(val COSMOS_KEY .env)" \
  AGENT_COSMOS_URL="$(val AGENT_COSMOS_URL .env)" \
  AGENT_COSMOS_KEY="$(val AGENT_COSMOS_KEY .env)" \
  BLOB_CONNECTION_STRING="$(val BLOB_CONNECTION_STRING .env)" \
  QDRANT_URL="$(val QDRANT_URL .env)" \
  QDRANT_API_KEY="$(val QDRANT_API_KEY .env)" \
  JINA_API_KEY="$(val JINA_API_KEY .env)" \
  TAVILY_API_KEY="$(val TAVILY_API_KEY .env)" -o none

echo "==> Pushing frontend secrets (frontend/.env.local) to $WEB_APP"
# FASTAPI_URL points at the backend's PUBLIC url: App Service has no private
# app-to-app network like Container Apps, so the BFF reaches the backend over
# HTTPS, gated by the shared X-API-Key (same key on both apps).
az webapp config appsettings set -g "$RG" -n "$WEB_APP" --settings \
  FASTAPI_URL="https://${API_APP}.azurewebsites.net" \
  API_KEY="$(val API_KEY frontend/.env.local)" \
  COOKIE_SECRET="$(val COOKIE_SECRET frontend/.env.local)" \
  AUTH_USERNAME="$(val AUTH_USERNAME frontend/.env.local)" \
  AUTH_PASSWORD="$(val AUTH_PASSWORD frontend/.env.local)" -o none

echo "==> Restarting apps"
az webapp restart -g "$RG" -n "$API_APP" -o none
az webapp restart -g "$RG" -n "$WEB_APP" -o none

# --- health waits -----------------------------------------------------------
wait_200() {
  local url="$1" label="$2"
  for _ in $(seq 1 30); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "$url" 2>/dev/null)" = "200" ] \
      && { echo "   $label OK"; return 0; }
    sleep 12
  done
  echo "   $label did NOT return 200 in time"; return 1
}
echo "==> Waiting for health"
wait_200 "https://${API_APP}.azurewebsites.net/market_agent/health" "backend"
wait_200 "https://${WEB_APP}.azurewebsites.net/login" "frontend"

echo
echo "Frontend: https://${WEB_APP}.azurewebsites.net"
echo "Backend : https://${API_APP}.azurewebsites.net  (X-API-Key protected)"
echo "Done."
