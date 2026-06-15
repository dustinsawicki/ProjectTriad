param location string
param tags object
param resourceToken string

var namespaceName = 'ehns-${resourceToken}'

resource namespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
    capacity: 1
  }
  properties: {
    disableLocalAuth: true
    isAutoInflateEnabled: false
    minimumTlsVersion: '1.2'
  }
}

resource claimEventsHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: namespace
  name: 'claim-events'
  properties: {
    messageRetentionInDays: 1
    partitionCount: 4
  }
}

resource fraudScoringHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: namespace
  name: 'fraud-scoring'
  properties: {
    messageRetentionInDays: 1
    partitionCount: 2
  }
}

resource telematicsStreamHub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: namespace
  name: 'telematics-stream'
  properties: {
    messageRetentionInDays: 1
    partitionCount: 2
  }
}

// Consumer groups for the API
resource claimEventsConsumer 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: claimEventsHub
  name: 'api-consumer'
}

resource telematicsConsumer 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = {
  parent: telematicsStreamHub
  name: 'api-consumer'
}

output namespaceFqdn string = '${namespace.name}.servicebus.windows.net'
output namespaceName string = namespace.name
output namespaceId string = namespace.id
