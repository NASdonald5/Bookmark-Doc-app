#!/bin/bash

# 1. Check and install Nginx & Apache utilities if not already present
if ! command -v nginx &> /dev/null; then
    echo "Nginx not found. Installing Nginx and apache2-utils..."
    sudo apt update
    sudo apt install nginx apache2-utils -y
else
    echo "Nginx is already installed. Skipping installation."
fi

# 2. Setup Nginx Password File if it doesn't exist
if [ ! -f /etc/nginx/.htpasswd ]; then
    echo "Creating Nginx basic auth password file..."
    sudo htpasswd -c /etc/nginx/.htpasswd admin
else
    echo "Nginx password file already exists. Skipping creation."
fi

# 3. Pull/Update the Bookmark Application repository
sudo rm -rf Bookmark-Doc-app/
sudo git clone https://github.com/NASdonald5/Bookmark-Doc-app.git
cd Bookmark-Doc-app/

# 4. Spin up the Docker container
sudo docker compose up --build -d
cd ..

# 5. Setup/Update Nginx Proxy Configuration if not already linked
if [ ! -f /etc/nginx/sites-available/python_proxy ]; then
    echo "Creating Nginx proxy configuration..."
    sudo bash -c 'cat > /etc/nginx/sites-available/python_proxy << "EOF"
# Proxy for Bookmark Pro Dashboard
server {
    listen 9000;
    server_name _;

    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Proxy for Daily Server Report
server {
    listen 9001;
    server_name _;

    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF'
fi

# 6. Enable site, open firewall ports, and restart Nginx
if [ ! -L /etc/nginx/sites-enabled/python_proxy ]; then
    sudo ln -s /etc/nginx/sites-available/python_proxy /etc/nginx/sites-enabled/
fi

sudo ufw allow 9000/tcp
sudo ufw allow 9001/tcp
sudo nginx -t
sudo systemctl restart nginx

echo "Deployment and Nginx reverse proxy configuration complete!"