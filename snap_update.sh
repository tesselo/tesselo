#!/usr/bin/env bash

# Script to update snap. This should be a one liner, but requires a hack. The
# strange hack is necessary because the update command does not automatically
# terminate after finishing. The hack works but we have to add another line to
# ignore the error code.
# Refs:
# https://forum.step.esa.int/t/snap-update-hangs/30529/2
# https://senbox.atlassian.net/wiki/spaces/SNAP/pages/30539785/Update+SNAP+from+the+command+line
# https://stackoverflow.com/questions/68250804/how-can-i-ignore-dockerfile-non-zero-return-codes
snap --nosplash --nogui --modules --update-all 2>&1 | while read -r line; do
    echo "$line"
    [ "$line" = "updates=0" ] && sleep 2 && pkill -TERM -f "snap/jre/bin/java"
done

echo "Finished updating SNAP."
