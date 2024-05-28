#!/bin/bash

while true; do
    read LINE
    echo "You have written $LINE"
    if [ "$LINE" == "q" ]; then
        break
    fi
done
