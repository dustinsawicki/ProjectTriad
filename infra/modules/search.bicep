param location string
param tags object
param resourceToken string

var serviceName = 'srch-${resourceToken}'

resource searchService 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name: serviceName
  location: location
  tags: tags
  sku: { name: 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    hostingMode: 'default'
    partitionCount: 1
    replicaCount: 1
    publicNetworkAccess: 'enabled'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http403'
      }
    }
    semanticSearch: 'free'
  }
}

output endpoint string = 'https://${searchService.name}.search.windows.net'
output name string = searchService.name
output id string = searchService.id
