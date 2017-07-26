#!/bin/bash

echo "Initialization steps should be performed here."
echo "A non-zero exit will result in this test being skipped"
echo ""
echo "All configuration variables have been exported."
echo "Including '$TMPDIR' which will automaticly be cleaned up"
echo ""
env
