import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg.connect(DATABASE_URL)


def get_sources():
    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    base_url,
                    active
                FROM sources
                """
            )

            return cursor.fetchall()

    finally:

        connection.close()


# --------------------------------------------------
# Scrape run
# --------------------------------------------------

def start_scrape_run(
    source_id,
    started_at,
    total_pages
):
    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO scrape_runs (
                    source_id,
                    started_at,
                    total_pages,
                    last_completed_page,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    source_id,
                    started_at,
                    total_pages,
                    0,
                    "running"
                )
            )

            scrape_run_id = cursor.fetchone()[0]

        connection.commit()

        return scrape_run_id

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


def update_scrape_progress(
    scrape_run_id,
    completed_page
):
    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE scrape_runs
                SET
                    last_completed_page = %s
                WHERE id = %s
                """,
                (
                    completed_page,
                    scrape_run_id
                )
            )

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


def finish_scrape_run(
    scrape_run_id,
    finished_at,
    pages_attempted,
    pages_successful,
    pages_failed,
    properties_found,
    new_properties,
    price_increases,
    price_decreases,
    unchanged_properties,
    no_longer_detected,
    status,
    errors
):
    connection = get_connection()

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE scrape_runs
                SET
                    finished_at = %s,
                    pages_attempted = %s,
                    pages_successful = %s,
                    pages_failed = %s,
                    properties_found = %s,
                    new_properties = %s,
                    price_increases = %s,
                    price_decreases = %s,
                    unchanged_properties = %s,
                    no_longer_detected = %s,
                    status = %s,
                    errors = %s
                WHERE id = %s
                """,
                (
                    finished_at,
                    pages_attempted,
                    pages_successful,
                    pages_failed,
                    properties_found,
                    new_properties,
                    price_increases,
                    price_decreases,
                    unchanged_properties,
                    no_longer_detected,
                    status,
                    errors,
                    scrape_run_id
                )
            )

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


# --------------------------------------------------
# Save one property using an existing connection
# --------------------------------------------------

def save_property_with_connection(
    connection,
    property_data,
    source_id
):
    with connection.cursor() as cursor:

        # ------------------------------------------
        # Find existing property
        # ------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                title,
                property_type,
                price,
                location,
                bedrooms,
                bathrooms,
                original_area,
                area_sqft,
                description,
                source_listed_at,
                url,
                first_observed_at
            FROM properties
            WHERE source_id = %s
            AND listing_id = %s
            """,
            (
                source_id,
                property_data.listing_id
            )
        )

        existing_property = cursor.fetchone()

        price_status = "NEW"
        changed_fields = []


        # ------------------------------------------
        # Existing property
        # ------------------------------------------

        if existing_property:

            property_id = existing_property[0]

            previous_title = existing_property[1]
            previous_property_type = existing_property[2]
            previous_price = existing_property[3]
            previous_location = existing_property[4]
            previous_bedrooms = existing_property[5]
            previous_bathrooms = existing_property[6]
            previous_original_area = existing_property[7]
            previous_area_sqft = existing_property[8]
            previous_description = existing_property[9]
            previous_source_listed_at = existing_property[10]
            previous_url = existing_property[11]
            first_observed_at = existing_property[12]


            # --------------------------------------
            # Price comparison
            # --------------------------------------

            if (
                previous_price is not None
                and property_data.price is not None
            ):

                if property_data.price < previous_price:

                    price_status = "PRICE DOWN"

                elif property_data.price > previous_price:

                    price_status = "PRICE UP"

                else:

                    price_status = "UNCHANGED"

            elif property_data.price is None:

                price_status = "PRICE UNAVAILABLE"


            # --------------------------------------
            # Other field comparisons
            # --------------------------------------

            if (
                property_data.title
                != previous_title
            ):

                changed_fields.append(
                    "title"
                )


            if (
                property_data.property_type
                != previous_property_type
            ):

                changed_fields.append(
                    "property_type"
                )


            if (
                property_data.location
                != previous_location
            ):

                changed_fields.append(
                    "location"
                )


            if (
                property_data.bedrooms
                != previous_bedrooms
            ):

                changed_fields.append(
                    "bedrooms"
                )


            if (
                property_data.bathrooms
                != previous_bathrooms
            ):

                changed_fields.append(
                    "bathrooms"
                )


            if (
                property_data.original_area
                != previous_original_area
            ):

                changed_fields.append(
                    "original_area"
                )


            # --------------------------------------
            # Area comparison
            # --------------------------------------

            if (
                property_data.area_sqft is not None
                and previous_area_sqft is not None
                and abs(
                    property_data.area_sqft
                    - float(previous_area_sqft)
                ) > 0.01
            ):

                changed_fields.append(
                    "area_sqft"
                )


            # --------------------------------------
            # Description comparison
            # --------------------------------------

            if (
                property_data.description
                != previous_description
            ):

                changed_fields.append(
                    "description"
                )


            # --------------------------------------
            # Source listed date comparison
            # --------------------------------------

            if (
                property_data.source_listed_at
                != previous_source_listed_at
            ):

                changed_fields.append(
                    "source_listed_at"
                )


            # --------------------------------------
            # URL comparison
            # --------------------------------------

            if (
                property_data.url
                != previous_url
            ):

                changed_fields.append(
                    "url"
                )


            # --------------------------------------
            # Update property
            # --------------------------------------

            cursor.execute(
                """
                UPDATE properties
                SET
                    title = %s,
                    property_type = %s,
                    price = %s,
                    location = %s,
                    bedrooms = %s,
                    bathrooms = %s,
                    original_area = %s,
                    area_sqft = %s,
                    description = %s,
                    source_listed_at = %s,
                    url = %s,
                    first_observed_at = %s,
                    last_observed_at = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    property_data.title,
                    property_data.property_type,
                    property_data.price,
                    property_data.location,
                    property_data.bedrooms,
                    property_data.bathrooms,
                    property_data.original_area,
                    property_data.area_sqft,
                    property_data.description,
                    property_data.source_listed_at,
                    property_data.url,
                    (
                        first_observed_at
                        or property_data.scraped_at
                    ),
                    property_data.scraped_at,
                    "active",
                    property_id
                )
            )

            action = "updated"


        # ------------------------------------------
        # New property
        # ------------------------------------------

        else:

            cursor.execute(
                """
                INSERT INTO properties (
                    source_id,
                    listing_id,
                    title,
                    property_type,
                    price,
                    location,
                    bedrooms,
                    bathrooms,
                    original_area,
                    area_sqft,
                    description,
                    source_listed_at,
                    url,
                    first_observed_at,
                    last_observed_at,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    source_id,
                    property_data.listing_id,
                    property_data.title,
                    property_data.property_type,
                    property_data.price,
                    property_data.location,
                    property_data.bedrooms,
                    property_data.bathrooms,
                    property_data.original_area,
                    property_data.area_sqft,
                    property_data.description,
                    property_data.source_listed_at,
                    property_data.url,
                    property_data.scraped_at,
                    property_data.scraped_at,
                    "active"
                )
            )

            property_id = cursor.fetchone()[0]

            action = "created"


        # ------------------------------------------
        # Save observation
        # ------------------------------------------

        cursor.execute(
            """
            INSERT INTO property_observations (
                property_id,
                title,
                property_type,
                price,
                location,
                bedrooms,
                bathrooms,
                original_area,
                area_sqft,
                description,
                source_listed_at,
                url,
                observed_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                property_id,
                property_data.title,
                property_data.property_type,
                property_data.price,
                property_data.location,
                property_data.bedrooms,
                property_data.bathrooms,
                property_data.original_area,
                property_data.area_sqft,
                property_data.description,
                property_data.source_listed_at,
                property_data.url,
                property_data.scraped_at
            )
        )


        return {
            "action": action,
            "property_id": property_id,
            "price_status": price_status,
            "changed_fields": changed_fields
        }


# --------------------------------------------------
# Save one property
# --------------------------------------------------

def save_property(
    property_data,
    source_id
):
    connection = get_connection()

    try:

        result = save_property_with_connection(
            connection,
            property_data,
            source_id
        )

        connection.commit()

        return result

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


# --------------------------------------------------
# Save an entire page atomically
# --------------------------------------------------

def save_properties_page(
    page_properties,
    source_id
):
    connection = get_connection()

    results = []

    try:

        # ------------------------------------------
        # One transaction for the entire page
        # ------------------------------------------

        for property_data in page_properties:

            result = save_property_with_connection(
                connection,
                property_data,
                source_id
            )

            results.append(
                result
            )


        # ------------------------------------------
        # Everything succeeded
        # ------------------------------------------

        connection.commit()

        return results


    except Exception:

        # ------------------------------------------
        # Something failed.
        #
        # Roll back EVERY property on this page.
        # ------------------------------------------

        connection.rollback()

        raise


    finally:

        connection.close()