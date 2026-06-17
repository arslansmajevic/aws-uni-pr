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
        # The access token is what Cognito's ChangePassword call needs,
        # not the id token used elsewhere for authorizer claims.
        auth_header = event.get('headers', {}).get('Authorization') or event.get('headers', {}).get('authorization')
        if not auth_header:
            return {
                'statusCode': 401,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': 'Missing Authorization header'})
            }

        body = json.loads(event.get('body', '{}'))
        previous_password = body.get('previousPassword')
        proposed_password = body.get('newPassword')

        if not previous_password or not proposed_password:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': 'Missing previousPassword or newPassword'})
            }

        client.change_password(
            PreviousPassword=previous_password,
            ProposedPassword=proposed_password,
            AccessToken=auth_header
        )

        return {
            'statusCode': 200,
            'headers': {**CORS_HEADERS, 'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'Password changed successfully'})
        }

    except client.exceptions.NotAuthorizedException:
        return {
            'statusCode': 401,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Current password is incorrect or session expired'})
        }
    except client.exceptions.InvalidPasswordException as e:
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': f'New password does not meet requirements: {str(e)}'})
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
            'body': json.dumps({'message': 'Could not change password'})
        }