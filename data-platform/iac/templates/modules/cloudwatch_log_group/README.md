# What is this module for?
This module creates following resources:
* CloudWatch log group
* KMS key for encryption of the log group

# How do I use it?
Simple useage:

```hcl
module log_group { 
   source = "../modules/cloudwatch_log_group" 
   name = "/aws/lambda/myfunction
}
```
# Inputs
|Variable name|Required|Description|
|-------------|--------|-----------|
|name|Yes|name of the log group to be created|
|roles|No|List of roles that will be allowed access to log groups KMS key|
|services|No|List of services that will be allowed access to log group's KMS key|
|via_services|No|List of services access through which will be allowed  to log group's KMS key|


# Outputs
|Output|Description|
|---|---|
|arn|ARN of the log group|
|kms_key_arn|ARN of the KMS key created|

# Ignored checkov warnings

None
