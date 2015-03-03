
## create email account

- create new user media@thegogame.com in gmail admin
- set up auto forward to ubuntu@ec2_public_dns
- add media@thegogame.com to authsmtp registered from addresses

## create server

- instantiate ec2 ubuntu 14.04 server
- assign existing smtp security group
- generate your key.pem file

## ensure you can ssh to server

    ssh -l ubuntu -i ~/.ec2/rcm-west-key-pair.pem 54.153.73.22

## fabric

    cp settings.py.template settings.py
    // update credentials
    fab setup
