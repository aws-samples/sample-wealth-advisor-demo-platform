"""Configuration for data access (Athena or Redshift)."""

import os


class DataAccessConfig:
    """Data access configuration supporting both Athena and Redshift backends."""

    def __init__(self):
        self.engine = os.getenv("DATA_ENGINE", "athena").lower()

        # Athena config
        self.athena_workgroup = os.getenv("ATHENA_WORKGROUP", "primary")
        self.athena_output_location = os.getenv("ATHENA_OUTPUT_LOCATION", "")
        self.athena_catalog = os.getenv("ATHENA_CATALOG", "s3tablescatalog/financial-advisor-s3table")
        self.athena_database = os.getenv("ATHENA_DATABASE", "financial_advisor")

        # Redshift config (legacy)
        self.workgroup = os.getenv("REDSHIFT_WORKGROUP", "financial-advisor-wg")
        self.database = os.getenv("REDSHIFT_DATABASE", "financial-advisor-db")

        self.region = os.getenv("AWS_REGION", "us-west-2")
        self.profile_name = os.getenv("AWS_PROFILE")
        self.use_default_credentials = os.getenv("USE_DEFAULT_AWS_CREDENTIALS", "false").lower() == "true"

    def get_profile_name(self) -> str | None:
        """Get AWS profile name, or None if using default credentials."""
        if self.use_default_credentials:
            return None
        return self.profile_name


# Global config instance
config = DataAccessConfig()
