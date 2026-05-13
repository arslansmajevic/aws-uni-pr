import { RemovalPolicy } from "aws-cdk-lib";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import {
  Bucket,
  BucketEncryption,
  BlockPublicAccess,
} from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import * as path from "path";

export class StorageConstruct extends Construct {
  public readonly bucket: Bucket;
  public readonly uploadImageLambda: Function;

  public readonly bucketName: string;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.bucket = new Bucket(this, id, {
      bucketName: "receipt-storage-bucket",
      encryption: BucketEncryption.S3_MANAGED,
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    this.bucketName = this.bucket.bucketName;

    this.uploadImageLambda = new Function(this, "UploadImageLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "uploadImage.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        BUCKET_NAME: this.bucket.bucketName,
      },
    });

    this.bucket.grantPut(this.uploadImageLambda);
  }
}
