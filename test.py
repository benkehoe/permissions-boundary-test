#! /usr/bin/env python

import argparse
import datetime

import boto3
import aws_assume_role_lib
import aws_error_utils

timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
timestamp_bytes = timestamp.encode()

parser = argparse.ArgumentParser()
parser.add_argument("--profile")
parser.add_argument("--stack-name", default="permissions-boundary-test")

args = parser.parse_args()

session = boto3.Session(profile_name=args.profile)

cloudformation = session.client("cloudformation")

response = cloudformation.describe_stacks(StackName=args.stack_name)

stacks = [stack for stack in response["Stacks"] if "DeletionTime" not in stack]
assert len(stacks) == 1

stack = stacks[0]

params = {}
for output in stack["Outputs"]:
    params[output["OutputKey"]] = output["OutputValue"]
assert "RoleArn" in params
assert "BucketName" in params

assumed_role_session = aws_assume_role_lib.assume_role(session, params["RoleArn"])

bucket = assumed_role_session.resource("s3").Bucket(params["BucketName"])

keys = [
    "RA",
    "BA-PA",
    "BA-RA",
    "BA-PA-RA",
    "BA",
    "PA",
    "PA-RA",
]
max_length = max(len(key) for key in keys)

results = []

for key in keys:
    try:
        bucket.put_object(
            Key=key,
            Body=timestamp_bytes,
        )
        results.append((key, True))
    except aws_error_utils.errors.AccessDenied:
        results.append((key, False))
    except aws_error_utils.ClientError as e:
        results.append((key, e))

for key, result in results:
    if isinstance(result, bool):
        result_str = "Allow" if result else "Deny"
    else:
        result_str = str(result)
    print(f"{key.ljust(max_length)} {result_str}")
