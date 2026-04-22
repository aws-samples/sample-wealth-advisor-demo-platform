# Connection factory for Redshift Serverless using IAM authentication
import os
from collections.abc import Callable

import redshift_connector

from wealth_management_portal_portfolio_data_access.config import config


def iam_connection_factory() -> Callable:
    """Returns a factory for IAM-authenticated Redshift Serverless connections."""

    def connect():
        # Tunnel mode: connect via SSM port forwarding with manual IAM credentials
        if os.environ.get("REDSHIFT_HOST"):
            import boto3

            profile_name = config.get_profile_name()
            if profile_name:
                session = boto3.Session(profile_name=profile_name, region_name=config.region)
            else:
                session = boto3.Session(region_name=config.region)

            creds = session.client("redshift-serverless").get_credentials(workgroupName=config.workgroup)

            return redshift_connector.connect(
                host=os.environ.get("REDSHIFT_HOST"),
                port=int(os.environ.get("REDSHIFT_PORT", "5439")),
                user=creds["dbUser"],
                password=creds["dbPassword"],
                database=config.database,
                ssl=True,
                sslmode="require",
            )

        # Standard serverless mode
        return redshift_connector.connect(
            iam=True,
            is_serverless=True,
            serverless_work_group=config.workgroup,
            region=config.region,
            database=os.environ.get("REDSHIFT_DATABASE", "financial-advisor-db"),
            serverless_acct_id=os.environ["AWS_ACCOUNT_ID"],
        )

    return connect
