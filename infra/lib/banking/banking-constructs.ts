import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";
import * as path from "path";

export class BankingConstruct extends Construct {
  public readonly createLinkTokenLambda: Function;
  public readonly exchangeTokenLambda: Function;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.createLinkTokenLambda = new Function(this, "CreateLinkTokenLambda", {
      runtime: Runtime.PYTHON_3_12,
      handler: "createLinkToken.handler",
      code: Code.fromAsset(path.join(__dirname, "lambdas")),
    });

    this.createLinkTokenLambda.addToRolePolicy(new PolicyStatement({
      actions: ["secretsmanager:GetSecretValue"],
      resources: ["*"],
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
      resources: ["*"],
    }));
  }
}