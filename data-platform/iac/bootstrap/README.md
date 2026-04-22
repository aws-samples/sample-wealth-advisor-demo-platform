This directory contains scripts that are required to be run before
the IaC can be deployed.

* `parameters.json` - contains Terraform back end CloudFormation stack parameters to perform initial setup in the primary region
* `parameters-crr.json` - contains Terraform back end CloudFormation stack parameters to perform final setup in the primary region
* `parameters-secondary.json` - contains Terraform back end CloudFormation stack parameters to perform complete setup in the secondary region