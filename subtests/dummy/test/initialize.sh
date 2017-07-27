#!/bin/bash

set -e
echo "$default_fqin" > this_one
echo "$(basename $config_section)_$RANDOM" > that_one
cat this_one that_one
echo "# timeout $docker_timeout $docker_path pull $(cat this_one)"
