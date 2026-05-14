import boto3
import os
import json

client = boto3.client('cognito-idp')

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Content-Type': 'application/json'
}

def handler(event, context):
    user_pool_id = os.environ['USER_POOL_ID']
    all_users = []
    
    try:
        # Create a paginator for the list_users operation
        paginator = client.get_paginator('list_users')
        page_iterator = paginator.paginate(UserPoolId=user_pool_id)

        for page in page_iterator:
            for user in page['Users']:
                # Clean up the attribute list into a readable dictionary
                user_data = {
                    'username': user['Username'],
                    'status': user['UserStatus'],
                    'enabled': user['Enabled'],
                    'created': str(user['UserCreateDate'])
                }
                
                # Convert the list of Attributes [{'Name': '...', 'Value': '...'}] to a dict
                attributes = {attr['Name']: attr['Value'] for attr in user.get('Attributes', [])}
                user_data.update(attributes)
                
                all_users.append(user_data)

        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({'users': all_users})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(e)})
        }