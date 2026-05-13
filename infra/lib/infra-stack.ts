import * as cdk from 'aws-cdk-lib/core';
import { Construct } from 'constructs';
import { StorageConstruct } from './storage/storage-construct';
import { GatewayConstruct } from './gateway/gateway-construct';
import { LambdaIntegration } from 'aws-cdk-lib/aws-apigateway';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    
    var storageConstruct = new StorageConstruct(this, "ReceiptStorage");
    var gatewayConstruct = new GatewayConstruct(this, "ApiGateway");

    gatewayConstruct.addRoute(
      "/images",
      "POST",
      new LambdaIntegration(storageConstruct.uploadImageLambda),
    );

    new cdk.CfnOutput(this, "ApiUrl", {
      value: gatewayConstruct.api.url
    });
  }
}
