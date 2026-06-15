param location string
param tags object
param resourceToken string

var accountName = 'di-${resourceToken}'

resource docIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

output endpoint string = docIntelligence.properties.endpoint
output name string = docIntelligence.name
output id string = docIntelligence.id
