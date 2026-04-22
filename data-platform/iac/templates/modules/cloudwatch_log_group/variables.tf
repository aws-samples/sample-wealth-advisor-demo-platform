#
# Module's input variables
#
variable "name" {
  description = "Name of the cloudwatch log group"
  type        = string
}

variable "log_retention_days" {
  description = "Log retention period. Defaults to 365"
  type        = number
  default     = 365
}

variable "roles" {
  type        = list(string)
  default     = []
  description = "List of roles which will be allowed access to log group's KMS key"
}

variable "services" {
  type        = list(string)
  default     = []
  description = "List of services which will be allowed access to log group's KMS key"
}

variable "via_services" {
  type        = list(string)
  default     = []
  description = "List of services access through which will be allowed to log group's KMS key"
}