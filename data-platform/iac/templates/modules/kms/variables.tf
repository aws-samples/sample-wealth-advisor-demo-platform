#
# Module's input variables
#
variable "alias" {
  description = "Key alias"
  type        = string
}

variable "description" {
  description = "Description of the key"
  type        = string
}

variable "roles" {
  description = "List of role (identity) ARNs that will be allowed to use the key for encryption/decryption purposes"
  type        = list(string)
  default     = []
}

variable "services" {
  description = "List of AWS services that will be allowed to use the key for encryption/decryption purposes"
  type        = list(string)
  default     = []
}

variable "via_services" {
  description = "List of AWS services that will allow any identity to use the key for encryption/decryption purposes"
  type        = list(string)
  default     = []
}

variable "key_policy" {
  description = "Optional JSON key policy if the default does not meet the requirements."
  type        = string
  default     = null
} 