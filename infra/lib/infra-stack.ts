import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import { StorageConstruct } from './storage/storage-construct';
import { GatewayConstruct } from './gateway/gateway-construct';
import { LambdaIntegration } from 'aws-cdk-lib/aws-apigateway';
import { AuthenticationConstruct } from './authentication/authentication-construct';
import { BankingConstruct } from './banking/banking-constructs';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    
    var storageConstruct = new StorageConstruct(this, "ReceiptStorage");
    var gatewayConstruct = new GatewayConstruct(this, "ApiGateway");
    var authenticationConstruct = new AuthenticationConstruct(this, "Authentication");
    var bankingConstruct = new BankingConstruct(this, "Banking");

    const jwtRequiredFlag = true;

    gatewayConstruct.addLambdaRoutes(
      [
        {
          function: storageConstruct.uploadImageLambda,
          method: "POST",
          resourcePath: "image",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: authenticationConstruct.registerLambda,
          method: "POST",
          resourcePath: "register",
        },
        {
          function: authenticationConstruct.loginLambda,
          method: "POST",
          resourcePath: "login",
        },
        {
          function: authenticationConstruct.refreshTokenLambda,
          method: "POST",
          resourcePath: "refresh",
        },
        {
          function: authenticationConstruct.listUsersLambda,
          method: "GET",
          resourcePath: "users",
          jwtRequired: jwtRequiredFlag,
        },
        { function: storageConstruct.getReceiptsLambda,     
           method: "GET",  
           resourcePath: "receipts", 
           jwtRequired: jwtRequiredFlag,
        }, 
        { function: bankingConstruct.createLinkTokenLambda, 
          method: "POST", 
          resourcePath: "bank/connect",  
          jwtRequired: jwtRequiredFlag,
        },
        { function: bankingConstruct.exchangeTokenLambda,   
          method: "POST", 
          resourcePath: "bank/exchange", 
          jwtRequired: jwtRequiredFlag 
        },
      ],
      authenticationConstruct.authorizer,
    );

    new cdk.CfnOutput(this, "ApiUrl", {
      value: gatewayConstruct.api.url
    });
  }
}
