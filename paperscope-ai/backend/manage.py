#!/usr/bin/env python
import os
import sys
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and your "
            "virtual environment is activated?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()