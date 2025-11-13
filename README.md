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
docker compose -f compose.yaml -f compose.admin.yaml up --build --watch --force-recreate --remove-orphans
```
To see the site, go to *localhost:8000*.

> [!WARNING]  
> DJANGO_SECRET_KEY in .env should be changed when setting up prod!
