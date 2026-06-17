import boto3
import os
import json

client = boto3.client('cognito-idp')

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'POST,OPTIONS'
}

def handler(event, context):
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps({'ok': True})}

    try:
        body = json.loads(event.get('body', '{}'))
        email = body.get('email')

        if not email:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': 'Missing email'})
            }

        client.forgot_password(
            ClientId=os.environ['CLIENT_ID'],
            Username=email
        )

        # Always return the same generic message, whether or not the
        # email exists, so this endpoint can't be used to enumerate
        # registered accounts.
        return {
            'statusCode': 200,
            'headers': {**CORS_HEADERS, 'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'If an account exists for this email, a reset code has been sent.'})
        }

    except client.exceptions.UserNotFoundException:
        return {
            'statusCode': 200,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'If an account exists for this email, a reset code has been sent.'})
        }
    except client.exceptions.LimitExceededException:
        return {
            'statusCode': 429,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Too many attempts, please try again later'})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Could not start password reset'})
        }