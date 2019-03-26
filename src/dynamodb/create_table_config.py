import boto3

dynamodb = boto3.resource('dynamodb')

"""
Table: fp.config
Partition key: id (string)
Attributes: value (string)
RCU: 2
WCU: 1
"""
config = dynamodb.create_table(
    TableName='fp.config',
    KeySchema=[
        {
            'AttributeName': 'id',
            'KeyType': 'HASH'  #Partition key
        }
    ],
    AttributeDefinitions=[
        {
            'AttributeName': 'id',
            'AttributeType': 'S'
        }
    ],
    ProvisionedThroughput={
        'ReadCapacityUnits': 2,
        'WriteCapacityUnits': 1
    }
)