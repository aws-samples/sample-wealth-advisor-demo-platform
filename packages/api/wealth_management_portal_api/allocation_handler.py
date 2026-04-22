import contextlib
import json

from pydantic import BaseModel
from wealth_management_portal_portfolio_data_access.repositories.allocation_repository import (
    AllocationRepository,
)


class AllocationItem(BaseModel):
    name: str
    value: float


class AssetAllocationResponse(BaseModel):
    success: bool
    allocations: list[AllocationItem]
    message: str


def get_client_asset_allocation(client_id: str) -> AssetAllocationResponse:
    """Get asset allocation for a client from portfolios table"""
    try:
        repo = AllocationRepository()
        rows = repo.get_client_allocation(client_id)

        if not rows:
            return AssetAllocationResponse(
                success=False,
                allocations=[],
                message="No allocation data found for client",
            )

        # Parse target_allocation - can be JSON or text format
        target_allocation = rows[0].get("target_allocation", "")

        if not target_allocation:
            return AssetAllocationResponse(
                success=False,
                allocations=[],
                message="No allocation data in target_allocation column",
            )

        allocation_dict = {}

        if isinstance(target_allocation, str):
            target_allocation = target_allocation.strip()

            # Try JSON first
            if target_allocation.startswith("{"):
                with contextlib.suppress(json.JSONDecodeError):
                    allocation_dict = json.loads(target_allocation)

            # Parse text format: "50% Stocks, 40% Bonds, 10% Alternatives"
            if not allocation_dict:
                parts = target_allocation.split(",")
                for part in parts:
                    part = part.strip()
                    if "%" in part:
                        # Split on % to get percentage and name
                        pct_str, name = part.split("%", 1)
                        pct_str = pct_str.strip()
                        name = name.strip()
                        try:
                            allocation_dict[name] = float(pct_str)
                        except ValueError:
                            continue
        elif isinstance(target_allocation, dict):
            allocation_dict = target_allocation

        if not allocation_dict:
            return AssetAllocationResponse(
                success=False,
                allocations=[],
                message=f"Could not parse target_allocation: {target_allocation[:100]}",
            )

        # Convert to list format
        allocations = [AllocationItem(name=key, value=float(value)) for key, value in allocation_dict.items()]

        return AssetAllocationResponse(
            success=True,
            allocations=allocations,
            message=f"Retrieved {len(allocations)} allocation items",
        )

    except Exception as e:
        return AssetAllocationResponse(
            success=False,
            allocations=[],
            message=f"Error retrieving asset allocation: {str(e)}",
        )
