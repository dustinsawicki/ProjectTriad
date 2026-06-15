// Azure AI Foundry account + project + model deployments.
// Foundry agents are created at runtime by the API via azure-ai-projects.
param location string
param tags object
param resourceToken string
param openAiModel string
param openAiMiniModel string
param principalId string

var aiAccountName = 'aif-${resourceToken}'
var aiProjectName = 'aifproj-${resourceToken}'

resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiAccountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: aiAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    allowProjectManagement: true
  }
}

resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiAccount
  name: openAiModel
  sku: {
    name: 'GlobalStandard'
    capacity: 30
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: openAiModel
      version: '2024-08-06'
    }
  }
}

resource gpt4oMini 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiAccount
  name: openAiMiniModel
  dependsOn: [ gpt4o ]
  sku: {
    name: 'GlobalStandard'
    capacity: 30
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: openAiMiniModel
      version: '2024-07-18'
    }
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2024-10-01' = {
  parent: aiAccount
  name: aiProjectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

// Grant the deploying principal "Azure AI User" so they can manage agents during development
resource aiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  scope: aiAccount
  name: guid(aiAccount.id, principalId, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    principalId: principalId
    principalType: 'User'
  }
}

output accountName string = aiAccount.name
output projectName string = aiProject.name
output projectEndpoint string = 'https://${aiAccount.name}.services.ai.azure.com/api/projects/${aiProject.name}'
output accountEndpoint string = aiAccount.properties.endpoint
