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
        confirmation_code = body.get('confirmationCode')
        new_password = body.get('newPassword')

        if not email or not confirmation_code or not new_password:
            return {
                'statusCode': 400,
                'headers': CORS_HEADERS,
                'body': json.dumps({'message': 'Missing email, confirmationCode or newPassword'})
            }

        client.confirm_forgot_password(
            ClientId=os.environ['CLIENT_ID'],
            Username=email,
            ConfirmationCode=confirmation_code,
            Password=new_password
        )

        return {
            'statusCode': 200,
            'headers': {**CORS_HEADERS, 'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'Password reset successfully'})
        }

    except client.exceptions.CodeMismatchException:
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Invalid reset code'})
        }
    except client.exceptions.ExpiredCodeException:
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Reset code has expired, please request a new one'})
        }
    except client.exceptions.InvalidPasswordException as e:
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': f'New password does not meet requirements: {str(e)}'})
        }
    except client.exceptions.UserNotFoundException:
        return {
            'statusCode': 400,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Invalid reset code'})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': CORS_HEADERS,
            'body': json.dumps({'message': 'Could not reset password'})
        }