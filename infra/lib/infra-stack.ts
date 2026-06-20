import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import { StorageConstruct } from './storage/storage-construct';
import { GatewayConstruct } from './gateway/gateway-construct';
import { AuthenticationConstruct } from './authentication/authentication-construct';
import { BankingConstruct } from './banking/banking-constructs';

export class InfraStack extends cdk.Stack {
  public readonly apiUrl: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    var storageConstruct = new StorageConstruct(this, "ReceiptStorage");
    var gatewayConstruct = new GatewayConstruct(this, "ApiGateway");
    var authenticationConstruct = new AuthenticationConstruct(
      this,
      "Authentication",
    );
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
          function: storageConstruct.uploadMultiImageLambda,
          method: "POST",
          resourcePath: "image/multi",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: storageConstruct.addReceiptImageLambda,
          method: "POST",
          resourcePath: "receipts/{receiptId}/image",
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
          function: authenticationConstruct.changePasswordLambda,
          method: "POST",
          resourcePath: "change-password",
        },
        {
          function: authenticationConstruct.forgotPasswordLambda,
          method: "POST",
          resourcePath: "forgot-password",
        },
        {
          function: authenticationConstruct.confirmForgotPasswordLambda,
          method: "POST",
          resourcePath: "confirm-forgot-password",
        },
        {
          function: authenticationConstruct.listUsersLambda,
          method: "GET",
          resourcePath: "users",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: storageConstruct.getReceiptsLambda,
          method: "GET",
          resourcePath: "receipts",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: storageConstruct.getReceiptDetailedSummaryLambda,
          method: "GET",
          resourcePath: "receipts/{receiptId}",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: storageConstruct.deleteReceiptLambda,
          method: "DELETE",
          resourcePath: "receipts/{receiptId}",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: storageConstruct.getReceiptsSummaryLambda,
          method: "GET",
          resourcePath: "summary",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: bankingConstruct.createLinkTokenLambda,
          method: "POST",
          resourcePath: "bank/connect",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: bankingConstruct.exchangeTokenLambda,
          method: "POST",
          resourcePath: "bank/exchange",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: bankingConstruct.disconnectBankLambda,
          method: "POST",
          resourcePath: "bank/disconnect",
          jwtRequired: jwtRequiredFlag,
        },
        {
          function: bankingConstruct.getBankStatusLambda,
          method: "GET",
          resourcePath: "bank/status",
          jwtRequired: jwtRequiredFlag,
        },
      ],
      authenticationConstruct.authorizer,
    );

    this.apiUrl = gatewayConstruct.api.url;

    new cdk.CfnOutput(this, "ApiUrl", {
      value: this.apiUrl,
    });
  }
}