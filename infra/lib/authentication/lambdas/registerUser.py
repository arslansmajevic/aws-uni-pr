import boto3
import os
import json

client = boto3.client('cognito-idp')

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

def handler(event, context):
    body = json.loads(event.get('body', '{}'))
    email = body.get('email')
    password = body.get('password')
    given_name = body.get('givenName')
    family_name = body.get('familyName')

    try:
        response = client.sign_up(
            ClientId=os.environ['CLIENT_ID'],
            Username=email,
            Password=password,
            UserAttributes=[
                {'Name': 'given_name', 'Value': given_name},
                {'Name': 'family_name', 'Value': family_name},
                {'Name': 'email', 'Value': email},
            ]
        )

        client.admin_confirm_sign_up(
            UserPoolId=os.environ['USER_POOL_ID'],
            Username=email
        )
        client.admin_update_user_attributes(
            UserPoolId=os.environ['USER_POOL_ID'],
            Username=email,
            UserAttributes=[
                {'Name': 'email_verified', 'Value': 'true'}
            ]
        )
        return {
            'statusCode': 200,
            'headers': {**CORS_HEADERS, 'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'User registered successfully', 'user_sub': response['UserSub']})
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({'error': str(e)})
        }