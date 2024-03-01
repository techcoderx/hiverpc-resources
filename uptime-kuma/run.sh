#!/bin/bash

# Parse command-line options
OPTS=$(getopt -o '' --long rpc:,push-url: -n "$(basename "$0")" -- "$@")
if [ $? != 0 ]; then echo "Failed to parse options"; exit 1; fi
eval set -- "$OPTS"

rpc_url=""
push_url=""

while true; do
  case "$1" in
    --rpc ) rpc_url="$2"; shift 2 ;;
    --push-url ) push_url="$2"; shift 2 ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done

# Check if urls are provided
if [ -z "$rpc_url" ] || [ -z "$push_url" ]; then
  echo "Both --rpc and --push-url are required"
  exit 1
fi

# POST request body
data='{"id":1,"jsonrpc":"2.0","method":"database_api.get_dynamic_global_properties","params":{}}'

# Send POST request to API
response=$(curl -s -X POST -H "Content-Type: application/json" -d "$data" $rpc_url)

time_string=$(echo "$response" | jq -r .result.time)
modified_time_string="${time_string}Z"

# Then you use $modified_time_string in your jq condition like so:
if echo "$response" | jq -e --arg TIME "$modified_time_string" '(.error | not) and (.result.head_block_number | (type=="number")) and ($TIME | fromdate - now | . > -6)' > /dev/null; then
  # If all conditions passed, then call the push API
  curl -X GET $push_url
fi