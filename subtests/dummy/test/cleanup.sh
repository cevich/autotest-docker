#!/bin/bash

echo "# docker kill $(cat that_one)"
echo "# docker rm $(cat that_one)"
if [ "$(cat this_one)" != "$default_fqin" ]
then
    echo "# docker rmi $(cat this_one)"
fi
