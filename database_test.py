import os

import psycopg
from dotenv import load_dotenv


load_dotenv()

database_url = os.getenv("DATABASE_URL")

connection = psycopg.connect(database_url)

print("Database connection successful!")

connection.close()