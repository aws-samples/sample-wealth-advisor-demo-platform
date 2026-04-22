variable "region" {
  type        = string
  description = "Name of the lambda function"
}

variable "function_name" {
  type        = string
  description = "Name of the lambda function"
}

variable "handler_name" {
  type        = string
  description = "Name of the function handler"
}

variable "description" {
  type        = string
  description = "Description of the function"
}

variable "resource_policies" {
  type        = list(string)
  description = "Lambda role IAM policy documents"
}

variable "runtime" {
  type        = string
  default     = "python3.9"
  description = "Lambda runtime e.g. dotnet, python3.9 etc"
}

variable "code_archive" {
  type        = string
  default     = null
  description = "Zip file with lambda's code package"
}

variable "code_archive_hash" {
  type = string
  default = null
  description = "The hash for the source code archive"
}

variable "environment_variables" {
  type        = map(any)
  description = "Optional map of environment variables"
  default     = { DUMMY = "" }
}

variable "memory_size" {
  default     = 512
  description = "Memory size for the function"
  type        = number
}

variable "layer_arns" {
  type        = list(string)
  default     = []
  description = "List of layer arn(s) for the lambda function"
}

variable "subnet_ids" {
  type        = list(string)
  default     = []
  description = "List of subnet id(s) to which lambda should be attached"
}

variable "security_group_ids" {
  type        = list(string)
  default     = []
  description = "List of security group id(s) to which lambda should be attached"
}

variable "timeout" {
  type        = number
  default     = 60
  description = "Timeout for the lambda function"
}