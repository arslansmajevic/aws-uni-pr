import {
  AuthorizationType,
  CognitoUserPoolsAuthorizer,
  Integration,
  LambdaIntegration,
  Method,
  MethodOptions,
  RestApi,
  IResource,
} from "aws-cdk-lib/aws-apigateway";
import { Function as LambdaFunction } from "aws-cdk-lib/aws-lambda";
import { Construct } from "constructs";
import * as cdk from "aws-cdk-lib/core";

export interface LambdaRouteConfig {
  function: LambdaFunction;
  method: string;
  resourcePath: string;
  jwtRequired?: boolean;
}

export class GatewayConstruct extends Construct {
  public readonly apiId: string;
  public readonly api: RestApi;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.api = new RestApi(this, "Gateway", {
      restApiName: "Backend gateway",
      description: "API for the backend services",
      defaultCorsPreflightOptions: {
        allowOrigins: ["*"],
        allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"],
        allowCredentials: false,
      },
    });

    this.apiId = this.api.restApiId;
  }

  public addRoute(
    path: string,
    method: string,
    integration: Integration,
    options?: MethodOptions,
  ): Method {
    const resource = this.getOrCreateResource(path);
    return resource.addMethod(method, integration, options);
  }

  public addLambdaRoutes(
    lambdaFunctions: LambdaRouteConfig[],
    authorizer?: CognitoUserPoolsAuthorizer,
  ): void {
    const resourcesByPath: Record<string, IResource> = {};

    for (const lambdaFunction of lambdaFunctions) {
      const cleanPath = this.cleanPath(lambdaFunction.resourcePath);

      let resource = resourcesByPath[cleanPath];

      if (!resource) {
        resource = this.getOrCreateResource(cleanPath);
        resourcesByPath[cleanPath] = resource;
      }

      const methodOptions: MethodOptions | undefined =
        lambdaFunction.jwtRequired
          ? {
              authorizer,
              authorizationType: AuthorizationType.COGNITO,
            }
          : undefined;

      if (lambdaFunction.jwtRequired && !authorizer) {
        throw new Error(
          `Route "${lambdaFunction.method} /${cleanPath}" requires JWT, but no authorizer was provided.`,
        );
      }

      resource.addMethod(
        lambdaFunction.method,
        new LambdaIntegration(lambdaFunction.function),
        methodOptions,
      );
      
    }
  }

  private getOrCreateResource(path: string): IResource {
    const cleanPath = this.cleanPath(path);
    const parts = cleanPath.split("/").filter(Boolean);

    let resource: IResource = this.api.root;

    for (const part of parts) {
      resource = resource.getResource(part) ?? resource.addResource(part);
    }

    return resource;
  }

  private cleanPath(path: string): string {
    return path.replace(/^\/+|\/+$/g, "");
  }
}
