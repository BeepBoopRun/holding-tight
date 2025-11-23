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
> You **NEED** to modify all the files inside the secrets directory, if the server is to be used for anything other than small testing.

> [!IMPORTANT]  
> Inside the .env file, you can configure some aspect of the website, if you plan to use it long-term, you should look through them.
