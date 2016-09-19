#!/bin/bash

fullpath="/home/yuval/pam-typopw/testDir"
for i in ${fullpath}/script*.sh ; do
	 bash $i
	# if [-r "$i"]; then
	# 	. $i
	# fi
done

echo "finished all"
