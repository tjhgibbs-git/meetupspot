import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set the Django environment
DJANGO_ENV = os.getenv("DJANGO_ENV", "development")

if DJANGO_ENV == "production":
    from .production import *
else:
    from .development import *