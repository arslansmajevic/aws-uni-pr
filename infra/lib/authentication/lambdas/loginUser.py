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

    try:
        response = client.initiate_auth(
            ClientId=os.environ['CLIENT_ID'],
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': email,
                'PASSWORD': password
            }
        )
        
        # This contains your AccessToken, IdToken, and RefreshToken
        auth_result = response.get('AuthenticationResult')

        return {
            'statusCode': 200,
            'headers': {**CORS_HEADERS, 'Content-Type': 'application/json'},
            'body': json.dumps(auth_result)
        }
        
    except client.exceptions.NotAuthorizedException:
        return { 'statusCode': 401, 'headers': CORS_HEADERS, 'body': json.dumps({'error': 'Invalid email or password'}) }
    except client.exceptions.UserNotConfirmedException:
        return { 'statusCode': 403, 'headers': CORS_HEADERS, 'body': json.dumps({'error': 'User is not confirmed'}) }
    except Exception as e:
        return { 'statusCode': 400, 'headers': CORS_HEADERS, 'body': json.dumps({'error': str(e)}) }