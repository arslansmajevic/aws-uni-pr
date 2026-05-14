import { RemovalPolicy } from "aws-cdk-lib";
import { CognitoUserPoolsAuthorizer } from "aws-cdk-lib/aws-apigateway";
import { UserPool, UserPoolClient } from "aws-cdk-lib/aws-cognito";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { Bucket, HttpMethods } from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";
import * as path from "path";

export class AuthenticationConstruct extends Construct {
  public readonly userPool: UserPool;
  public readonly userPoolClient: UserPoolClient;
  public readonly authorizer: CognitoUserPoolsAuthorizer;
  public readonly registerLambda: Function;
  public readonly loginLambda: Function;
  public readonly listUsersLambda: Function;
  public readonly refreshTokenLambda: Function;

  constructor(scope: Construct, id: string, postConformationLambda?: Function) {
    super(scope, id);

    this.userPool = new UserPool(this, "UserPool", {
      selfSignUpEnabled: true,
      signInCaseSensitive: false,
      signInAliases: { email: true },
      standardAttributes: {
        givenName: { required: true, mutable: true },
        familyName: { required: true, mutable: true },
      },
      passwordPolicy: {
        minLength: 6,
        requireLowercase: true,
      },
      autoVerify: { email: true },
      lambdaTriggers: postConformationLambda ? { postConfirmation: postConformationLambda } : undefined
    });

    this.userPoolClient = new UserPoolClient(this, "UserPoolClient", {
      userPool: this.userPool,
      generateSecret: false,
      authFlows: {
        userSrp: true,
        userPassword: true,
      },
    });

    this.registerLambda = new Function(this, "RegisterUserLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "registerUser.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.userPool.grant(this.registerLambda, "cognito-idp:SignUp");
    this.userPool.grant(this.registerLambda, "cognito-idp:AdminCreateUser");
    this.userPool.grant(this.registerLambda, "cognito-idp:AdminConfirmSignUp");

    this.loginLambda = new Function(this, "LoginUserLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "loginUser.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.userPool.grant(this.loginLambda, "cognito-idp:InitiateAuth");

    this.listUsersLambda = new Function(this, "ListUsersLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "listUsers.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
      },
    });

    this.refreshTokenLambda = new Function(this, "RefreshTokenLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "refreshToken.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.userPool.grant(this.refreshTokenLambda, "cognito-idp:InitiateAuth");

    // 1. Create the Authorizer
    // used for checking JWT tokens in API Gateway
    this.authorizer = new CognitoUserPoolsAuthorizer(
      this,
      "CognitoAuthorizer",
      {
        cognitoUserPools: [this.userPool],
      },
    );

    this.userPool.grant(this.listUsersLambda, "cognito-idp:ListUsers");
  }
}
