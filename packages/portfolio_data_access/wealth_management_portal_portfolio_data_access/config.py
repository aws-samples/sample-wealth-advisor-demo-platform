"""Configuration for Redshift connection."""

import os


class RedshiftConfig:
    """Redshift connection configuration."""

    def __init__(self):
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
config = RedshiftConfig()
