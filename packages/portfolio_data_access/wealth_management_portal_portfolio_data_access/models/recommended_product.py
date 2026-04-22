# Redshift-mirroring model for recommended products
from datetime import date

from pydantic import BaseModel


class RecommendedProduct(BaseModel):
    """Recommended product record from Redshift recommended_products table."""

    product_id: str
    product_name: str
    product_type: str
    description: str | None = None
    status: str = "Active"
    created_date: date | None = None
