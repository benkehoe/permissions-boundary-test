#! /usr/bin/env python

import argparse
import datetime

import boto3
import aws_assume_role_lib
import aws_error_utils

EMPTY_PARAM = "###NONE###"

KEYS = [
    "RA",
    "PA-RA",
    "BA-PA",
    "BA-RA",
    "BA-PA-RA",
    "BA",
    "PA",
]

def get_stack_info(response):
    stacks = [stack for stack in response["Stacks"] if "DeletionTime" not in stack]
    assert len(stacks) == 1

    stack = stacks[0]

    parameters = {}
    for parameter in stack["Parameters"]:
        parameters[parameter["ParameterKey"]] = parameter["ParameterValue"]
    assert "AssumedRoleSessionArn" in parameters

    outputs = {}
    for output in stack["Outputs"]:
        outputs[output["OutputKey"]] = output["OutputValue"]
    assert "RoleArn" in outputs
    assert "BucketName" in outputs

    return stack, parameters, outputs

def run_test(bucket, keys, body):
    results = []
    for key in keys:
        try:
            bucket.put_object(
                Key=key,
                Body=body,
            )
            results.append((key, True))
        except aws_error_utils.errors.AccessDenied:
            results.append((key, False))
        except aws_error_utils.ClientError as e:
            results.append((key, e))
    return results

def print_results(results):
    max_length = max(len(key) for key, _ in results)
    for key, result in results:
        if isinstance(result, bool):
            result_str = "Allow" if result else "Deny"
        else:
            result_str = str(result)
        print(f"{key.ljust(max_length)} {result_str}")

timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
timestamp_bytes = timestamp.encode()

parser = argparse.ArgumentParser()
parser.add_argument("--profile")
parser.add_argument("--stack-name", default="permissions-boundary-test")

args = parser.parse_args()

with open("template.yaml") as fp:
    template = fp.read()

session = boto3.Session(profile_name=args.profile)

cloudformation = session.client("cloudformation")

try:
    response = cloudformation.describe_stacks(StackName=args.stack_name)
    _, parameters, outputs = get_stack_info(response)
    if parameters["AssumedRoleSessionArn"] != EMPTY_PARAM:
        print("Resetting AssumedRoleSessionArn")
        cloudformation.update_stack(
            StackName=args.stack_name,
            UsePreviousTemplate=True,
            Parameters=[{
                "ParameterKey": "AssumedRoleSessionArn",
                "ParameterValue": EMPTY_PARAM,
            }],
            Capabilities=["CAPABILITY_IAM"],
        )
        print("Update in progress")
        cloudformation.get_waiter("stack_update_complete").wait(StackName=args.stack_name)
        print("Update complete")
except aws_error_utils.errors.ValidationError:
    print("Stack doesn't exist, creating")
    cloudformation.create_stack(
        StackName=args.stack_name,
        TemplateBody=template,
        Capabilities=["CAPABILITY_IAM"],
        OnFailure="DELETE",
    )
    print("Create in progress")
    cloudformation.get_waiter("stack_create_complete").wait(StackName=args.stack_name)
    print("Create complete")

response = cloudformation.describe_stacks(StackName=args.stack_name)
_, _, outputs = get_stack_info(response)

assumed_role_session = aws_assume_role_lib.assume_role(session, outputs["RoleArn"])

response = assumed_role_session.client("sts").get_caller_identity()
assumed_role_session_arn = response["Arn"]

bucket = assumed_role_session.resource("s3").Bucket(outputs["BucketName"])

print("\n\nTesting role as resource policy principal")
results = run_test(bucket, KEYS, timestamp_bytes)

print_results(results)
print("\n")

print(f"Updating stack with assumed role session {assumed_role_session_arn}")
cloudformation.update_stack(
    StackName=args.stack_name,
    UsePreviousTemplate=True,
    Parameters=[{
        "ParameterKey": "AssumedRoleSessionArn",
        "ParameterValue": assumed_role_session_arn
    }],
    Capabilities=["CAPABILITY_IAM"],
)
print("Update in progress")
cloudformation.get_waiter("stack_update_complete").wait(StackName=args.stack_name)
print("Update complete")

print("\n\nTesting assumed role session as resource policy principal")
results = run_test(bucket, KEYS, timestamp_bytes)

print_results(results)
