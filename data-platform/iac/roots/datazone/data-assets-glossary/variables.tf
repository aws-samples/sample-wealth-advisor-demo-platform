variable "AWS_ACCOUNT_ID" {
  type = string
}

variable "AWS_PRIMARY_REGION" {
  type = string
}

variable "APP" {
  type = string
}

variable "ENV" {
  type = string
}

variable "DOMAIN_ID" {
  type        = string
  description = "SageMaker/DataZone domain ID"
}

variable "PRODUCER_PROJECT_ID" {
  type        = string
  description = "Producer project ID"
}

variable "CONSUMER_PROJECT_ID" {
  type        = string
  description = "Consumer project ID"
}
