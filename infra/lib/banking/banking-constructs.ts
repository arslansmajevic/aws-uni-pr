import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";
import * as path from "path";
import * as cdk from "aws-cdk-lib";

export class BankingConstruct extends Construct {
  public readonly createLinkTokenLambda: Function;
  public readonly exchangeTokenLambda: Function;
  public readonly disconnectBankLambda: Function;
  public readonly getBankStatusLambda: Function;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.createLinkTokenLambda = new Function(this, "CreateLinkTokenLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "createLinkToken.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
    });

    this.createLinkTokenLambda.addToRolePolicy(new PolicyStatement({
      actions: ["secretsmanager:GetSecretValue"],
      resources: [
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/credentials*`,
      ],
    }));

    this.exchangeTokenLambda = new Function(this, "ExchangeTokenLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "exchangeToken.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
    });

    this.exchangeTokenLambda.addToRolePolicy(new PolicyStatement({
      actions: [
        "secretsmanager:GetSecretValue",
        "secretsmanager:CreateSecret",
        "secretsmanager:UpdateSecret",
      ],
      resources: [
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/*`,
      ],
    }));

    this.disconnectBankLambda = new Function(this, "DisconnectBankLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "disconnectBank.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
    });

    this.disconnectBankLambda.addToRolePolicy(new PolicyStatement({
      actions: ["secretsmanager:DeleteSecret"],
      resources: [
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/access-token/*`,
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/credentials/*`,
      ],
    }));

    this.getBankStatusLambda = new Function(this, "GetBankStatusLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "getBankStatus.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
    });

    this.getBankStatusLambda.addToRolePolicy(new PolicyStatement({
      actions: ["secretsmanager:DescribeSecret"],
      resources: [
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/access-token/*`,
        `arn:aws:secretsmanager:${cdk.Stack.of(this).region}:${cdk.Stack.of(this).account}:secret:plaid/credentials/*`,
      ],
    }));
  }
}