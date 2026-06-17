#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { InfraStack } from "../lib/infra-stack";
import { FrontendStack } from "../lib/frontend-stack";

const app = new cdk.App();

const infraStack = new InfraStack(app, "InfraStack", {
  env: {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: "eu-central-1",
  },
});

const frontendStack = new FrontendStack(app, "FrontendStack", {
  env: {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: "eu-central-1",
  },
  apiUrl: infraStack.apiUrl,
});

frontendStack.addDependency(infraStack);
