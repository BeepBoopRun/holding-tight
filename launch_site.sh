#!/bin/sh
# used for testing, not prod!
# open localholst:8000 in browser to see the site
docker run -it --rm -p 8000:8000 $(docker build -q .)%