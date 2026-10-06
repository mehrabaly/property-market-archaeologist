from datetime import datetime, timezone
import json

from zameen_scraper import scrape_page
from database import (
    save_property,
    start_scrape_run,
    finish_scrape_run
)


PAGE_URLS = [
    "https://www.zameen.com/Houses_Property/Lahore-1-1.html",
    "https://www.zameen.com/Houses_Property/Lahore-1-2.html"
]


SOURCE_ID = 1


scrape_started_at = datetime.now(
    timezone.utc
)


# --------------------------------------------------
# Start database scrape run
# --------------------------------------------------

scrape_run_id = start_scrape_run(
    SOURCE_ID,
    scrape_started_at
)


print(
    f"Started scrape run #{scrape_run_id}"
)


# --------------------------------------------------
# Scrape pages
# --------------------------------------------------

all_properties = []

pages_attempted = len(PAGE_URLS)
pages_successful = 0
pages_failed = 0

errors = []


for page_number, url in enumerate(
    PAGE_URLS,
    start=1
):

    print()
    print(
        f"SCRAPING PAGE {page_number}: {url}"
    )

    try:

        page_properties = scrape_page(url)

        print(
            f"FOUND {len(page_properties)} "
            f"PROPERTIES ON PAGE {page_number}"
        )

        all_properties.extend(
            page_properties
        )

        pages_successful += 1

    except Exception as error:

        pages_failed += 1

        error_message = (
            f"Page {page_number}: {str(error)}"
        )

        errors.append(
            error_message
        )

        print(
            f"ERROR: {error_message}"
        )


# --------------------------------------------------
# Check scraping result
# --------------------------------------------------

scrape_successful = (
    pages_successful == pages_attempted
    and len(all_properties) > 0
)


if not scrape_successful:

    print()
    print(
        "SCRAPE FAILED OR WAS INCOMPLETE."
    )

    print(
        "Successfully scraped listings "
        "will still be processed."
    )


# --------------------------------------------------
# Remove duplicate listings
# --------------------------------------------------

unique_properties = []

seen_listing_ids = set()


for property_data in all_properties:

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


all_properties = unique_properties


print()
print(
    f"UNIQUE PROPERTY LISTINGS FOUND: "
    f"{len(all_properties)}"
)


# --------------------------------------------------
# Save properties
# --------------------------------------------------

created_count = 0
updated_count = 0

price_increases = 0
price_decreases = 0
unchanged_properties = 0
price_unavailable = 0

property_changes = 0


for property_data in all_properties:

    result = save_property(
        property_data,
        SOURCE_ID
    )


    # ----------------------------------------------
    # Property action
    # ----------------------------------------------

    if result["action"] == "created":

        created_count += 1

    elif result["action"] == "updated":

        updated_count += 1


    # ----------------------------------------------
    # Price status
    # ----------------------------------------------

    price_status = result[
        "price_status"
    ]


    if price_status == "PRICE UP":

        price_increases += 1

        print(
            f"PRICE UP | "
            f"{property_data.listing_id}"
        )


    elif price_status == "PRICE DOWN":

        price_decreases += 1

        print(
            f"PRICE DOWN | "
            f"{property_data.listing_id}"
        )


    elif price_status == "UNCHANGED":

        unchanged_properties += 1


    elif price_status == "PRICE UNAVAILABLE":

        price_unavailable += 1


    elif price_status == "NEW":

        print(
            f"NEW PROPERTY | "
            f"{property_data.listing_id}"
        )


    # ----------------------------------------------
    # Other property changes
    # ----------------------------------------------

    changed_fields = result[
        "changed_fields"
    ]


    if changed_fields:

        property_changes += 1

        print(
            f"PROPERTY CHANGED | "
            f"{property_data.listing_id} | "
            f"{', '.join(changed_fields)}"
        )


# --------------------------------------------------
# Finish database scrape run
# --------------------------------------------------

scrape_finished_at = (
    datetime.now(
        timezone.utc
    )
)


if scrape_successful:

    run_status = "success"

else:

    run_status = "partial"


finish_scrape_run(
    scrape_run_id=scrape_run_id,
    finished_at=scrape_finished_at,
    pages_attempted=pages_attempted,
    pages_successful=pages_successful,
    pages_failed=pages_failed,
    properties_found=len(all_properties),
    new_properties=created_count,
    price_increases=price_increases,
    price_decreases=price_decreases,
    unchanged_properties=unchanged_properties,
    no_longer_detected=0,
    status=run_status,
    errors=json.dumps(errors)
)


# --------------------------------------------------
# Final output
# --------------------------------------------------

print()
print(
    "SCRAPE COMPLETE."
)

print(
    "-----------------------------"
)

print(
    f"Scrape run ID: "
    f"{scrape_run_id}"
)

print(
    f"Started: "
    f"{scrape_started_at}"
)

print(
    f"Finished: "
    f"{scrape_finished_at}"
)

print(
    f"Pages attempted: "
    f"{pages_attempted}"
)

print(
    f"Pages successful: "
    f"{pages_successful}"
)

print(
    f"Pages failed: "
    f"{pages_failed}"
)

print(
    f"Unique properties found: "
    f"{len(all_properties)}"
)

print(
    f"New properties: "
    f"{created_count}"
)

print(
    f"Updated properties: "
    f"{updated_count}"
)

print(
    f"Price increases: "
    f"{price_increases}"
)

print(
    f"Price decreases: "
    f"{price_decreases}"
)

print(
    f"Unchanged prices: "
    f"{unchanged_properties}"
)

print(
    f"Price unavailable: "
    f"{price_unavailable}"
)

print(
    f"Properties with other changes: "
    f"{property_changes}"
)

print(
    f"Run status: "
    f"{run_status}"
)

if errors:

    print()
    print(
        "Errors:"
    )

    for error in errors:

        print(
            f"- {error}"
        )