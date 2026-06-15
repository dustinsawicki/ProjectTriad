param location string
param tags object
param resourceToken string
param logAnalyticsId string
param appInsightsConnStr string
param keyVaultName string
param acrLoginServer string
param acrName string
param sqlServerFqdn string
param sqlDatabaseName string
param foundryProjectEndpoint string
param foundryModelDeployment string
param foundryMiniModelDeployment string
param tenantId string
param adjusterUserObjectIds string
// v2 params
param cosmosEndpoint string
param cosmosDatabase string
param blobAccountName string
param blobEndpoint string
param eventHubNamespaceFqdn string
param docIntelEndpoint string
param searchEndpoint string
param searchIndexName string
param cosmosAccountName string
param storageAccountId string
param cosmosAccountId string
param eventHubNamespaceId string
param docIntelId string
param searchId string

var envName = 'cae-${resourceToken}'
var apiName = 'ca-api-${resourceToken}'
var webName = 'ca-web-${resourceToken}'
var extApiName = 'ca-extapis-${resourceToken}'
var placeholderImage = 'mcr.microsoft.com/k8se/quickstart:latest'

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsId, '/'))
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

resource kv 'Microsoft.KeyVault/vaults@2024-04-01-preview' existing = {
  name: keyVaultName
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// User-assigned identity isn't required — both apps use system-assigned MI

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: [ 'https://${webName}.${env.properties.defaultDomain}' ]
          allowedMethods: [ 'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS' ]
          allowedHeaders: [ '*' ]
          allowCredentials: true
        }
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: placeholderImage
          resources: { cpu: json('1.0'), memory: '2.0Gi' }
          env: [
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnStr }
            { name: 'SQL_SERVER_FQDN',  value: sqlServerFqdn }
            { name: 'SQL_DATABASE_NAME', value: sqlDatabaseName }
            { name: 'KEY_VAULT_NAME',    value: keyVaultName }
            { name: 'AZURE_TENANT_ID',   value: tenantId }
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_MODEL_DEPLOYMENT', value: foundryModelDeployment }
            { name: 'FOUNDRY_MINI_MODEL_DEPLOYMENT', value: foundryMiniModelDeployment }
            { name: 'ADJUSTER_USER_OBJECT_IDS', value: adjusterUserObjectIds }
            // v2 env vars
            { name: 'COSMOS_ENDPOINT',    value: cosmosEndpoint }
            { name: 'COSMOS_DATABASE',    value: cosmosDatabase }
            { name: 'BLOB_ACCOUNT_NAME',  value: blobAccountName }
            { name: 'BLOB_ENDPOINT',      value: blobEndpoint }
            { name: 'EVENT_HUB_NAMESPACE_FQDN', value: eventHubNamespaceFqdn }
            { name: 'DOCINTEL_ENDPOINT',  value: docIntelEndpoint }
            { name: 'SEARCH_ENDPOINT',    value: searchEndpoint }
            { name: 'SEARCH_INDEX_NAME',  value: searchIndexName }
            { name: 'EXTERNAL_API_BASE_URL', value: 'https://${extApiName}.internal.${env.properties.defaultDomain}' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

resource webApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: webName
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'web'
          image: placeholderImage
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnStr }
            { name: 'NEXT_PUBLIC_API_BASE_URL', value: 'https://${apiApp.properties.configuration.ingress.fqdn}' }
            { name: 'NEXT_PUBLIC_AZURE_TENANT_ID', value: tenantId }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// Role: AcrPull for both apps on the ACR
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource apiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, apiApp.id, acrPullRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
resource webAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, webApp.id, acrPullRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Role: Key Vault Secrets User for the API
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
resource apiKvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, apiApp.id, kvSecretsUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Role: Cognitive Services OpenAI User for the API (data-plane access to Foundry)
var aiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: 'aif-${resourceToken}'
}
resource apiAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: aiAccount
  name: guid(aiAccount.id, apiApp.id, aiUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', aiUserRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- v2: External APIs Container App ---

resource extApiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: extApiName
  location: location
  tags: union(tags, { 'azd-service-name': 'external-apis' })
  identity: { type: 'SystemAssigned' }
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      ingress: {
        external: false
        targetPort: 80
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'external-apis'
          image: placeholderImage
          resources: { cpu: json('0.5'), memory: '1.0Gi' }
          env: [
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnStr }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
}

// AcrPull for external-apis
resource extApiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, extApiApp.id, acrPullRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: extApiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// --- v2: Role assignments for Cosmos, Blob, Event Hubs, Doc Intelligence, AI Search ---

// Cosmos DB Built-in Data Contributor for API
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}
resource apiCosmosRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, apiApp.id, cosmosDataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${cosmosDataContributorRoleId}'
    principalId: apiApp.identity.principalId
    scope: cosmosAccount.id
  }
}

// Storage Blob Data Contributor for API
var blobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: blobAccountName
}
resource apiBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, apiApp.id, blobContributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributorRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Event Hubs Data Owner for API
var ehDataOwnerRoleId = 'f526a384-b230-433a-b45c-95f59c4a2dec'
resource ehNamespace 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: last(split(eventHubNamespaceId, '/'))
}
resource apiEhRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: ehNamespace
  name: guid(ehNamespace.id, apiApp.id, ehDataOwnerRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', ehDataOwnerRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User for API on Document Intelligence
var cogServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'
resource docIntelAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(docIntelId, '/'))
}
resource apiDocIntelRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: docIntelAccount
  name: guid(docIntelAccount.id, apiApp.id, cogServicesUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cogServicesUserRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor for API
var searchIndexContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' existing = {
  name: last(split(searchId, '/'))
}
resource apiSearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, apiApp.id, searchIndexContributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexContributorRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Search Service Contributor for API (index management)
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
resource apiSearchMgmtRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, apiApp.id, searchServiceContributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalId: apiApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output apiName string = apiApp.name
output webName string = webApp.name
output apiFqdn string = 'https://${apiApp.properties.configuration.ingress.fqdn}'
output webFqdn string = 'https://${webApp.properties.configuration.ingress.fqdn}'
output apiPrincipalId string = apiApp.identity.principalId
output webPrincipalId string = webApp.identity.principalId
output externalApiFqdn string = 'https://${extApiApp.properties.configuration.ingress.fqdn}'
