from fabric.api import env, put, run, sudo
from fabric.contrib.project import rsync_project

from config.settings import *

env.hosts = hosts
env.user = user
env.key_filename = key_filename

def setup():
    sudo('apt-get update')
    run('mkdir -p /home/ubuntu/mailsubmit/logs')
    run('mkdir -p /home/ubuntu/Maildir/new')
    deploy()

    ### postfix config ###
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y postfix')

    put('config/main.cf', '/etc/postfix', use_sudo=True)
    sudo('postconf -e "myhostname = %s"' % ec2_public_dns)
    sudo('postconf -e "mydestination = %s, localhost"' % ec2_public_dns)

    sudo('echo "[mail.authsmtp.com] %s:%s" > /etc/postfix/sasl_passwd' % (
        authsmtp_username, authsmtp_password))
    sudo('postmap /etc/postfix/sasl_passwd')
    # secure sasl pw and hash db files
    sudo('chown root:root /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db')
    sudo('chmod 0600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db')
    sudo('service postfix restart')
    # test
    sudo('apt-get install -y mailutils')
    sudo('echo "postfix smtp outbound mail test" | mail -s "Subject" -a "From: media@thegogame.com" %s' % smtp_test_recipient) 

    ### requirements ###
    sudo('apt-get install -y python-pip')
    sudo('pip install dateutils requests supervisor')
    sudo('apt-get install -y inotify-tools')

    ### supervisor ###
    put('config/supervisord.conf', '/etc', use_sudo=True)
    sudo('supervisord -c /etc/supervisord.conf')

    ### nginx ###
    sudo('apt-get install -y nginx')
    put('config/nginx.conf', '/etc/nginx', use_sudo=True)
    sudo('rm /etc/nginx/sites-enabled/default')
    put('config/nginx_site.conf', '/etc/nginx/sites-enabled', use_sudo=True)
    sudo('echo "%s" > /etc/nginx/.htpasswd' % htpasswd)
    sudo('nginx -s reload')

def deploy():
    rsync_project('/home/ubuntu/mailsubmit', 'deploy/')

def config():
    ### supervisor ###
    put('config/supervisord.conf', '/etc', use_sudo=True)
    sudo('supervisorctl reload')   