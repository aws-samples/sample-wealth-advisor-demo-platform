#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

mkdir -p /tmp/lambda_layer/python/lib/python3.9/site-packages

pip install -r "$SCRIPT_DIR/layer/requirements.txt" -t /tmp/lambda_layer/python/lib/python3.9/site-packages

cd /tmp/lambda_layer
zip -r "$SCRIPT_DIR/lambda_layer.zip" .

echo "Lambda layer created at $SCRIPT_DIR/lambda_layer.zip"