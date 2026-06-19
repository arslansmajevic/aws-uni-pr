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
          id: "ExpireUploads",
          enabled: true,
          expiration: Duration.days(90),
          prefix: "uploads/",
        },
        {
          id: "ExpireNormalizedInputs",
          enabled: true,
          expiration: Duration.days(90),
          prefix: "normalized-inputs/",
        },
        {
          id: "ExpireRawExtractions",
          enabled: true,
          expiration: Duration.days(90),
          prefix: "raw-extractions/",
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

    // -------------------------------------------------------------------------
    // Receipt Processing Pipeline (Step Functions — Textract-first architecture)
    // -------------------------------------------------------------------------

    const pipelinePath = path.join(__dirname, "lambdas", "pipeline");
    const bedrockRegion = "eu-central-1";
    const account = cdk.Stack.of(this).account;

    // --- Lambdas ---

    const triggerLambda = new Function(this, "PipelineTriggerLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "trigger.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(15),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        STATE_MACHINE_ARN: "PLACEHOLDER", // replaced after state machine creation
      },
    });

    const preflightLambda = new Function(this, "PreflightLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "preflight.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(30),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const analyzeExpenseLambda = new Function(this, "AnalyzeExpenseLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "extract_textract.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(60),
      memorySize: 512,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const normalizeLambda = new Function(this, "NormalizeLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "normalize.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(60),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const validateLambda = new Function(this, "ValidateLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "validate.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(30),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const analyzeDocumentFallbackLambda = new Function(
      this,
      "AnalyzeDocumentFallbackLambda",
      {
        runtime: Runtime.PYTHON_3_12,
        handler: "extract_layout.handler",
        code: Code.fromAsset(pipelinePath),
        timeout: Duration.seconds(120),
        memorySize: 512,
        environment: {
          BUCKET_NAME: this.bucket.bucketName,
        },
      }
    );

    const repairItemsLambda = new Function(this, "RepairItemsLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "repair_items.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(120),
      memorySize: 512,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
        REPAIR_MODEL_ID: "eu.amazon.nova-pro-v1:0",
      },
    });

    const mergeRepairLambda = new Function(this, "MergeRepairLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "merge_repair.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(30),
      memorySize: 256,
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const saveLambda = new Function(this, "SaveLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "save.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(30),
      memorySize: 256,
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    const errorHandlerLambda = new Function(this, "ErrorHandlerLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "error_handler.handler",
      code: Code.fromAsset(pipelinePath),
      timeout: Duration.seconds(15),
      environment: {
        RECEIPTS_TABLE_NAME: this.receiptsTable.tableName,
      },
    });

    // --- S3 permissions ---

    // Trigger: read the uploaded file (for ETag in idempotency).
    this.bucket.grantRead(triggerLambda);

    // Preflight: read original upload, write to normalized-inputs/.
    this.bucket.grantRead(preflightLambda);
    this.bucket.grantPut(preflightLambda);

    // AnalyzeExpense: read normalized input, write raw-extractions/.
    this.bucket.grantRead(analyzeExpenseLambda);
    this.bucket.grantPut(analyzeExpenseLambda);

    // Normalize: read raw-extractions/, write normalized.json.
    this.bucket.grantRead(normalizeLambda);
    this.bucket.grantPut(normalizeLambda);

    // Validate: read raw-extractions/, write validation.json.
    this.bucket.grantRead(validateLambda);
    this.bucket.grantPut(validateLambda);

    // AnalyzeDocumentFallback: read normalized input, write layout.json.
    this.bucket.grantRead(analyzeDocumentFallbackLambda);
    this.bucket.grantPut(analyzeDocumentFallbackLambda);

    // RepairItems: read image + textract + layout + normalized, write repair.json.
    this.bucket.grantRead(repairItemsLambda);
    this.bucket.grantPut(repairItemsLambda);

    // MergeRepair: read + write normalized.json and repair audit.
    this.bucket.grantRead(mergeRepairLambda);
    this.bucket.grantPut(mergeRepairLambda);

    // Save: read normalized + validation, write any remaining artifacts.
    this.bucket.grantRead(saveLambda);
    this.bucket.grantPut(saveLambda);

    // --- DynamoDB permissions ---
    this.receiptsTable.grantWriteData(triggerLambda);
    this.receiptsTable.grantWriteData(saveLambda);
    this.receiptsTable.grantWriteData(errorHandlerLambda);

    // --- Textract permissions ---
    const textractAnalyzeExpensePolicy = new PolicyStatement({
      actions: ["textract:AnalyzeExpense"],
      resources: ["*"],
    });
    const textractAnalyzeDocumentPolicy = new PolicyStatement({
      actions: ["textract:AnalyzeDocument"],
      resources: ["*"],
    });
    analyzeExpenseLambda.addToRolePolicy(textractAnalyzeExpensePolicy);
    analyzeDocumentFallbackLambda.addToRolePolicy(textractAnalyzeDocumentPolicy);

    // --- Bedrock permissions (repair Lambda only) ---
    repairItemsLambda.addToRolePolicy(
      new PolicyStatement({
        actions: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources: [
          `arn:aws:bedrock:${bedrockRegion}:${account}:inference-profile/eu.amazon.nova-pro-v1:0`,
          `arn:aws:bedrock:${bedrockRegion}::foundation-model/*`,
          `arn:aws:bedrock:eu-north-1::foundation-model/*`,
          `arn:aws:bedrock:eu-west-1::foundation-model/*`,
          `arn:aws:bedrock:eu-west-3::foundation-model/*`,
        ],
      })
    );

    // -------------------------------------------------------------------------
    // Step Functions: Textract-first pipeline with repair branch
    // -------------------------------------------------------------------------

    const errorCatchProps: sfn.CatchProps = { resultPath: "$.error" };

    const addErrorInfo = (stageName: string) =>
      new sfn.Pass(this, `PrepError_${stageName}`, {
        parameters: {
          "userId.$": "$.userId",
          "receiptId.$": "$.receiptId",
          "error.$": "$.error",
          failedStage: stageName,
        },
      });

    const handleErrorTask = new tasks.LambdaInvoke(this, "HandleError", {
      lambdaFunction: errorHandlerLambda,
      outputPath: "$.Payload",
    });

    // Wire error pass states → handleError.
    const stageNames = [
      "Preflight", "AnalyzeExpense", "Normalize",
      "Validate", "AnalyzeDocumentFallback", "RepairItems",
      "MergeRepair", "ValidateAfterRepair", "Save",
    ];
    const errorPasses: Record<string, sfn.Pass> = {};
    stageNames.forEach((name) => {
      const pass = addErrorInfo(name);
      pass.next(handleErrorTask);
      errorPasses[name] = pass;
    });

    // --- Primary pipeline tasks ---

    const preflightTask = new tasks.LambdaInvoke(this, "Preflight", {
      lambdaFunction: preflightLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: false,
    });
    preflightTask.addRetry({ errors: ["States.TaskFailed"], interval: Duration.seconds(2), maxAttempts: 1, backoffRate: 1 });
    preflightTask.addCatch(errorPasses["Preflight"], errorCatchProps);

    const analyzeExpenseTask = new tasks.LambdaInvoke(this, "AnalyzeExpense", {
      lambdaFunction: analyzeExpenseLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    analyzeExpenseTask.addRetry({
      errors: ["States.TaskFailed"],
      interval: Duration.seconds(5),
      maxAttempts: 2,
      backoffRate: 2,
    });
    analyzeExpenseTask.addCatch(errorPasses["AnalyzeExpense"], errorCatchProps);

    const normalizeTask = new tasks.LambdaInvoke(this, "NormalizeData", {
      lambdaFunction: normalizeLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    normalizeTask.addRetry({ errors: ["States.TaskFailed"], interval: Duration.seconds(3), maxAttempts: 2, backoffRate: 2 });
    normalizeTask.addCatch(errorPasses["Normalize"], errorCatchProps);

    const validateTask = new tasks.LambdaInvoke(this, "ValidateData", {
      lambdaFunction: validateLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    validateTask.addCatch(errorPasses["Validate"], errorCatchProps);

    const saveTask = new tasks.LambdaInvoke(this, "SaveReceipt", {
      lambdaFunction: saveLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    saveTask.addRetry({ errors: ["States.TaskFailed"], interval: Duration.seconds(3), maxAttempts: 2, backoffRate: 2 });
    saveTask.addCatch(errorPasses["Save"], errorCatchProps);

    // --- Repair branch tasks ---

    const analyzeDocumentFallbackTask = new tasks.LambdaInvoke(
      this,
      "AnalyzeDocumentFallback",
      {
        lambdaFunction: analyzeDocumentFallbackLambda,
        outputPath: "$.Payload",
        retryOnServiceExceptions: true,
      }
    );
    analyzeDocumentFallbackTask.addRetry({ errors: ["States.TaskFailed"], interval: Duration.seconds(5), maxAttempts: 2, backoffRate: 2 });
    analyzeDocumentFallbackTask.addCatch(errorPasses["AnalyzeDocumentFallback"], errorCatchProps);

    const repairItemsTask = new tasks.LambdaInvoke(this, "RepairItems", {
      lambdaFunction: repairItemsLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    repairItemsTask.addRetry({ errors: ["States.TaskFailed"], interval: Duration.seconds(5), maxAttempts: 1, backoffRate: 2 });
    repairItemsTask.addCatch(errorPasses["RepairItems"], errorCatchProps);

    const mergeRepairTask = new tasks.LambdaInvoke(this, "MergeRepair", {
      lambdaFunction: mergeRepairLambda,
      outputPath: "$.Payload",
      retryOnServiceExceptions: true,
    });
    mergeRepairTask.addRetry({ errors: ["States.TaskFailed"], interval: Duration.seconds(3), maxAttempts: 2, backoffRate: 2 });
    mergeRepairTask.addCatch(errorPasses["MergeRepair"], errorCatchProps);

    const validateAfterRepairTask = new tasks.LambdaInvoke(
      this,
      "ValidateAfterRepair",
      {
        lambdaFunction: validateLambda,
        outputPath: "$.Payload",
        retryOnServiceExceptions: true,
      }
    );
    validateAfterRepairTask.addCatch(errorPasses["ValidateAfterRepair"], errorCatchProps);

    // --- Repair branch chain ---
    const repairBranch = analyzeDocumentFallbackTask
      .next(repairItemsTask)
      .next(mergeRepairTask)
      .next(validateAfterRepairTask)
      .next(saveTask);

    // --- Choice: repair required? ---
    const repairChoice = new sfn.Choice(this, "RepairRequired?")
      .when(
        sfn.Condition.booleanEquals("$.repairRequired", true),
        repairBranch
      )
      .otherwise(saveTask);

    // --- Full pipeline definition ---
    const definition = preflightTask
      .next(analyzeExpenseTask)
      .next(normalizeTask)
      .next(validateTask)
      .next(repairChoice);

    const stateMachine = new sfn.StateMachine(
      this,
      "ReceiptProcessingPipeline",
      {
        definitionBody: sfn.DefinitionBody.fromChainable(definition),
        timeout: Duration.minutes(10),
        tracingEnabled: true,
      }
    );

    // Grant trigger Lambda permission to start executions.
    stateMachine.grantStartExecution(triggerLambda);

    // Inject the real state machine ARN (avoids circular reference).
    triggerLambda.addEnvironment(
      "STATE_MACHINE_ARN",
      stateMachine.stateMachineArn
    );

    this.bucket.addEventNotification(
      EventType.OBJECT_CREATED,
      new LambdaDestination(triggerLambda),
      { prefix: "uploads/" }
    );

    // -------------------------------------------------------------------------
    // Query / read-side Lambdas (unchanged)
    // -------------------------------------------------------------------------

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
