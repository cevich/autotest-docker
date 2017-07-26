#!/bin/bash

echo "Test steps should be performed here.  A Non-zero"
echo "exit will signal test-failure"
echo ""
echo "Current dir. ($PWD) is for results"
echo ""
echo "Other scripts, input data, etc. are in $(dirname $0)"
echo ""
echo "The same environment variables are available"
env
