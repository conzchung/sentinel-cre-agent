// Sentinel — Azure Container Apps deployment.
//
// Two services in one Container Apps Environment:
//   • api (FastAPI agent) — INTERNAL ingress only; reachable from web over the
//     ACA private network, never exposed to the internet.
//   • web (Next.js BFF)   — EXTERNAL ingress; this is the public URL. It proxies
//     to api server-side, injecting X-API-Key, so the key never reaches a browser.
//
// Secrets are passed as @secure() parameters (sourced from the local .env /
// frontend/.env.local by azd) and materialised as Container Apps secrets — they
// are never written to the repo or the image.
//
// Naming follows the az{prefix}{token} convention for the supporting resources;
// the two apps keep readable names (api app name surfaces in the public FQDN).

targetScope = 'resourceGroup'

@minLength(1)
@description('Name of the azd environment — used to derive a unique resource token.')
param environmentName string

@minLength(1)
@description('Azure region for all resources (defaults to the resource group location).')
param location string = resourceGroup().location

// ---- Secrets: backend (FastAPI agent) ----
@secure()
param openaiApiKey string
@secure()
param azureOpenaiEndpoint string
@secure()
param deploymentNameGpt54 string
@secure()
param deploymentNameGpt54m string
@secure()
param imageDeploymentName string
@secure()
param apiKey string
@secure()
param cosmosUrl string
@secure()
param cosmosKey string
@secure()
param agentCosmosUrl string
@secure()
param agentCosmosKey string
@secure()
param blobConnectionString string
@secure()
param qdrantUrl string
@secure()
param qdrantApiKey string
@secure()
param jinaApiKey string
@secure()
param tavilyApiKey string

// ---- Secrets: frontend (Next.js) ----
// apiKey above is shared — the web BFF must present the SAME key the api expects.
@secure()
param cookieSecret string
@secure()
param authUsername string
@secure()
param authPassword string

// Resource-group-scoped token: stable per (subscription, RG, location, env).
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var tags = { 'azd-env-name': environmentName, application: 'sentinel' }

// azd updates these placeholder images with the real built images on `azd deploy`.
var placeholderImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// ---------------------------------------------------------------------------
// Container Registry — holds both built images. Anonymous pull stays disabled.
// ---------------------------------------------------------------------------
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: 'azcr${resourceToken}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
  }
}

// ---------------------------------------------------------------------------
// User-assigned managed identity — both apps use it to pull from ACR.
// ---------------------------------------------------------------------------
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'azid${resourceToken}'
  location: location
  tags: tags
}

// MANDATORY: grant the identity AcrPull on the registry BEFORE the apps exist,
// so the first revision can pull. One assignment per registry.
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: acr
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

// ---------------------------------------------------------------------------
// Log Analytics — required backing store for the Container Apps Environment.
// ---------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'azlog${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Container Apps Environment.
// ---------------------------------------------------------------------------
resource caeEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'azcae${resourceToken}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Backend: FastAPI agent — INTERNAL ingress, port 8000.
// ---------------------------------------------------------------------------
resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'sentinel-api'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: caeEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['*']
          allowedHeaders: ['*']
        }
      }
      registries: [
        { server: acr.properties.loginServer, identity: identity.id }
      ]
      secrets: [
        { name: 'openai-api-key', value: openaiApiKey }
        { name: 'azure-openai-endpoint', value: azureOpenaiEndpoint }
        { name: 'deployment-name-gpt54', value: deploymentNameGpt54 }
        { name: 'deployment-name-gpt54m', value: deploymentNameGpt54m }
        { name: 'image-deployment-name', value: imageDeploymentName }
        { name: 'api-key', value: apiKey }
        { name: 'cosmos-url', value: cosmosUrl }
        { name: 'cosmos-key', value: cosmosKey }
        { name: 'agent-cosmos-url', value: agentCosmosUrl }
        { name: 'agent-cosmos-key', value: agentCosmosKey }
        { name: 'blob-connection-string', value: blobConnectionString }
        { name: 'qdrant-url', value: qdrantUrl }
        { name: 'qdrant-api-key', value: qdrantApiKey }
        { name: 'jina-api-key', value: jinaApiKey }
        { name: 'tavily-api-key', value: tavilyApiKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: placeholderImage
          resources: { cpu: json('1.0'), memory: '2.0Gi' }
          env: [
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
            { name: 'AZURE_OPENAI_ENDPOINT', secretRef: 'azure-openai-endpoint' }
            { name: 'DEPLOYMENT_NAME_GPT54', secretRef: 'deployment-name-gpt54' }
            { name: 'DEPLOYMENT_NAME_GPT54M', secretRef: 'deployment-name-gpt54m' }
            { name: 'IMAGE_DEPLOYMENT_NAME', secretRef: 'image-deployment-name' }
            { name: 'API_KEY', secretRef: 'api-key' }
            { name: 'COSMOS_URL', secretRef: 'cosmos-url' }
            { name: 'COSMOS_KEY', secretRef: 'cosmos-key' }
            { name: 'AGENT_COSMOS_URL', secretRef: 'agent-cosmos-url' }
            { name: 'AGENT_COSMOS_KEY', secretRef: 'agent-cosmos-key' }
            { name: 'BLOB_CONNECTION_STRING', secretRef: 'blob-connection-string' }
            { name: 'QDRANT_URL', secretRef: 'qdrant-url' }
            { name: 'QDRANT_API_KEY', secretRef: 'qdrant-api-key' }
            { name: 'JINA_API_KEY', secretRef: 'jina-api-key' }
            { name: 'TAVILY_API_KEY', secretRef: 'tavily-api-key' }
          ]
        }
      ]
      // min 1: the agent serves long LLM requests — a cold start on the internal
      // backend would stall the first call. Kept to max 2 for cost.
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
  dependsOn: [ acrPullRole ]
}

// ---------------------------------------------------------------------------
// Frontend: Next.js — EXTERNAL ingress, port 3000. This is the public URL.
// ---------------------------------------------------------------------------
resource webApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'sentinel-web'
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: caeEnv.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['*']
          allowedHeaders: ['*']
        }
      }
      registries: [
        { server: acr.properties.loginServer, identity: identity.id }
      ]
      secrets: [
        { name: 'api-key', value: apiKey }
        { name: 'cookie-secret', value: cookieSecret }
        { name: 'auth-username', value: authUsername }
        { name: 'auth-password', value: authPassword }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: placeholderImage
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            // Reach the backend over the ACA private network (HTTPS on the
            // internal FQDN). Server-side only — never exposed to the browser.
            { name: 'FASTAPI_URL', value: 'https://${apiApp.properties.configuration.ingress.fqdn}' }
            { name: 'API_KEY', secretRef: 'api-key' }
            { name: 'COOKIE_SECRET', secretRef: 'cookie-secret' }
            { name: 'AUTH_USERNAME', secretRef: 'auth-username' }
            { name: 'AUTH_PASSWORD', secretRef: 'auth-password' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [ acrPullRole ]
}

// Outputs azd surfaces after provision. ACR vars let azd push the built images.
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.properties.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = acr.name
output SENTINEL_WEB_URI string = 'https://${webApp.properties.configuration.ingress.fqdn}'
output SENTINEL_API_INTERNAL_FQDN string = apiApp.properties.configuration.ingress.fqdn
