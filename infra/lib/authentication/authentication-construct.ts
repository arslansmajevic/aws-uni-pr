import { RemovalPolicy } from "aws-cdk-lib";
import { CognitoUserPoolsAuthorizer } from "aws-cdk-lib/aws-apigateway";
import { UserPool, UserPoolClient } from "aws-cdk-lib/aws-cognito";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { Bucket, HttpMethods } from "aws-cdk-lib/aws-s3";
import { PolicyStatement } from "aws-cdk-lib/aws-iam"; 
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
  public readonly changePasswordLambda: Function;
public readonly forgotPasswordLambda: Function;
public readonly confirmForgotPasswordLambda: Function;

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

    this.registerLambda.addToRolePolicy(new PolicyStatement({
      actions: [
        "cognito-idp:SignUp",
        "cognito-idp:AdminCreateUser",
        "cognito-idp:AdminConfirmSignUp",
        "cognito-idp:AdminUpdateUserAttributes",
      ],
      resources: [this.userPool.userPoolArn],
    }));


    this.loginLambda = new Function(this, "LoginUserLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "loginUser.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.loginLambda.addToRolePolicy(new PolicyStatement({
      actions: ["cognito-idp:InitiateAuth"],
      resources: [this.userPool.userPoolArn],
    }));

    this.listUsersLambda = new Function(this, "ListUsersLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "listUsers.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
      },
    });

    this.listUsersLambda.addToRolePolicy(new PolicyStatement({
      actions: ["cognito-idp:ListUsers"],
      resources: [this.userPool.userPoolArn],
    }));

    this.refreshTokenLambda = new Function(this, "RefreshTokenLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "refreshToken.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.refreshTokenLambda.addToRolePolicy(new PolicyStatement({
      actions: ["cognito-idp:InitiateAuth"],
      resources: [this.userPool.userPoolArn],
    }));

    this.authorizer = new CognitoUserPoolsAuthorizer(this, "CognitoAuthorizer", {
      cognitoUserPools: [this.userPool],
      identitySource: "method.request.header.Authorization",
    });

    this.changePasswordLambda = new Function(this, "ChangePasswordLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "changePassword.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
    });

    this.changePasswordLambda.addToRolePolicy(new PolicyStatement({
      actions: ["cognito-idp:ChangePassword"],
      resources: ["*"],
    }));

    this.forgotPasswordLambda = new Function(this, "ForgotPasswordLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "forgotPassword.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.forgotPasswordLambda.addToRolePolicy(new PolicyStatement({
      actions: ["cognito-idp:ForgotPassword"],
      resources: ["*"],
    }));

    this.confirmForgotPasswordLambda = new Function(this, "ConfirmForgotPasswordLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "confirmForgotPassword.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
      environment: {
        CLIENT_ID: this.userPoolClient.userPoolClientId,
      },
    });

    this.confirmForgotPasswordLambda.addToRolePolicy(new PolicyStatement({
      actions: ["cognito-idp:ConfirmForgotPassword"],
      resources: ["*"],
    }));
  }
}
