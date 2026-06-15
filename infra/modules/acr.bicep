param location string
param tags object
param resourceToken string

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: 'acr${replace(resourceToken, '-', '')}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output name string = acr.name
output id string = acr.id
output loginServer string = acr.properties.loginServer
