import json
import boto3
import os

client = boto3.client('cognito-idp')

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

def handler(event, context):
    try:
        # 1. Parse the body to get the refresh token
        body = json.loads(event.get('body', '{}'))
        refresh_token = body.get('refreshToken')

        if not refresh_token:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"message": "Missing refreshToken in request body"})
            }

        # 2. Call Cognito to exchange the Refresh Token for new ID/Access tokens
        response = client.initiate_auth(
            ClientId=os.environ['CLIENT_ID'],
            AuthFlow='REFRESH_TOKEN_AUTH',
            AuthParameters={
                'REFRESH_TOKEN': refresh_token
            }
        )

        # 3. Extract the new tokens
        auth_result = response.get('AuthenticationResult', {})

        return {
            "statusCode": 200,
            "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
            "body": json.dumps({
                "IdToken": auth_result.get('IdToken'),
                "AccessToken": auth_result.get('AccessToken'),
                "ExpiresIn": auth_result.get('ExpiresIn')
            })
        }

    except client.exceptions.NotAuthorizedException:
        return {
            "statusCode": 401,
            "headers": CORS_HEADERS,
            "body": json.dumps({"message": "Invalid or expired refresh token. Please log in again."})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"message": "Could not refresh token"})
        }