param location string
param tags object
param resourceToken string

var accountName = 'cosmos-${resourceToken}'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      { name: 'EnableServerless' }
    ]
    disableLocalAuth: true
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'claims'
  properties: {
    resource: { id: 'claims' }
  }
}

resource telemeticsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'telematics'
  properties: {
    resource: {
      id: 'telematics'
      partitionKey: { paths: [ '/claimId' ], kind: 'Hash' }
    }
  }
}

resource featureStoreContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'feature_store'
  properties: {
    resource: {
      id: 'feature_store'
      partitionKey: { paths: [ '/key' ], kind: 'Hash' }
    }
  }
}

resource linkGraphContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'link_graph'
  properties: {
    resource: {
      id: 'link_graph'
      partitionKey: { paths: [ '/partitionKey' ], kind: 'Hash' }
    }
  }
}

output endpoint string = cosmosAccount.properties.documentEndpoint
output name string = cosmosAccount.name
output id string = cosmosAccount.id
output databaseName string = database.name
