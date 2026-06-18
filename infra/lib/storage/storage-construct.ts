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
import * as sfn from "aws-cdk-lib/aws-stepfunctions";
import * as tasks from "aws-cdk-lib/aws-stepfunctions-tasks";

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

    // --- Receipt Processing Pipeline (Step Functions) ---

    const pipelineLambdasPath = path.join(__dirname, "lambdas", "pipeline");

    const extractOcrLambda = new Function(this, "ExtractOcrLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "extract_ocr.handler",
      code: Code.fromAsset(pipelineLambdasPath),
      timeout: Duration.seconds(60),
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
        BEDROCK_MODEL_ID: "eu.amazon.nova-pro-v1:0",
      },
    });

    const normalizeLambda = new Function(this, "NormalizeLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "normalize.handler",
      code: Code.fromAsset(pipelineLambdasPath),
      timeout: Duration.seconds(30),
      environment: {
        BEDROCK_MODEL_ID: "eu.amazon.nova-pro-v1:0",
      },
    });

    const validateLambda = new Function(this, "ValidateLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "validate.handler",
      code: Code.fromAsset(pipelineLambdasPath),
      timeout: Duration.seconds(10),
    });

    const saveLambda = new Function(this, "SaveLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "save.handler",
      code: Code.fromAsset(pipelineLambdasPath),
      timeout: Duration.seconds(10),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const errorHandlerLambda = new Function(this, "ErrorHandlerLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "error_handler.handler",
      code: Code.fromAsset(pipelineLambdasPath),
      timeout: Duration.seconds(10),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
      },
    });

    // Permissions for pipeline Lambdas
    this.bucket.grantRead(extractOcrLambda);
    this.bucket.grantPut(extractOcrLambda);
    this.bucket.grantPut(saveLambda);
    this.receiptsTable.grantWriteData(saveLambda);
    this.receiptsTable.grantWriteData(errorHandlerLambda);

    const bedrockRegion = "eu-central-1";
    const account = cdk.Stack.of(this).account;

    extractOcrLambda.addToRolePolicy(
      new PolicyStatement({
        actions: ["bedrock:InvokeModel*"],
        resources: [
          `arn:aws:bedrock:${bedrockRegion}:${account}:inference-profile/eu.amazon.nova-pro-v1:0`,
          `arn:aws:bedrock:eu-central-1::foundation-model/*`,
          `arn:aws:bedrock:eu-north-1::foundation-model/*`,
          `arn:aws:bedrock:eu-west-1::foundation-model/*`,
          `arn:aws:bedrock:eu-west-3::foundation-model/*`,
        ],
      })
    );

    normalizeLambda.addToRolePolicy(
      new PolicyStatement({
        actions: ["bedrock:InvokeModel*"],
        resources: [
          `arn:aws:bedrock:${bedrockRegion}:${account}:inference-profile/eu.amazon.nova-pro-v1:0`,
          `arn:aws:bedrock:eu-central-1::foundation-model/*`,
          `arn:aws:bedrock:eu-north-1::foundation-model/*`,
          `arn:aws:bedrock:eu-west-1::foundation-model/*`,
          `arn:aws:bedrock:eu-west-3::foundation-model/*`,
        ],
      })
    );

    // Step Functions state machine definition
    const extractTask = new tasks.LambdaInvoke(this, "ExtractOCR", {
      lambdaFunction: extractOcrLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    extractTask.addRetry({
      errors: ["States.TaskFailed"],
      interval: Duration.seconds(5),
      maxAttempts: 2,
      backoffRate: 2,
    });

    const normalizeTask = new tasks.LambdaInvoke(this, "NormalizeData", {
      lambdaFunction: normalizeLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    normalizeTask.addRetry({
      errors: ["States.TaskFailed"],
      interval: Duration.seconds(3),
      maxAttempts: 2,
      backoffRate: 2,
    });

    const validateTask = new tasks.LambdaInvoke(this, "ValidateData", {
      lambdaFunction: validateLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });

    const saveTask = new tasks.LambdaInvoke(this, "SaveReceipt", {
      lambdaFunction: saveLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });

    const handleError = new tasks.LambdaInvoke(this, "HandleError", {
      lambdaFunction: errorHandlerLambda,
      outputPath: "$.Payload",
    });

    // Wire error handling: each stage catches errors and routes to handler
    const errorCatchProps: sfn.CatchProps = {
      resultPath: "$.error",
    };

    const addErrorInfo = (stageName: string) =>
      new sfn.Pass(this, `PrepError_${stageName}`, {
        parameters: {
          "userId.$": "$.userId",
          "receiptId.$": "$.receiptId",
          "error.$": "$.error",
          failedStage: stageName,
        },
      });

    const extractErrorPass = addErrorInfo("ExtractOCR");
    const normalizeErrorPass = addErrorInfo("Normalize");
    const validateErrorPass = addErrorInfo("Validate");
    const saveErrorPass = addErrorInfo("Save");

    extractErrorPass.next(handleError);
    normalizeErrorPass.next(handleError);
    validateErrorPass.next(handleError);
    saveErrorPass.next(handleError);

    extractTask.addCatch(extractErrorPass, errorCatchProps);
    normalizeTask.addCatch(normalizeErrorPass, errorCatchProps);
    validateTask.addCatch(validateErrorPass, errorCatchProps);
    saveTask.addCatch(saveErrorPass, errorCatchProps);

    const definition = extractTask
      .next(normalizeTask)
      .next(validateTask)
      .next(saveTask);

    const stateMachine = new sfn.StateMachine(
      this,
      "ReceiptProcessingPipeline",
      {
        definitionBody: sfn.DefinitionBody.fromChainable(definition),
        timeout: Duration.minutes(5),
        tracingEnabled: true,
      }
    );

    // Trigger Lambda: S3 event -> starts Step Function
    const triggerLambda = new Function(this, "PipelineTriggerLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "trigger.handler",
      code: Code.fromAsset(pipelineLambdasPath),
      timeout: Duration.seconds(10),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        STATE_MACHINE_ARN: stateMachine.stateMachineArn,
      },
    });

    stateMachine.grantStartExecution(triggerLambda);
    this.receiptsTable.grantWriteData(triggerLambda);
    this.bucket.grantRead(triggerLambda);

    this.bucket.addEventNotification(
      EventType.OBJECT_CREATED,
      new LambdaDestination(triggerLambda),
      { prefix: "uploads/" }
    );

    // --- End Pipeline ---

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

    this.getReceiptsSummaryLambda = new Function(
      this,
      "GetReceiptsSummaryLambda",
      {
        runtime: Runtime.PYTHON_3_12,
        handler: "getReceiptsSummary.handler",
        code: Code.fromAsset(path.join(__dirname, "lambdas")),
        environment: {
          RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        },
      }
    );
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
      }
    );

    this.receiptsTable.grantReadData(this.getReceiptDetailedSummaryLambda);
    this.bucket.grantRead(this.getReceiptDetailedSummaryLambda, "uploads/*");
  }
}