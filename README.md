**Read the [accompanying article](https://ben11kehoe.medium.com/aws-iam-permission-boundaries-has-a-caveat-that-may-surprise-you-2e8cbad2883a).**

The flowchart from the AWS IAM [policy evaluation documentation page](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html), as of 2021-09-12, and dating back to at least [2018-12-27](https://web.archive.org/web/20181227013421/https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html), is the following:

![Flowchart](policy-evaluation-flowchart-20210912.png)

The flowchart indicates that an Allow in a resource policy causes a final decision of Allow, before permissions boundaries have a chance to cause an implicit Deny.
This would mean a resource policy could unilaterally grant access to a principal, circumventing its permissions boundary.
However, this is only partially correct.

Resource policies cannot unilaterally grant access to an IAM *role* but *can* unilaterally grant access to *particular role sessions*, that is, the thing that is created by calling `AssumeRole`. This is mentioned in the docs [here](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html#access_policies_boundaries-eval-logic), illustrated with the following diagram, though this information is excluded from subsequent diagrams about SCPs and session policies.

![VennDiagram](venn-diagram-20210912.png)

This is true for assumed role sessions created with `AssumeRole` (and presumably `AssumeRoleWithSAML` and `AssumeRoleWithWebIdentity`), where the principal in the resource policy is the assumed role session ARN, which is retrievable through the `GetCallerIdentity` API, which does not require permissions.

This also applies "federated users" but this does *not* mean an assumed role session using `AssumeRoleWithSAML` with a federated identity provider; it refers to sessions created with [`GetFederationToken`](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetFederationToken.html) using IAM User credentials.
Note that the usage of "federated user" is inconsistent in the IAM documentation, used to refer to both kinds of federation.

## Verification

For an IAM role with a permissions boundary, role policy, and resource policy, none with any `Deny`s, the possible combinations of `Allow`s in the policy have the following results:

### Role as resource policy principal
Permissions Boundary | Role Policy | Resource Policy | Result
--- | --- | --- | ---
\- | - | Allow | **Deny**
\- | Allow | Allow | **Deny**
Allow | Allow | - | Allow
Allow | - | Allow | Allow
Allow | Allow | Allow | Allow
Allow | - | - | Deny
\- | Allow | - | Deny

### Assumed role session as resource policy principal
Permissions Boundary | Role Policy | Resource Policy | Result
--- | --- | --- | ---
\- | - | Allow | **Allow**
\- | Allow | Allow | **Allow**
Allow | Allow | - | Allow
Allow | - | Allow | Allow
Allow | Allow | Allow | Allow
Allow | - | - | Deny
\- | Allow | - | Deny

### Account as resource policy principal, with role in `aws:PrincipalArn` condition
Permissions Boundary | Role Policy | Resource Policy | Result
--- | --- | --- | ---
\- | - | Allow | **Deny**
\- | Allow | Allow | **Deny**
Allow | Allow | - | Allow
Allow | - | Allow | **Deny**
Allow | Allow | Allow | Allow
Allow | - | - | Deny
\- | Allow | - | Deny

### "*" as resource policy principal, with role in `aws:PrincipalArn` condition
Permissions Boundary | Role Policy | Resource Policy | Result
--- | --- | --- | ---
\- | - | Allow | **Allow**
\- | Allow | Allow | **Allow**
Allow | Allow | - | Allow
Allow | - | Allow | **Allow**
Allow | Allow | Allow | Allow
Allow | - | - | Deny
\- | Allow | - | Deny

The code in this repo verifies this.

Install [pipenv](https://pipenv.pypa.io/en/latest/) if you haven't got it.
Run `pipenv install` and then `test.py`.
Use `--profile` on `test.py` to make it use a config profile.

This will create a stack named `permissions-boundary-test` with a role, and managed policy (for the role's permissions boundary), and an S3 bucket.
It will run the tests against the stack using the role as the principal in the bucket policy, and then create an assumed role session, update the stack to use the assumed role session as the principal in the bucket policy, and run the tests.
