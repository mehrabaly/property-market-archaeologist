import re

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from property_schema import Property


BASE_URL = "https://www.zameen.com"


def parse_price(price_text):
    if not price_text:
        return None

    cleaned_text = (
        price_text
        .replace(",", "")
        .strip()
    )

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(Arab|Crore|Lakh)",
        cleaned_text,
        re.IGNORECASE
    )

    if not match:
        return None

    try:
        amount = float(match.group(1))
    except ValueError:
        return None

    unit = match.group(2).lower()

    if unit == "crore":
        return amount * 10_000_000

    if unit == "lakh":
        return amount * 100_000

    if unit == "arab":
        return amount * 1_000_000_000

    return None


def parse_area(area_text):
    if not area_text:
        return None

    cleaned_text = (
        area_text
        .replace(",", "")
        .strip()
    )

    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(Marla|Kanal)",
        cleaned_text,
        re.IGNORECASE
    )

    if not match:
        return None

    try:
        amount = float(match.group(1))
    except ValueError:
        return None

    unit = match.group(2).lower()

    if unit == "marla":
        return amount * 272.25

    if unit == "kanal":
        return amount * 5445

    return None


def get_page(url):
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):

        try:
            response = httpx.get(
                url,
                timeout=20
            )

            response.raise_for_status()

            return response

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.HTTPStatusError
        ) as error:

            if attempt == max_attempts:
                raise

            print(
                f"REQUEST FAILED "
                f"(attempt {attempt}/{max_attempts}): "
                f"{error}"
            )

    raise RuntimeError(
        f"Could not retrieve page: {url}"
    )


def build_page_url(page_number):
    return (
        f"{BASE_URL}/Houses_Property/"
        f"Lahore-1-{page_number}.html"
    )


def get_total_pages(url):
    response = get_page(url)

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    page_text = soup.get_text(
        " ",
        strip=True
    )

    match = re.search(
        r"1\s+to\s+\d+\s+of\s+([\d,]+)\s+Houses",
        page_text,
        re.IGNORECASE
    )

    if not match:

        raise ValueError(
            "Could not determine total property count "
            f"from page: {url}"
        )

    total_properties = int(
        match.group(1).replace(",", "")
    )

    properties_per_page = 25

    total_pages = (
        total_properties
        + properties_per_page
        - 1
    ) // properties_per_page

    return total_properties, total_pages


def scrape_page(url):

    response = get_page(url)

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    articles = soup.find_all(
        "article"
    )

    property_articles = []

    for article in articles:

        listing_link = article.find(
            "a",
            {"aria-label": "Listing link"}
        )

        if listing_link:

            property_articles.append(
                article
            )

    if len(property_articles) == 0:

        raise ValueError(
            f"No property listings found on page: {url}"
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


        # ------------------------------------------
        # Title
        # ------------------------------------------

        title = listing_link.get(
            "title"
        )

        if not title:
            title = "Title not found"


        # ------------------------------------------
        # URL
        # ------------------------------------------

        href = listing_link.get(
            "href"
        )

        if not href:
            continue

        if href.startswith("http"):

            property_url = href

        else:

            property_url = (
                BASE_URL + href
            )


        # ------------------------------------------
        # Listing ID
        # ------------------------------------------

        url_parts = property_url.split("-")

        if len(url_parts) < 3:
            continue

        listing_id = url_parts[-3]

        if not listing_id.isdigit():
            continue


        # ------------------------------------------
        # Price
        # ------------------------------------------

        price_element = article.find(
            string=lambda value: value and (
                "Crore" in value
                or "Lakh" in value
                or "Arab" in value
            )
        )

        original_price = (
            price_element.strip()
            if price_element
            else "Price not found"
        )

        price = parse_price(
            original_price
        )


        # ------------------------------------------
        # Location
        # ------------------------------------------

        location_element = article.find(
            "div",
            class_="db1aca2f"
        )

        location = (
            location_element.get_text(
                strip=True
            )
            if location_element
            else "Location not found"
        )


        # ------------------------------------------
        # Features
        # ------------------------------------------

        feature_elements = article.find_all(
            "span",
            class_="_5ca8f903"
        )

        features = []

        for feature in feature_elements:

            value = feature.get_text(
                strip=True
            )

            features.append(
                value
            )


        # ------------------------------------------
        # Bedrooms, Bathrooms and Area
        # ------------------------------------------

        bedrooms = "Not found"
        bathrooms = "Not found"
        original_area = "Not found"

        for feature in features:

            if any(
                unit in feature.lower()
                for unit in ("marla", "kanal")
            ):

                original_area = feature

            elif bedrooms == "Not found":

                bedrooms = feature

            elif bathrooms == "Not found":

                bathrooms = feature

        area_sqft = parse_area(
            original_area
        )


        # ------------------------------------------
        # Create property
        # ------------------------------------------

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
            description="",
            source_listed_at=None,
            url=property_url,
            scraped_at=scraped_at
        )

        properties.append(
            property_data
        )


    # ----------------------------------------------
    # Remove duplicate listings
    # ----------------------------------------------

    unique_properties = []

    seen_listing_ids = set()

    for property_data in properties:

        listing_id = (
            property_data.listing_id
        )

        if listing_id in seen_listing_ids:
            continue

        seen_listing_ids.add(
            listing_id
        )

        unique_properties.append(
            property_data
        )

    return unique_properties