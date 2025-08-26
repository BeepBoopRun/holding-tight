# Installation
Start by cloning the repository:

```bash
git clone --recursive https://github.com/BeepBoopRun/holding-tight
```

To get the server running ASAP, do:

```bash
./launch_server.sh
```
This method also cleans after itself!


To build normally, do:
```bash
docker build .
docker run -it -p 8000:8000 [IMAGE ID] 
```

To see the site, go to *localhost:8000*.

Notice that this website is still a work in progress and doesn't represent the final result. Though, all feedback is welcome.

> [!WARNING]  
> DJANGO_SECRET_KEY in .env should be changed when setting up prod!

# What might change

- Databases are stored inside the containers, which I am unsure of. They will contain cached results from calling GPCRdb, so it might be better to do something different.

- No restart mechanism after crash, dangerous!


