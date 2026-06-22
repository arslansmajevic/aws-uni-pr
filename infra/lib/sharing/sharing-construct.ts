import { RemovalPolicy } from "aws-cdk-lib";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import {
  Table,
  AttributeType,
  BillingMode,
  ProjectionType,
} from "aws-cdk-lib/aws-dynamodb";
import { Bucket } from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import * as path from "path";

export interface SharingConstructProps {
  /** The receipts table whose rows may be shared with other users. */
  receiptsTable: Table;
  /** The bucket that stores the receipt images. */
  bucket: Bucket;
}

const VIEWER_INDEX_NAME = "ViewerIndex";

export class SharingConstruct extends Construct {
  public readonly sharesTable: Table;
  public readonly addShareLambda: Function;
  public readonly listSharesLambda: Function;
  public readonly removeShareLambda: Function;
  public readonly listSharedWithMeLambda: Function;
  public readonly getSharedReceiptsLambda: Function;
  public readonly getSharedReceiptSummaryLambda: Function;

  constructor(scope: Construct, id: string, props: SharingConstructProps) {
    super(scope, id);

    const { receiptsTable, bucket } = props;

    this.sharesTable = new Table(this, "SharesTable", {
      partitionKey: { name: "ownerId", type: AttributeType.STRING },
      sortKey: { name: "viewerId", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // Reverse lookup so a viewer can list every owner sharing with them.
    this.sharesTable.addGlobalSecondaryIndex({
      indexName: VIEWER_INDEX_NAME,
      partitionKey: { name: "viewerId", type: AttributeType.STRING },
      projectionType: ProjectionType.ALL,
    });

    const lambdasPath = path.join(__dirname, "lambdas");

    const sharesEnv = {
      SHARES_TABLE_NAME: this.sharesTable.tableName,
      VIEWER_INDEX_NAME,
    };

    const receiptEnv = {
      ...sharesEnv,
      RECEIPTS_TABLE_NAME: receiptsTable.tableName,
      BUCKET_NAME: bucket.bucketName,
    };

    this.addShareLambda = new Function(this, "AddShareLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "addShare.handler",
      code: Code.fromAsset(lambdasPath),
      environment: sharesEnv,
    });
    this.sharesTable.grantWriteData(this.addShareLambda);

    this.listSharesLambda = new Function(this, "ListSharesLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "listShares.handler",
      code: Code.fromAsset(lambdasPath),
      environment: sharesEnv,
    });
    this.sharesTable.grantReadData(this.listSharesLambda);

    this.removeShareLambda = new Function(this, "RemoveShareLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "removeShare.handler",
      code: Code.fromAsset(lambdasPath),
      environment: sharesEnv,
    });
    this.sharesTable.grantWriteData(this.removeShareLambda);

    this.listSharedWithMeLambda = new Function(this, "ListSharedWithMeLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "listSharedWithMe.handler",
      code: Code.fromAsset(lambdasPath),
      environment: sharesEnv,
    });
    this.sharesTable.grantReadData(this.listSharedWithMeLambda);

    this.getSharedReceiptsLambda = new Function(this, "GetSharedReceiptsLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "getSharedReceipts.handler",
      code: Code.fromAsset(lambdasPath),
      environment: receiptEnv,
    });
    this.sharesTable.grantReadData(this.getSharedReceiptsLambda);
    receiptsTable.grantReadData(this.getSharedReceiptsLambda);
    bucket.grantRead(this.getSharedReceiptsLambda);

    this.getSharedReceiptSummaryLambda = new Function(
      this,
      "GetSharedReceiptSummaryLambda",
      {
        runtime: Runtime.PYTHON_3_12,
        handler: "getSharedReceiptSummary.handler",
        code: Code.fromAsset(lambdasPath),
        environment: receiptEnv,
      }
    );
    this.sharesTable.grantReadData(this.getSharedReceiptSummaryLambda);
    receiptsTable.grantReadData(this.getSharedReceiptSummaryLambda);
    bucket.grantRead(this.getSharedReceiptSummaryLambda);
  }
}
