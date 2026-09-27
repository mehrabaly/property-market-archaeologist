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
                SELECT id, name, base_url, active
                FROM sources
                """
            )

            return cursor.fetchall()

    finally:
        connection.close()


def start_scrape_run(
    source_id,
    started_at
):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO scrape_runs (
                    source_id,
                    started_at,
                    status
                )
                VALUES (
                    %s,
                    %s,
                    %s
                )
                RETURNING id
                """,
                (
                    source_id,
                    started_at,
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


def save_property(property_data, source_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    price,
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

            if existing_property:

                property_id = existing_property[0]
                previous_price = existing_property[1]
                first_observed_at = existing_property[2]

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
                        property_data.url,
                        first_observed_at
                        or property_data.scraped_at,
                        property_data.scraped_at,
                        "active",
                        property_id
                    )
                )

                action = "updated"

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
                        property_data.url,
                        property_data.scraped_at,
                        property_data.scraped_at,
                        "active"
                    )
                )

                property_id = cursor.fetchone()[0]

                action = "created"

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
                    property_data.url,
                    property_data.scraped_at
                )
            )

        connection.commit()

        return {
            "action": action,
            "property_id": property_id,
            "price_status": price_status
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()