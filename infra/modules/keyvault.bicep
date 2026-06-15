param location string
param tags object
param resourceToken string
param tenantId string
param principalId string

resource kv 'Microsoft.KeyVault/vaults@2024-04-01-preview' = {
  name: 'kv-${take(resourceToken, 20)}'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenantId
    enableRbacAuthorization: true
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 7
    enableSoftDelete: true
  }
}

// Give the deploying principal Secrets Officer so seed/setup can write secrets
resource kvSecretsOfficer 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(principalId)) {
  scope: kv
  name: guid(kv.id, principalId, 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
    principalId: principalId
    principalType: 'User'
  }
}

output name string = kv.name
output id string = kv.id
output uri string = kv.properties.vaultUri
