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
    finish_scrape_run
)


SOURCE_ID = 1

# --------------------------------------------------
# Scrape range
#
# Keep this at 5 while testing.
#
# Later, change MAX_PAGES to None to scrape all
# remaining pages until the end of the website.
# --------------------------------------------------

MAX_PAGES = 5

PAGE_DELAY_SECONDS = 3


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
                    status,
                    pages_attempted,
                    pages_successful,
                    pages_failed,
                    properties_found,
                    new_properties,
                    price_increases,
                    price_decreases,
                    unchanged_properties,
                    no_longer_detected
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


def get_seen_listing_ids(
    scrape_run_id
):

    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT DISTINCT
                    p.listing_id
                FROM property_observations po
                JOIN properties p
                    ON p.id = po.property_id
                WHERE po.scrape_run_id = %s
                """,
                (scrape_run_id,)
            )

            rows = cursor.fetchall()

            return {
                row[0]
                for row in rows
            }

    finally:

        connection.close()


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
# Check for an unfinished scrape
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

    # ----------------------------------------------
    # Load statistics already checkpointed for this
    # run.
    # ----------------------------------------------

    previous_pages_attempted = incomplete_run[4]
    previous_pages_successful = incomplete_run[5]
    previous_pages_failed = incomplete_run[6]

    previous_properties_found = incomplete_run[7]
    previous_created_count = incomplete_run[8]

    previous_price_increases = incomplete_run[9]
    previous_price_decreases = incomplete_run[10]

    previous_unchanged_properties = incomplete_run[11]
    previous_no_longer_detected = incomplete_run[12]

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

    print()
    print(
        "CHECKPOINTED RUN STATISTICS:"
    )

    print(
        f"Pages attempted: "
        f"{previous_pages_attempted}"
    )

    print(
        f"Pages successful: "
        f"{previous_pages_successful}"
    )

    print(
        f"Pages failed: "
        f"{previous_pages_failed}"
    )

    print(
        f"Properties processed: "
        f"{previous_properties_found}"
    )

    print(
        f"New properties: "
        f"{previous_created_count}"
    )

    print(
        f"Price increases: "
        f"{previous_price_increases}"
    )

    print(
        f"Price decreases: "
        f"{previous_price_decreases}"
    )

    print(
        f"Unchanged prices: "
        f"{previous_unchanged_properties}"
    )


else:

    start_page = 1

    scrape_started_at = datetime.now(
        timezone.utc
    )

    scrape_run_id = start_scrape_run(
        SOURCE_ID,
        scrape_started_at,
        total_pages
    )

    # ----------------------------------------------
    # New run starts with zero counters.
    # ----------------------------------------------

    previous_pages_attempted = 0
    previous_pages_successful = 0
    previous_pages_failed = 0

    previous_properties_found = 0
    previous_created_count = 0

    previous_price_increases = 0
    previous_price_decreases = 0

    previous_unchanged_properties = 0
    previous_no_longer_detected = 0

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
# Load listings already processed in this run.
#
# This prevents duplicate observations when a
# scrape resumes after an interruption.
# --------------------------------------------------

seen_listing_ids = get_seen_listing_ids(
    scrape_run_id
)

print()

print(
    f"LISTINGS ALREADY RECORDED "
    f"IN THIS RUN: {len(seen_listing_ids)}"
)


# --------------------------------------------------
# Determine the end page
#
# If MAX_PAGES is 5:
#     scrape at most 5 pages.
#
# If MAX_PAGES is None:
#     scrape all remaining pages.
# --------------------------------------------------

if MAX_PAGES is None:

    end_page = total_pages

else:

    end_page = min(
        start_page + MAX_PAGES - 1,
        total_pages
    )


# --------------------------------------------------
# Check whether the entire crawl is already done
# --------------------------------------------------

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
    f"SCRAPE RANGE: "
    f"PAGE {start_page} TO PAGE {end_page}"
)

print(
    f"PAGES TO SCRAPE: "
    f"{pages_to_scrape}"
)


# --------------------------------------------------
# Counters
#
# These begin with the statistics already stored
# in the database when a run is resumed.
# --------------------------------------------------

pages_attempted = previous_pages_attempted
pages_successful = previous_pages_successful
pages_failed = previous_pages_failed

properties_found = previous_properties_found
created_count = previous_created_count
updated_count = 0

price_increases = previous_price_increases
price_decreases = previous_price_decreases
unchanged_properties = previous_unchanged_properties

price_unavailable = 0

property_changes = 0

duplicates_skipped = 0

errors = []


# --------------------------------------------------
# Scrape pages
# --------------------------------------------------

for page_number in range(
    start_page,
    end_page + 1
):

    url = build_page_url(
        page_number
    )

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
        # Remove duplicates
        # ------------------------------------------

        unique_page_properties = []

        page_seen_listing_ids = set()

        for property_data in page_properties:

            listing_id = property_data.listing_id

            if (
                listing_id in seen_listing_ids
                or listing_id in page_seen_listing_ids
            ):

                duplicates_skipped += 1

                print(
                    f"DUPLICATE SKIPPED | "
                    f"{listing_id}"
                )

                continue

            page_seen_listing_ids.add(
                listing_id
            )

            unique_page_properties.append(
                property_data
            )


        print(
            f"UNIQUE PROPERTIES ON PAGE {page_number}: "
            f"{len(unique_page_properties)}"
        )


        if len(unique_page_properties) != len(
            page_properties
        ):

            skipped_on_page = (
                len(page_properties)
                - len(unique_page_properties)
            )

            print(
                f"DUPLICATES SKIPPED ON PAGE "
                f"{page_number}: "
                f"{skipped_on_page}"
            )


        # ------------------------------------------
        # Save entire page atomically.
        #
        # The database function now also checkpoints
        # the cumulative scrape statistics.
        # ------------------------------------------

        try:

            results = save_properties_page(
                unique_page_properties,
                SOURCE_ID,
                scrape_run_id,
                page_number
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
        # Only remember listing IDs AFTER the
        # entire page transaction successfully
        # committed.
        # ------------------------------------------

        seen_listing_ids.update(
            page_seen_listing_ids
        )


        # ------------------------------------------
        # Process database results
        #
        # The cumulative database counters were
        # already checkpointed atomically.
        # ------------------------------------------

        for property_data, result in zip(
            unique_page_properties,
            results
        ):

            if result["action"] == "created":

                print(
                    f"NEW PROPERTY | "
                    f"{property_data.listing_id}"
                )

            elif result["action"] == "updated":

                pass


            # --------------------------------------
            # Price status
            # --------------------------------------

            price_status = result[
                "price_status"
            ]


            if price_status == "PRICE UP":

                print(
                    f"PRICE UP | "
                    f"{property_data.listing_id}"
                )


            elif price_status == "PRICE DOWN":

                print(
                    f"PRICE DOWN | "
                    f"{property_data.listing_id}"
                )


            # --------------------------------------
            # Other property changes
            # --------------------------------------

            changed_fields = result[
                "changed_fields"
            ]


            if changed_fields:

                print(
                    f"PROPERTY CHANGED | "
                    f"{property_data.listing_id} | "
                    f"{', '.join(changed_fields)}"
                )


        # ------------------------------------------
        # Update local counters from this page.
        #
        # These are used for the final finish call.
        # The database already checkpointed the
        # cumulative values atomically.
        # ------------------------------------------

        page_created_count = sum(
            1
            for result in results
            if result["action"] == "created"
        )

        page_updated_count = sum(
            1
            for result in results
            if result["action"] == "updated"
        )

        page_price_up_count = sum(
            1
            for result in results
            if result["price_status"] == "PRICE UP"
        )

        page_price_down_count = sum(
            1
            for result in results
            if result["price_status"] == "PRICE DOWN"
        )

        page_unchanged_count = sum(
            1
            for result in results
            if result["price_status"] == "UNCHANGED"
        )

        page_price_unavailable_count = sum(
            1
            for result in results
            if result["price_status"]
            == "PRICE UNAVAILABLE"
        )

        page_property_change_count = sum(
            1
            for result in results
            if result["changed_fields"]
        )


        pages_attempted += 1
        pages_successful += 1

        properties_found += len(
            results
        )

        created_count += (
            page_created_count
        )

        updated_count += (
            page_updated_count
        )

        price_increases += (
            page_price_up_count
        )

        price_decreases += (
            page_price_down_count
        )

        unchanged_properties += (
            page_unchanged_count
        )

        price_unavailable += (
            page_price_unavailable_count
        )

        property_changes += (
            page_property_change_count
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


    # ----------------------------------------------
    # Delay between pages
    # ----------------------------------------------

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
# Finish scrape
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
# Determine last completed page
#
# The database checkpoint is authoritative.
# --------------------------------------------------

latest_run = get_latest_incomplete_run(
    SOURCE_ID
)

if latest_run and latest_run[0] == scrape_run_id:

    last_completed_page = latest_run[2]

else:

    last_completed_page = end_page


# --------------------------------------------------
# Update scrape run
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
    no_longer_detected=previous_no_longer_detected,
    status=run_status,
    errors=json.dumps(errors)
)


# --------------------------------------------------
# Final summary
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
    f"Duplicates skipped: "
    f"{duplicates_skipped}"
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