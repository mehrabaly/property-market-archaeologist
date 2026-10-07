from datetime import datetime, timezone
import json
import time

from zameen_scraper import (
    scrape_page,
    build_page_url,
    get_total_pages
)

from database import (
    get_connection,
    save_properties_page,
    start_scrape_run,
    update_scrape_progress,
    finish_scrape_run
)


SOURCE_ID = 1

# --------------------------------------------------
# Test settings
# --------------------------------------------------

# Maximum number of pages to process in one execution.
#
# Keep this at 5 for now.
# We will remove this later.
MAX_PAGES = 5

# Delay between pages.
PAGE_DELAY_SECONDS = 3


# --------------------------------------------------
# Find an unfinished scrape run
# --------------------------------------------------

def get_latest_incomplete_run(source_id):

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    total_pages,
                    last_completed_page,
                    status
                FROM scrape_runs
                WHERE source_id = %s
                  AND status IN ('running', 'partial')
                ORDER BY id DESC
                LIMIT 1
                """,
                (source_id,)
            )

            row = cursor.fetchone()

            return row

    finally:

        connection.close()


# --------------------------------------------------
# Start
# --------------------------------------------------

print()
print(
    "=========================================="
)

print(
    "PROPERTY MARKET ARCHAEOLOGIST"
)

print(
    "SCRAPER STARTING..."
)

print(
    "=========================================="
)


# --------------------------------------------------
# Discover total pages
# --------------------------------------------------

first_page_url = build_page_url(1)

print()
print(
    "DISCOVERING TOTAL PAGES..."
)

total_properties, total_pages = get_total_pages(
    first_page_url
)

print(
    f"TOTAL PROPERTIES REPORTED BY ZAMEEN: "
    f"{total_properties}"
)

print(
    f"TOTAL PAGES AVAILABLE: "
    f"{total_pages}"
)


# --------------------------------------------------
# Check for unfinished crawl
# --------------------------------------------------

incomplete_run = get_latest_incomplete_run(
    SOURCE_ID
)


if incomplete_run:

    scrape_run_id = incomplete_run[0]

    last_completed_page = incomplete_run[2]

    previous_status = incomplete_run[3]

    start_page = (
        last_completed_page + 1
    )

    print()
    print(
        "=========================================="
    )

    print(
        "UNFINISHED SCRAPE RUN FOUND"
    )

    print(
        "=========================================="
    )

    print(
        f"Scrape run ID: {scrape_run_id}"
    )

    print(
        f"Previous status: {previous_status}"
    )

    print(
        f"Last completed page: "
        f"{last_completed_page}"
    )

    print(
        f"RESUMING FROM PAGE: {start_page}"
    )


else:

    # --------------------------------------------------
    # Start a completely new crawl
    # --------------------------------------------------

    start_page = 1

    scrape_started_at = datetime.now(
        timezone.utc
    )

    scrape_run_id = start_scrape_run(
        SOURCE_ID,
        scrape_started_at,
        total_pages
    )

    print()
    print(
        "=========================================="
    )

    print(
        "NO UNFINISHED SCRAPE FOUND"
    )

    print(
        "STARTING NEW SCRAPE"
    )

    print(
        "=========================================="
    )

    print(
        f"Started scrape run #{scrape_run_id}"
    )


# --------------------------------------------------
# Determine test range
# --------------------------------------------------

end_page = min(
    start_page + MAX_PAGES - 1,
    total_pages
)


if start_page > total_pages:

    print()
    print(
        "=========================================="
    )

    print(
        "NOTHING TO SCRAPE"
    )

    print(
        f"Last completed page: "
        f"{start_page - 1}"
    )

    print(
        f"Total pages available: "
        f"{total_pages}"
    )

    print(
        "The crawl is already complete."
    )

    print(
        "=========================================="
    )

    raise SystemExit


pages_to_scrape = (
    end_page - start_page + 1
)


print()
print(
    f"TEST RANGE: "
    f"PAGE {start_page} TO PAGE {end_page}"
)

print(
    f"PAGES TO SCRAPE: "
    f"{pages_to_scrape}"
)


# --------------------------------------------------
# Counters
# --------------------------------------------------

pages_attempted = 0
pages_successful = 0
pages_failed = 0

properties_found = 0
created_count = 0
updated_count = 0

price_increases = 0
price_decreases = 0
unchanged_properties = 0
price_unavailable = 0

property_changes = 0

errors = []


# --------------------------------------------------
# Scrape pages one by one
# --------------------------------------------------

for page_number in range(
    start_page,
    end_page + 1
):

    url = build_page_url(
        page_number
    )

    pages_attempted += 1

    print()
    print(
        "=========================================="
    )

    print(
        f"SCRAPING PAGE {page_number} "
        f"OF {end_page}"
    )

    print(
        url
    )

    try:

        # ------------------------------------------
        # Scrape page
        # ------------------------------------------

        page_properties = scrape_page(
            url
        )

        print(
            f"FOUND {len(page_properties)} "
            f"PROPERTIES ON PAGE {page_number}"
        )


        # ------------------------------------------
        # Save entire page in one transaction
        # ------------------------------------------

        try:

            results = save_properties_page(
                page_properties,
                SOURCE_ID
            )

        except Exception as error:

            pages_failed += 1

            error_message = {
                "page": page_number,
                "error": str(error)
            }

            errors.append(
                error_message
            )

            print()
            print(
                f"ERROR SAVING PAGE {page_number}: "
                f"{error}"
            )

            print()
            print(
                "ENTIRE PAGE TRANSACTION "
                "ROLLED BACK."
            )

            print(
                f"PAGE {page_number} WAS NOT "
                "MARKED AS COMPLETED."
            )

            print(
                "The crawler will stop so this page "
                "can be safely retried."
            )

            break


        # ------------------------------------------
        # Process committed results
        # ------------------------------------------

        for property_data, result in zip(
            page_properties,
            results
        ):

            properties_found += 1


            # --------------------------------------
            # Property action
            # --------------------------------------

            if result["action"] == "created":

                created_count += 1

                print(
                    f"NEW PROPERTY | "
                    f"{property_data.listing_id}"
                )

            elif result["action"] == "updated":

                updated_count += 1


            # --------------------------------------
            # Price status
            # --------------------------------------

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


            # --------------------------------------
            # Other changes
            # --------------------------------------

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


        # ------------------------------------------
        # Page completed successfully
        # ------------------------------------------

        pages_successful += 1

        update_scrape_progress(
            scrape_run_id,
            page_number
        )

        print()
        print(
            f"PAGE {page_number} "
            "COMPLETED AND CHECKPOINTED."
        )


    except Exception as error:

        pages_failed += 1

        error_message = {
            "page": page_number,
            "error": str(error)
        }

        errors.append(
            error_message
        )

        print()
        print(
            f"ERROR ON PAGE {page_number}: "
            f"{error}"
        )

        print(
            "This page was NOT marked as completed."
        )

        break


    # --------------------------------------------------
    # Delay before next page
    # --------------------------------------------------

    if page_number < end_page:

        print()
        print(
            f"WAITING {PAGE_DELAY_SECONDS} "
            "SECONDS BEFORE NEXT PAGE..."
        )

        time.sleep(
            PAGE_DELAY_SECONDS
        )


# --------------------------------------------------
# Determine run status
# --------------------------------------------------

scrape_finished_at = datetime.now(
    timezone.utc
)


if pages_failed > 0:

    run_status = "partial"

elif pages_successful == pages_attempted:

    run_status = "success"

else:

    run_status = "partial"


# --------------------------------------------------
# Determine actual last completed page
# --------------------------------------------------

if pages_successful > 0:

    last_completed_page = (
        start_page + pages_successful - 1
    )

else:

    incomplete_run = get_latest_incomplete_run(
        SOURCE_ID
    )

    if incomplete_run:

        last_completed_page = incomplete_run[2]

    else:

        last_completed_page = 0


# --------------------------------------------------
# Finish scrape run
# --------------------------------------------------

finish_scrape_run(
    scrape_run_id=scrape_run_id,
    finished_at=scrape_finished_at,
    pages_attempted=pages_attempted,
    pages_successful=pages_successful,
    pages_failed=pages_failed,
    properties_found=properties_found,
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
    "=========================================="
)

print(
    "SCRAPE COMPLETE."
)

print(
    "=========================================="
)

print(
    f"Scrape run ID: "
    f"{scrape_run_id}"
)

print(
    f"Total properties reported by Zameen: "
    f"{total_properties}"
)

print(
    f"Total pages available: "
    f"{total_pages}"
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
    f"Properties processed: "
    f"{properties_found}"
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
    f"Last completed page: "
    f"{last_completed_page}"
)

print(
    f"Run status: "
    f"{run_status}"
)


if errors:

    print()
    print(
        "ERRORS:"
    )

    for error in errors:

        print(
            f"- {error}"
        )