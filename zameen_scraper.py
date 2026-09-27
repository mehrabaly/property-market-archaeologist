import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from property_schema import Property


BASE_URL = "https://www.zameen.com"


def scrape_page(url):
    response = httpx.get(url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    articles = soup.find_all("article")

    property_articles = []

    for article in articles:
        listing_link = article.find(
            "a",
            {"aria-label": "Listing link"}
        )

        if listing_link:
            property_articles.append(article)

    if len(property_articles) == 0:
        raise ValueError(
            "No property listings found on page."
        )

    properties = []

    scraped_at = datetime.now(
        timezone.utc
    ).isoformat()

    for article in property_articles:
        listing_link = article.find(
            "a",
            {"aria-label": "Listing link"}
        )

        if not listing_link:
            continue

        title = listing_link.get("title")

        property_url = (
            BASE_URL +
            listing_link.get("href")
        )

        listing_id = (
            property_url.split("-")[-3]
        )

        price_element = article.find(
            string=lambda value: value and (
                "Crore" in value or
                "Lakh" in value or
                "Arab" in value
            )
        )

        original_price = (
            price_element.strip()
            if price_element
            else "Price not found"
        )

        price = None

        if original_price != "Price not found":
            price_parts = original_price.split()

            if len(price_parts) >= 2:
                try:
                    amount = float(price_parts[-2])
                    unit = price_parts[-1].lower()

                    if unit == "crore":
                        price = amount * 10_000_000

                    elif unit == "lakh":
                        price = amount * 100_000

                    elif unit == "arab":
                        price = amount * 1_000_000_000

                except ValueError:
                    price = None

        location_element = article.find(
            "div",
            class_="db1aca2f"
        )

        location = (
            location_element.get_text(strip=True)
            if location_element
            else "Location not found"
        )

        feature_elements = article.find_all(
            "span",
            class_="_5ca8f903"
        )

        features = []

        for feature in feature_elements:
            value = feature.get_text(strip=True)
            features.append(value)

        bedrooms = (
            features[0]
            if len(features) > 0
            else "Not found"
        )

        bathrooms = (
            features[1]
            if len(features) > 1
            else "Not found"
        )

        original_area = (
            features[2]
            if len(features) > 2
            else "Not found"
        )

        area_sqft = None

        if original_area != "Not found":
            area_parts = original_area.split()

            if len(area_parts) >= 2:
                try:
                    area_amount = float(area_parts[0])
                    area_unit = area_parts[1].lower()

                    if area_unit == "marla":
                        area_sqft = (
                            area_amount * 272.25
                        )

                    elif area_unit == "kanal":
                        area_sqft = (
                            area_amount * 5445
                        )

                except ValueError:
                    area_sqft = None

        property_data = Property(
            source="Zameen",
            listing_id=listing_id,
            title=title,
            property_type="House",
            original_price=original_price,
            price=price,
            location=location,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            original_area=original_area,
            area_sqft=area_sqft,
            url=property_url,
            scraped_at=scraped_at
        )

        properties.append(property_data)

    unique_properties = []
    seen_listing_ids = set()

    for property_data in properties:
        listing_id = property_data.listing_id

        if listing_id in seen_listing_ids:
            continue

        seen_listing_ids.add(listing_id)
        unique_properties.append(property_data)

    return unique_properties