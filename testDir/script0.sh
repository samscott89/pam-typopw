#!/bin/bash

fullpath="/home/yuval/pam-typopw/testDir"
bash ${fullpath}/longBg.sh.tmp >> ${fullpath}/longBg.out &
echo "meanwhile"
echo "lets sit and talk"
