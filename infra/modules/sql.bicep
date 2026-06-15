param location string
param tags object
param resourceToken string
@description('Object ID of the deploying principal — set as Entra admin so it can run schema/seed and grant DB principals to MIs.')
param principalId string

var serverName = 'sql-${resourceToken}'
var dbName     = 'sqldb-claims'

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    version: '12.0'
    publicNetworkAccess: 'Enabled'
    minimalTlsVersion: '1.2'
    restrictOutboundNetworkAccess: 'Disabled'
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'User'
      login: 'azd-deployer'
      sid: principalId
      tenantId: tenant().tenantId
      azureADOnlyAuthentication: true
    }
  }
}

// Allow Azure services + ACA outbound; PoC simplification
resource fwAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Wide PoC rule — REMOVE for production (use Private Endpoint)
resource fwOpen 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAllForPoc'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '255.255.255.255'
  }
}

resource db 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: dbName
  location: location
  tags: tags
  sku: {
    name: 'GP_S_Gen5_2'
    tier: 'GeneralPurpose'
    family: 'Gen5'
    capacity: 2
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    autoPauseDelay: 60
    minCapacity: json('0.5')
    maxSizeBytes: 34359738368  // 32 GB
    zoneRedundant: false
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: 'Local'
  }
}

output serverName  string = sqlServer.name
output serverFqdn  string = sqlServer.properties.fullyQualifiedDomainName
output databaseName string = db.name
