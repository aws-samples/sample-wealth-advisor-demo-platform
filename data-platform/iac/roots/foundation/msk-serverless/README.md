# What is this module for?
This module creates following resources:
* MSK cluster
* Cluster nodes
* Cloudwatch log group
* KMS keys for encryption of cluster data and logs

# How do I use it?
Simple useage:

```hcl
module "msk" {
  source             = "../modules/msk-serverless"
  cluster_name       = "test"
  subnet_ids         = module.vpc.vpc_private_subnet_ids
  security_group_ids = [aws_security_group.msk.id]
}
```
# Inputs
|Variable name|Required|Description|
|-------------|--------|-----------|
|cluster_name|Yes|Name of the MSK cluster to be created|
|subnet_ids|Yes|Subnets where the cluster nodes will be created. The number of nodes is determined by the number of subnets|
|security_group_ids|Yes|IDs of the security group(s) that will control access to the cluster|
|kafka_version|No|Defaults to 3.3.1|
|instance_type|No|Type fo the cluster instance. Defaults to kafka.m5.large|
|storage_size|No|Storage size in GiB. Defaults to 1TiB|
|enhanced_monitoring_level|No|Level of monitoring. Defaults to PER_TOPIC_PER_PARTITION|

# Outputs
|Output|Description|
|---|---|
|zookeeper_connect_string|Connection string to zookeeper|
|bootstrap_brokers_tls|Connection strings to brokers|

# Ignored checkov warnings

None
