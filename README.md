# Installation
Start by cloning the repository:

```bash
git clone https://github.com/BeepBoopRun/holding-tight
```

To get the server running ASAP, do:
```bash
docker compose up
```

For development, do:
```bash
docker compose -f compose.yaml -f compose.admin.yaml up --watch --build
```

To see the site, go to *localhost:8000*.

Notice that this website is still a work in progress and doesn't represent the final result. Though, all feedback is welcome.

> [!WARNING]  
> DJANGO_SECRET_KEY in .env should be changed when setting up prod!

# What might change

- Cron job to clear submissions older than 30 days.

- Changing whitenoise to nginx, since we might need to serve multiple files.
