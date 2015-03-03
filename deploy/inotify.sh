#!/bin/sh

while true; do
  inotifywait -e create /home/ubuntu/Maildir/new | while read line; do
    echo 'You have mail!';
    date
    python parse_maildir.py
  done
  if [ "$?" != "0" ]; then break; fi
done
exit 1  
