#!/bin/bash

set -e
pwd
cat this_one that_one
echo "# docker run -i --name $(cat that_one) $(cat this_one) echo 'hello world'"
