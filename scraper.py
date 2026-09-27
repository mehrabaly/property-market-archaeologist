import json
from datetime import datetime, timezone

from dataclasses import asdict

from zameen_scraper import scrape_page


PAGE_URLS = [
    "https://www.zameen.com/Houses_Property/Lahore-1-1.html",
    "https://www.zameen.com/Houses_Property/Lahore-1-2.html"
]

HISTORY_FILE = "properties_history.json"
RUNS_FILE = "scrape_runs.json"
PROPERTIES_FILE = "properties.json"


scrape_started_at = datetime.now(timezone.utc).isoformat()


# --------------------------------------------------
# Load previous history
# --------------------------------------------------

try:
    with open(
        HISTORY_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        history = json.load(file)

except FileNotFoundError:
    history = {}


# --------------------------------------------------
# Convert old history format if necessary
# --------------------------------------------------

if isinstance(history, list):

    converted_history = {}

    for old_property in history:

        listing_id = old_property.get("listing_id")

        if not listing_id:
            continue

        observation = dict(old_property)

        converted_history[listing_id] = {
            "listing_id": listing_id,
            "status": "active",
            "observations": [
                observation
            ]
        }

    history = converted_history

    print("Converted old history format successfully.")


# --------------------------------------------------
# Make sure every history record has the new format
# --------------------------------------------------

for listing_id, record in history.items():

    if "observations" not in record:
        record["observations"] = []

    if "status" not in record:
        record["status"] = "active"


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

        errors.append(error_message)

        print(
            f"ERROR: {error_message}"
        )


# --------------------------------------------------
# Determine whether the scrape was successful
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
        "Missing-property detection will NOT run."
    )


# --------------------------------------------------
# Remove duplicates across all pages
# --------------------------------------------------

unique_properties = []
seen_listing_ids = set()


for property_data in all_properties:

    listing_id = property_data.listing_id

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
# Add observation timestamp
# --------------------------------------------------

scraped_at = datetime.now(
    timezone.utc
).isoformat()


current_listing_ids = set()


for property_data in all_properties:

    property_data_dict = asdict(
        property_data
    )

    property_data_dict["scraped_at"] = (
        scraped_at
    )

    listing_id = (
        property_data.listing_id
    )

    current_listing_ids.add(
        listing_id
    )

    # ----------------------------------------------
    # New property
    # ----------------------------------------------

    if listing_id not in history:

        history[listing_id] = {
            "listing_id": listing_id,
            "status": "active",
            "observations": []
        }

        history[listing_id][
            "observations"
        ].append(
            property_data_dict
        )

        print(
            f"NEW PROPERTY | {listing_id}"
        )

        continue


    # ----------------------------------------------
    # Existing property
    # ----------------------------------------------

    record = history[listing_id]

    observations = record[
        "observations"
    ]


    # ----------------------------------------------
    # Price comparison
    # ----------------------------------------------

    old_price = None

    if observations:

        old_price = observations[
            -1
        ].get("price")


    new_price = property_data.price


    if (
        old_price is not None
        and new_price is not None
    ):

        if new_price < old_price:

            difference = (
                old_price - new_price
            )

            print(
                f"PRICE DOWN | "
                f"{listing_id} | "
                f"{old_price} -> {new_price} | "
                f"Difference: {difference}"
            )

        elif new_price > old_price:

            difference = (
                new_price - old_price
            )

            print(
                f"PRICE UP | "
                f"{listing_id} | "
                f"{old_price} -> {new_price} | "
                f"Difference: {difference}"
            )

        else:

            print(
                f"UNCHANGED | "
                f"{listing_id} | "
                f"{new_price}"
            )

    else:

        print(
            f"EXISTING | "
            f"{listing_id} | "
            f"Price unavailable"
        )


    # ----------------------------------------------
    # Reappeared property
    # ----------------------------------------------

    if record.get("status") == (
        "no_longer_detected"
    ):

        print(
            f"REAPPEARED | {listing_id}"
        )

        record["status"] = "active"


    # ----------------------------------------------
    # Add new observation
    # ----------------------------------------------

    observations.append(
        property_data_dict
    )


# --------------------------------------------------
# No-longer-detected tracking
# --------------------------------------------------

no_longer_detected_count = 0


if scrape_successful:

    for listing_id, record in history.items():

        if listing_id not in current_listing_ids:

            if record.get("status") != (
                "no_longer_detected"
            ):

                record["status"] = (
                    "no_longer_detected"
                )

                record["last_detected"] = (
                    scraped_at
                )

                no_longer_detected_count += 1

                print(
                    f"NO LONGER DETECTED | "
                    f"{listing_id}"
                )


# --------------------------------------------------
# Convert current properties to dictionaries
# --------------------------------------------------

properties_for_json = []


for property_data in all_properties:

    property_dict = asdict(
        property_data
    )

    property_dict["scraped_at"] = (
        scraped_at
    )

    properties_for_json.append(
        property_dict
    )


# --------------------------------------------------
# Save current properties
# --------------------------------------------------

with open(
    PROPERTIES_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        properties_for_json,
        file,
        indent=4,
        ensure_ascii=False
    )


# --------------------------------------------------
# Save history
# --------------------------------------------------

with open(
    HISTORY_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        history,
        file,
        indent=4,
        ensure_ascii=False
    )


# --------------------------------------------------
# Scrape run statistics
# --------------------------------------------------

new_properties_count = 0
price_increases = 0
price_decreases = 0
unchanged_properties = 0


for property_data in all_properties:

    listing_id = property_data.listing_id

    record = history.get(
        listing_id
    )

    if not record:
        continue

    observations = record.get(
        "observations",
        []
    )

    if len(observations) < 2:
        new_properties_count += 1
        continue

    old_price = observations[
        -2
    ].get("price")

    new_price = observations[
        -1
    ].get("price")


    if (
        old_price is not None
        and new_price is not None
    ):

        if new_price > old_price:
            price_increases += 1

        elif new_price < old_price:
            price_decreases += 1

        else:
            unchanged_properties += 1

    else:
        unchanged_properties += 1


scrape_finished_at = (
    datetime.now(timezone.utc)
    .isoformat()
)


# --------------------------------------------------
# Create scrape-run record
# --------------------------------------------------

run_record = {

    "started_at": scrape_started_at,

    "finished_at": scrape_finished_at,

    "source": "Zameen",

    "pages_attempted": pages_attempted,

    "pages_successful": pages_successful,

    "pages_failed": pages_failed,

    "properties_found": len(
        all_properties
    ),

    "new_properties": (
        new_properties_count
    ),

    "price_increases": (
        price_increases
    ),

    "price_decreases": (
        price_decreases
    ),

    "unchanged_properties": (
        unchanged_properties
    ),

    "no_longer_detected": (
        no_longer_detected_count
    ),

    "status": (
        "success"
        if scrape_successful
        else "failed"
    ),

    "errors": errors
}


# --------------------------------------------------
# Load previous scrape runs
# --------------------------------------------------

try:

    with open(
        RUNS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        scrape_runs = json.load(
            file
        )

except FileNotFoundError:

    scrape_runs = []


scrape_runs.append(
    run_record
)


# --------------------------------------------------
# Save scrape runs
# --------------------------------------------------

with open(
    RUNS_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        scrape_runs,
        file,
        indent=4,
        ensure_ascii=False
    )


# --------------------------------------------------
# Final output
# --------------------------------------------------

print()
print(
    "SCRAPE COMPLETE."
)

print(
    f"Pages successful: "
    f"{pages_successful}/{pages_attempted}"
)

print(
    f"Unique properties: "
    f"{len(all_properties)}"
)

print(
    f"New properties: "
    f"{new_properties_count}"
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
    f"No longer detected: "
    f"{no_longer_detected_count}"
)

print(
    f"Run status: "
    f"{run_record['status']}"
)

print()
print(
    "Data saved to:"
)

print(
    f"- {PROPERTIES_FILE}"
)

print(
    f"- {HISTORY_FILE}"
)

print(
    f"- {RUNS_FILE}"
)