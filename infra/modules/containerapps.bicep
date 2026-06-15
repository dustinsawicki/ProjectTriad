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

var envName = 'cae-${resourceToken}'
var apiName = 'ca-api-${resourceToken}'
var webName = 'ca-web-${resourceToken}'
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

output apiName string = apiApp.name
output webName string = webApp.name
output apiFqdn string = 'https://${apiApp.properties.configuration.ingress.fqdn}'
output webFqdn string = 'https://${webApp.properties.configuration.ingress.fqdn}'
output apiPrincipalId string = apiApp.identity.principalId
output webPrincipalId string = webApp.identity.principalId
