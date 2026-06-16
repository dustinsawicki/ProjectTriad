// Subscription-scope entry point for the Agentic Claims Processing PoC (v2).
// Creates a single resource group and delegates to per-service modules.
targetScope = 'subscription'

@minLength(1)
@maxLength(20)
@description('azd environment name (used in naming).')
param environmentName string

@description('Primary Azure region for all resources.')
param location string

@description('Entra tenant ID.')
param tenantId string

@description('Object ID of the principal running azd (gets KV/SQL admin during deploy).')
param principalId string

@description('Comma-separated Entra user object IDs to grant the ClaimsAdjuster app role.')
param adjusterUserObjectIds string = ''

@description('Azure OpenAI model deployment name for reasoning agents.')
param openAiModel string = 'gpt-4o'

@description('Azure OpenAI mini model deployment name for the Guardrails agent.')
param openAiMiniModel string = 'gpt-4o-mini'

@description('AI Search index name for historical claims RAG.')
param searchIndexName string = 'historical-claims'

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var rgName        = 'rg-claims-poc-${environmentName}'

var tags = {
  'azd-env-name': environmentName
  workload: 'claims-poc-v2'
  industry: 'fsi-insurance'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module keyvault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    tenantId: tenantId
    principalId: principalId
  }
}

module acr 'modules/acr.bicep' = {
  name: 'acr'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module sql 'modules/sql.bicep' = {
  name: 'sql'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    principalId: principalId
  }
}

module foundry 'modules/foundry.bicep' = {
  name: 'foundry'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    openAiModel: openAiModel
    openAiMiniModel: openAiMiniModel
    principalId: principalId
  }
}

// --- v2 modules ---

module storage 'modules/storage.bicep' = {
  name: 'storage'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module eventhubs 'modules/eventhubs.bicep' = {
  name: 'eventhubs'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module docintel 'modules/docintel.bicep' = {
  name: 'docintel'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module search 'modules/search.bicep' = {
  name: 'search'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
  }
}

module aca 'modules/containerapps.bicep' = {
  name: 'aca'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    logAnalyticsId:      monitoring.outputs.logAnalyticsId
    appInsightsConnStr:  monitoring.outputs.appInsightsConnectionString
    keyVaultName:        keyvault.outputs.name
    acrLoginServer:      acr.outputs.loginServer
    acrName:             acr.outputs.name
    sqlServerFqdn:       sql.outputs.serverFqdn
    sqlDatabaseName:     sql.outputs.databaseName
    foundryProjectEndpoint: foundry.outputs.projectEndpoint
    foundryModelDeployment: openAiModel
    foundryMiniModelDeployment: openAiMiniModel
    tenantId: tenantId
    adjusterUserObjectIds: adjusterUserObjectIds
    // v2 params
    cosmosEndpoint:       cosmos.outputs.endpoint
    cosmosDatabase:       cosmos.outputs.databaseName
    blobAccountName:      storage.outputs.name
    blobEndpoint:         storage.outputs.blobEndpoint
    eventHubNamespaceFqdn: eventhubs.outputs.namespaceFqdn
    docIntelEndpoint:     docintel.outputs.endpoint
    searchEndpoint:       search.outputs.endpoint
    searchIndexName:      searchIndexName
    cosmosAccountName:    cosmos.outputs.name
    storageAccountId:     storage.outputs.id
    cosmosAccountId:      cosmos.outputs.id
    eventHubNamespaceId:  eventhubs.outputs.namespaceId
    docIntelId:           docintel.outputs.id
    searchId:             search.outputs.id
  }
}

// Outputs consumed by azd and by seed scripts
output AZURE_LOCATION                  string = location
output AZURE_TENANT_ID                 string = tenantId
output AZURE_RESOURCE_GROUP            string = rg.name
output SQL_SERVER_FQDN                 string = sql.outputs.serverFqdn
output SQL_DATABASE_NAME               string = sql.outputs.databaseName
output KEY_VAULT_NAME                  string = keyvault.outputs.name
output AZURE_CONTAINER_REGISTRY_NAME   string = acr.outputs.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.outputs.loginServer
output FOUNDRY_PROJECT_ENDPOINT        string = foundry.outputs.projectEndpoint
output FOUNDRY_MODEL_DEPLOYMENT        string = openAiModel
output FOUNDRY_MINI_MODEL_DEPLOYMENT   string = openAiMiniModel
output API_BASE_URL                    string = aca.outputs.apiFqdn
output WEB_BASE_URL                    string = aca.outputs.webFqdn
// v2 outputs
output COSMOS_ENDPOINT                 string = cosmos.outputs.endpoint
output COSMOS_DATABASE                 string = cosmos.outputs.databaseName
output BLOB_ACCOUNT_NAME               string = storage.outputs.name
output BLOB_ENDPOINT                   string = storage.outputs.blobEndpoint
output EVENT_HUB_NAMESPACE_FQDN        string = eventhubs.outputs.namespaceFqdn
output DOCINTEL_ENDPOINT               string = docintel.outputs.endpoint
output SEARCH_ENDPOINT                 string = search.outputs.endpoint
output SEARCH_INDEX_NAME               string = searchIndexName
output EXTERNAL_API_BASE_URL           string = aca.outputs.externalApiFqdn
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
