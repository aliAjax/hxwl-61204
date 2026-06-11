from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-hxwl-61204"
DEBUG = True
ALLOWED_HOSTS = ["*"]

ROOT_URLCONF = "labfreezer.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
INSTALLED_APPS = []
MIDDLEWARE = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "freezer_samples.db",
    }
}
