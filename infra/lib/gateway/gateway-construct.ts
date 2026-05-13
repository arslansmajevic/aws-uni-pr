import { Integration, Method, MethodOptions, RestApi } from "aws-cdk-lib/aws-apigateway";
import { Construct } from "constructs";

export class GatewayConstruct extends Construct {
  public readonly apiId: string;
  public readonly api: RestApi;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.api = new RestApi(this, "Gateway", {
      restApiName: "Backend gateway",
      description: "API for the backend services",
      //   deployOptions: {
      //     stageName: "prod",
      //   },
      defaultCorsPreflightOptions: {
        allowOrigins: ["*"],
        allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
        allowCredentials: false,
      },
    });
  }

  public addRoute(
    path: string,
    method: string,
    integration: Integration,
    options?: MethodOptions,
  ): Method {
    const cleanPath = path.replace(/^\/+|\/+$/g, "");
    const parts = cleanPath.split("/").filter(Boolean);

    let resource = this.api.root;

    for (const part of parts) {
      resource = resource.getResource(part) ?? resource.addResource(part);
    }

    return resource.addMethod(method, integration, options);
  }
}
