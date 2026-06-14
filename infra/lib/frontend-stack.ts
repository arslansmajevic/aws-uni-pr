import * as cdk from "aws-cdk-lib/core";
import { Construct } from "constructs";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as path from "path";

export interface FrontendStackProps extends cdk.StackProps {
  apiUrl: string;
}

export class FrontendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    const frontendBucket = new s3.Bucket(this, "FrontendBucket", {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    const distribution = new cloudfront.Distribution(
      this,
      "FrontendDistribution",
      {
        defaultBehavior: {
          origin:
            origins.S3BucketOrigin.withOriginAccessControl(frontendBucket),
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        },
        defaultRootObject: "index.html",
        errorResponses: [
          {
            httpStatus: 404,
            responseHttpStatus: 200,
            responsePagePath: "/index.html",
            ttl: cdk.Duration.seconds(300),
          },
          {
            httpStatus: 403,
            responseHttpStatus: 200,
            responsePagePath: "/index.html",
            ttl: cdk.Duration.seconds(300),
          },
        ],
      },
    );

    new s3deploy.BucketDeployment(this, "DeployFrontend", {
      sources: [
        s3deploy.Source.asset(path.join(__dirname, "../../apps/web/dist")),

        // This file is generated during deployment and contains the real API URL.
        s3deploy.Source.jsonData("config.json", {
          apiUrl: props.apiUrl,
        }),
      ],
      destinationBucket: frontendBucket,
      distribution,
      distributionPaths: ["/*"],
    });

    new cdk.CfnOutput(this, "FrontendUrl", {
      value: `https://${distribution.domainName}`,
      description: "URL of the frontend distribution",
      exportName: "FrontendUrl",
    });
  }
}
