variable "table_name" {
  type        = string
  description = "Name of the table"
}

variable "hash_key" {
  type        = string
  description = "Hash key"
}

variable "range_key" {
  type        = string
  default     = null
  description = "Sort key"
}

variable "stream_enabled" {
  type        = bool
  default     = false
  description = "Enable streaming of changes (defaults to false)"
}

variable "attributes" {
  type        = list(any)
  default     = []
  description = "Include additional attributes and those used for secondary indices here"
}

variable "local_secondary_indices" {
  type        = list(any)
  default     = []
  description = "List of objects which each describe a local secondary index"
}

variable "global_secondary_indices" {
  type        = list(any)
  default     = []
  description = "List of objects which each describe a global secondary index"
}

variable "enable_import" {
  description = "Enable importing data from S3"
  type        = bool
  default     = false
}

variable "import_format" {
  description = "Format of the import file (CSV, DYNAMODB_JSON, ION)"
  type        = string
  default     = "CSV"
}

variable "import_compression_type" {
  description = "Type of compression (GZIP, ZSTD, NONE)"
  type        = string
  default     = "NONE"
}

variable "import_bucket_name" {
  description = "S3 bucket name containing the import data"
  type        = string
  default     = ""
}

variable "import_key_prefix" {
  description = "S3 key prefix for the import data"
  type        = string
  default     = ""
}

variable "csv_delimiter" {
  description = "Delimiter for CSV import"
  type        = string
  default     = ","
}

variable "csv_header_list" {
  description = "List of headers for CSV import"
  type        = list(string)
  default     = []
}

variable "dynamodb_kms_key_arn" {
  type        = string
  default     = null
  description = "KMS key ARN for DynamoDB encryption. If null, uses AWS managed key."
}