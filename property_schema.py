from dataclasses import dataclass
from typing import Optional


@dataclass
class Property:
    source: str
    listing_id: str

    title: str
    property_type: str

    original_price: str
    price: Optional[float]

    location: str

    bedrooms: str
    bathrooms: str

    original_area: str
    area_sqft: Optional[float]

    description: str
    source_listed_at: Optional[str]

    url: str

    scraped_at: Optional[str] = None