// Subscription-scope entry point for the Agentic Claims Processing PoC.
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

var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var rgName        = 'rg-claims-poc-${environmentName}'

var tags = {
  'azd-env-name': environmentName
  workload: 'claims-poc'
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
  }
}

// Outputs consumed by azd and by run-seed scripts
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
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.appInsightsConnectionString
