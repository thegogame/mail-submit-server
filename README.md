# mail-submit-server
email media to Breadcrumb

- postfix smtp mail server running on an EC2 instance accepts inbound mail forwarded from gmail and has ability to send error notification emails outbound
- inotify script watches Maildir for new mail and runs parse_maildir.py
- parse_maildir.py retrieves new mail from the Maildir inbox, finds waypoint id, updates waypoint through Breadcrumb API, uploads attachments to S3, discards mail
- if parse fails for any reason, error notification email is sent, inotify loop breaks and the parent supervisor process is stopped
- stateserver.py is a micro HTTP server that responds to GET requests from Pingdom and returns 200 OK if inotify process is still running, else an error code and Pingdom will notify tech team that service is down 
