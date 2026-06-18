import { Duration, RemovalPolicy } from "aws-cdk-lib";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { Key } from "aws-cdk-lib/aws-kms";
import {
  Bucket,
  BucketEncryption,
  BlockPublicAccess,
  EventType,
  HttpMethods,
} from "aws-cdk-lib/aws-s3";
import { LambdaDestination } from "aws-cdk-lib/aws-s3-notifications";
import { Table, AttributeType, BillingMode } from "aws-cdk-lib/aws-dynamodb";
import { Construct } from "constructs";
import * as path from "path";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as cdk from "aws-cdk-lib";

export class StorageConstruct extends Construct {
  public readonly bucket: Bucket;
  public readonly receiptsTable: Table;
  public readonly uploadImageLambda: Function;
  public readonly getReceiptsLambda: Function;
  public readonly getReceiptLambda: Function;
  public readonly deleteReceiptLambda: Function;
  public readonly getReceiptsSummaryLambda: Function;
  public readonly getReceiptDetailedSummaryLambda: Function;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    const receiptEncryptionKey = new Key(this, "ReceiptEncryptionKey", {
      description: "KMS key for encrypting receipt images and extracted data",
      enableKeyRotation: true,        
      removalPolicy: RemovalPolicy.DESTROY,
    });

    this.bucket = new Bucket(this, id, {
      encryptionKey: receiptEncryptionKey,         
      encryption: BucketEncryption.KMS,   
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      cors: [
      {
        allowedMethods: [HttpMethods.GET],
        allowedOrigins: ["*"], 
        allowedHeaders: ["*"],
        maxAge: 300,
      },
    ],
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          id: "DeleteReceiptImagesAfter90Days",
          enabled: true,
          expiration: Duration.days(90),
          prefix: "uploads/",     
        },
      ],
    });

    this.receiptsTable = new Table(this, "ReceiptsTable", {
      partitionKey: { name: "userId", type: AttributeType.STRING },
      sortKey: { name: "receiptId", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      encryptionKey: receiptEncryptionKey,
      removalPolicy: RemovalPolicy.DESTROY, 
    });

    this.uploadImageLambda = new Function(this, "UploadImageLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "uploadImage.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    this.bucket.grantPut(this.uploadImageLambda);

    const processReceiptLambda = new Function(this, "ProcessReceiptLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "processReceipt.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      timeout: Duration.seconds(60),
      memorySize: 512,
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        BEDROCK_MODEL_ID: "eu.amazon.nova-lite-v1:0",
      },
    });

    this.receiptsTable.grantWriteData(processReceiptLambda);
    this.bucket.grantRead(processReceiptLambda);

    this.bucket.addEventNotification(
      EventType.OBJECT_CREATED,
      new LambdaDestination(processReceiptLambda),
      { prefix: "uploads/" }
    );

    this.getReceiptsLambda = new Function(this, "GetReceiptsLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "getReceipts.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    this.receiptsTable.grantReadData(this.getReceiptsLambda);
    this.bucket.grantRead(this.getReceiptsLambda); 

    processReceiptLambda.addToRolePolicy(new PolicyStatement({
      actions: [
        "textract:AnalyzeExpense",
      ],
      resources: ["*"],
    }));

    processReceiptLambda.addToRolePolicy(new PolicyStatement({
      actions: ["bedrock:InvokeModel"],
      resources: [
        `arn:aws:bedrock:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:inference-profile/eu.amazon.nova-lite-v1:0`,
        `arn:aws:bedrock:eu-west-1::foundation-model/amazon.nova-lite-v1:0`,
        `arn:aws:bedrock:eu-west-3::foundation-model/amazon.nova-lite-v1:0`,
        `arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-lite-v1:0`,
        `arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-lite-v1:0`,
      ],
    }));

    processReceiptLambda.addToRolePolicy(new PolicyStatement({
      actions: ["secretsmanager:GetSecretValue"],
      resources: [
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/*`,
      ],
    }));

    this.deleteReceiptLambda = new Function(this, "DeleteReceiptLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "deleteReceipt.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        BUCKET_NAME: this.bucket.bucketName,
      },
    });
    this.receiptsTable.grantReadWriteData(this.deleteReceiptLambda);
    this.bucket.grantDelete(this.deleteReceiptLambda);

    this.getReceiptsSummaryLambda = new Function(this, "GetReceiptsSummaryLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "getReceiptsSummary.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
      },
    });
    this.receiptsTable.grantReadData(this.getReceiptsSummaryLambda);
    this.bucket.grantRead(this.getReceiptsSummaryLambda, "uploads/*");

    this.getReceiptDetailedSummaryLambda = new Function(
      this,
      "GetReceiptDetailedSummaryLambda",
      {
        runtime: Runtime.PYTHON_3_12,
        handler: "receiptDetailedSummary.handler",
        code: Code.fromAsset(path.join(__dirname, "lambdas")),
        environment: {
          RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
          BUCKET_NAME: this.bucket.bucketName,
        },
      },
    );
    
    this.receiptsTable.grantReadData(this.getReceiptDetailedSummaryLambda);
    this.bucket.grantRead(this.getReceiptDetailedSummaryLambda, "uploads/*");
  }
}