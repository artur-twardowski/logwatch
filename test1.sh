#!/bin/sh

X=0
while true; do
    >&2 echo "Stderr line $X"
    sleep 10
    ls -la --color
    X=$(( $X + 1 ))
done
