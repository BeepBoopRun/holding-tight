#!/bin/sh

mkdir raw
cd raw


[ ! -f ncbi-blast-2.17.0+-x64-linux.tar.gz ] && echo "Downloading blast binary..." && wget 'https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.17.0/ncbi-blast-2.17.0+-x64-linux.tar.gz'
[ ! -f ncbi-blast-2.17.0+-x64-linux.tar.gz.md5 ] && echo "Downloading blast binary md5checksum..." && wget 'https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.17.0/ncbi-blast-2.17.0+-x64-linux.tar.gz.md5'

md5sum -c 'ncbi-blast-2.17.0+-x64-linux.tar.gz.md5' || { echo "BAD MD5SUM"; exit; } 

tar -xzf ncbi-blast-2.17.0+-x64-linux.tar.gz -C ..

cd ..
python makeblastdb.py
