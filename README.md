# Linux Server Project: Item Catalog

DNS: http://ec2-13-228-232-119.ap-southeast-1.compute.amazonaws.com/
IP address: 13.228.232.119
SSH port: 2200

### Website:

* Requires gmail login
* For JSON API resource info, please add '/catalog/<topicname>/JSON'

### Stack:

* Python2
* Postgresql / SQLAlchemy
* Flask
* Apache2

### Directory structure

```
/var/www/catalog  -- catalog.wsgi
                  -- catalog (folder) -- __init__.py 
									     database_setup.py
									     static
									     templates
									     client_secrets1.json                  						
```

### ufw status

```
To                         Action      From
--                         ------      ----
2200/tcp                   ALLOW       Anywhere                  
80/tcp                     ALLOW       Anywhere                  
123                        ALLOW       Anywhere                  
8000/tcp                   ALLOW       Anywhere                  
5432                       ALLOW       Anywhere                  
2200/tcp (v6)              ALLOW       Anywhere (v6)             
80/tcp (v6)                ALLOW       Anywhere (v6)             
123 (v6)                   ALLOW       Anywhere (v6)             
8000/tcp (v6)              ALLOW       Anywhere (v6)             
5432 (v6)                  ALLOW       Anywhere (v6)  
```

### Timezone

```
/var/www/catalog/catalog$ timedatectl status | grep "Time zone"
Time zone: Etc/UTC (UTC, +0000)
```

### /var/www/catalog/catalog.wsgi

```
#!/usr/bin/python
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, "/var/www/catalog/")

from catalog import app as application
application.secret_key = 'super_secret_key'
```

### /etc/apache2/sites-enabled/000-default.conf

```
<VirtualHost *:80>
                ServerName 13.228.232.119
                ServerAdmin admin@13.228.232.119
                WSGIScriptAlias / /var/www/catalog/catalog.wsgi
                <Directory /var/www/catalog/catalog/>
                        Order allow,deny
                        Allow from all
                </Directory>
                Alias /static /var/www/catalog/catalog/static
                <Directory /var/www/catalog/catalog/static/>
                        Order allow,deny
                        Allow from all
                </Directory>
                ErrorLog ${APACHE_LOG_DIR}/error.log
                LogLevel warn
                CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
```

### /etc/postgresql/9.5/main/postgresql.conf

```
listen_addresses = '*'                  
port = 5432
```

### /etc/postgresql/9.5/main/pg_hba.conf

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
# "local" is for Unix domain socket connections only
local   all             all                                     peer
# IPv4 local connections:
host    all             all             127.0.0.1/32            md5
# IPv6 local connections:
host    all             all             ::1/128                 md5
# Allow replication connections from localhost, by a user with the
# replication privilege.
#local   replication     postgres                                peer
#host    replication     postgres        127.0.0.1/32            md5
#host    replication     postgres        ::1/128                 md5         
```

### Resources for reference

* Flask on Ubuntu: https://www.digitalocean.com/community/tutorials/how-to-deploy-a-flask-application-on-an-ubuntu-vps                    
* Database engine configuration: http://docs.sqlalchemy.org/en/latest/core/engines.html
* Setting up Postgresql on Ubuntu: https://www.digitalocean.com/community/tutorials/how-to-secure-postgresql-on-an-ubuntu-vps
* Locale setting (can face when installing modules): https://askubuntu.com/questions/162391/how-do-i-fix-my-locale-issue
* Change timezone: https://askubuntu.com/questions/138423/how-do-i-change-my-timezone-to-utc-gmt

