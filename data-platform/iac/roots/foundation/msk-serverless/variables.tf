#
# Module's input variables
#
variable "APP" {
  description = "Short abbr of the app"
  type        = string
  default     = "daivi"
}
variable "ENV" {
  description = "Environment name"
  type        = string
}

variable "AWS_PRIMARY_REGION" {

  type = string
}

variable "SSM_KMS_KEY_ALIAS" {
  description = "KMS key alias for SSM"
  type        = string
}