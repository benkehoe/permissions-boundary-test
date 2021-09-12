The flowchart from the AWS IAM [policy evaluation documentation page](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html), as of 2021-09-21, and dating back to at least [2018-12-27](https://web.archive.org/web/20181227013421/https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html), is the following:
![Flowchart](policy-evaluation-flowchart-20210912.png)

The flowchart indicates that an Allow in a resource policy causes a final decision of Allow, before permissions boundaries have a chance to cause an implicit Deny.
This would mean a resource policy could unilaterally grant access to a principal, circumventing its permissions boundary.
However, a test of this shows this to be incorrect.

For an IAM role with a permissions boundary, role policy, and resource policy, none with any `Deny`s, the possible combinations of `Allow`s in the policy have the following results:

Permissions Boundary | Role Policy | Resource Policy | Result
--- | --- | --- | ---
\- | - | Allow | **Deny**
Allow | Allow | - | Allow
Allow | - | Allow | Allow
Allow | Allow | Allow | Allow
Allow | - | - | Deny
\- | Allow | - | Deny
\- | Allow | Allow | Deny

The code in this repo verifies this.

```
> pipenv install
> ./deploy.sh
> ./test.sh
RA       Deny
BA-PA    Allow
BA-RA    Allow
BA-PA-RA Allow
BA       Deny
PA       Deny
PA-RA    Deny
```

`deploy.sh` will set up a stack named `permissions-boundary-test` with a role, and managed policy (for the role's permissions boundary), and an S3 bucket.
`test.py` will run tests against this stack.
Use `--profile` on `test.py` to make it use a config profile.
