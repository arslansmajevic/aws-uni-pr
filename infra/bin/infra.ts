#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { InfraStack } from "../lib/infra-stack";
import { FrontendStack } from "../lib/frontend-stack";

const app = new cdk.App();

const infraStack = new InfraStack(app, "InfraStack", {
  env: {
    account: "000000000000",
    region: "us-east-1",
  },
});

const frontendStack = new FrontendStack(app, "FrontendStack", {
  env: {
    account: "000000000000",
    region: "us-east-1",
  },
  apiUrl: infraStack.apiUrl,
});

frontendStack.addDependency(infraStack);
