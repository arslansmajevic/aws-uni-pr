import { RemovalPolicy } from "aws-cdk-lib";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import {
  Bucket,
  BucketEncryption,
  BlockPublicAccess,
  EventType,
} from "aws-cdk-lib/aws-s3";
import { LambdaDestination } from "aws-cdk-lib/aws-s3-notifications";
import { Table, AttributeType, BillingMode } from "aws-cdk-lib/aws-dynamodb";
import { Construct } from "constructs";
import * as path from "path";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";

export class StorageConstruct extends Construct {
  public readonly bucket: Bucket;
  public readonly receiptsTable: Table;
  public readonly uploadImageLambda: Function;
  public readonly getReceiptsLambda: Function;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.bucket = new Bucket(this, id, {
      // bucketName: "receipt-storage-bucket",
      encryption: BucketEncryption.S3_MANAGED,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    this.receiptsTable = new Table(this, "ReceiptsTable", {
      partitionKey: { name: "userId", type: AttributeType.STRING },
      sortKey: { name: "receiptId", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
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
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        BEDROCK_MODEL_ID: "anthropic.claude-haiku-4-5",
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
      },
    });

    this.receiptsTable.grantReadData(this.getReceiptsLambda);

    processReceiptLambda.addToRolePolicy(new PolicyStatement({
      actions: [
        "textract:AnalyzeExpense",
        "textract:DetectDocumentText",
      ],
      resources: ["*"],
    }));

    processReceiptLambda.addToRolePolicy(new PolicyStatement({
      actions: ["bedrock:InvokeModel"],
      resources: ["*"],
    }));
  }
}