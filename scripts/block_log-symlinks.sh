#!/bin/bash

# Check for correct number of arguments
if [ "$#" -ne 4 ]; then
    echo "Usage: $0 source_dir dest_dir start_part end_part"
    exit 1
fi

source_dir="$1"
dest_dir="$2"
start_part="$3"
end_part="$4"

# Validate that start_part and end_part are numeric
if ! [[ "$start_part" =~ ^[0-9]+$ ]] || ! [[ "$end_part" =~ ^[0-9]+$ ]]; then
    echo "Error: Start and end parts must be numeric."
    exit 1
fi

# Convert to integers
start_num=$(( $start_part ))
end_num=$(( $end_part ))

# Check if start_num is greater than end_num
if (( start_num > end_num )); then
    echo "Error: Start part must be less than or equal to end part."
    exit 1
fi

# Check if source directory exists
if [ ! -d "$source_dir" ]; then
    echo "Error: Source directory '$source_dir' does not exist."
    exit 1
fi

# Create destination directory if it doesn't exist
mkdir -p "$dest_dir"

# Loop through each part number in the range
for (( i = start_num; i <= end_num; i++ )); do
    part_str=$(printf "%04d" "$i")  # Format as 4-digit string
    main_file="$source_dir/block_log_part.$part_str"
    artifacts_file="$source_dir/block_log_part.$part_str.artifacts"

    # Create symbolic links
    ln -s "$main_file" "$dest_dir/block_log_part.$part_str"
    ln -s "$artifacts_file" "$dest_dir/block_log_part.$part_str.artifacts"
done

echo "Symbolic links created successfully."