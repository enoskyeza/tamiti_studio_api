# Environment Variables

The application relies on the following environment variables. Create a `.env` file or set them in your environment before running the project.

| Variable | Description | Default |
| --- | --- | --- |
| `SECRET_KEY` | **Required.** Django secret key. | none |
| `ALLOWED_HOSTS` | Comma-separated list of hostnames served by Django. | empty |
| `DB_ENGINE` | Django database engine. | `django.db.backends.sqlite3` |
| `DB_NAME` | Database name or path. | `db.sqlite3` in project root |
| `DB_USER` | Database user. | empty |
| `DB_PASSWORD` | Database password. | empty |
| `DB_HOST` | Database host. | empty |
| `DB_PORT` | Database port. | empty |
| `EMAIL_BACKEND` | Django email backend. | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | Email server host. | empty |
| `EMAIL_PORT` | Email server port. | `587` |
| `EMAIL_USE_TLS` | Whether to use TLS for email. (`True`/`False`) | `True` |
| `EMAIL_HOST_USER` | Email server username. | empty |
| `EMAIL_HOST_PASSWORD` | Email server password. | empty |
| `DEFAULT_FROM_EMAIL` | Default address used for outgoing email. | `hello@tamiti.com` |

These settings allow the application to be configured for different environments without modifying the source code.
