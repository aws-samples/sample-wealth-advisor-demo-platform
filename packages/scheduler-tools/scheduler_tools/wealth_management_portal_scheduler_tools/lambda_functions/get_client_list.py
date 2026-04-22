from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from wealth_management_portal_portfolio_data_access.repositories.client_repository import ClientRepository

logger = Logger()
tracer = Tracer()

# First N clients run as a canary batch before the full run
TEST_BATCH_SIZE = 3


def _fetch_all_client_ids(repo: ClientRepository) -> list[str]:
    """Paginate through Redshift to get all client IDs."""
    all_ids = []
    offset = 0
    page_size = 100
    while True:
        page = repo.get_all_clients(limit=page_size, offset=offset)
        all_ids.extend(str(c["client_id"]) for c in page if c.get("client_id"))
        if len(page) < page_size:
            break
        offset += page_size
    return all_ids


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """Get all active client IDs from Redshift, split into test and remaining batches."""
    logger.info("Fetching client list from Redshift")

    repo = ClientRepository()
    client_ids = _fetch_all_client_ids(repo)

    logger.info(f"Found {len(client_ids)} clients, test batch size: {TEST_BATCH_SIZE}")

    return {
        "test_client_ids": client_ids[:TEST_BATCH_SIZE],
        "remaining_client_ids": client_ids[TEST_BATCH_SIZE:],
        "count": len(client_ids),
    }
