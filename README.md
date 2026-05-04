# A simple Book Mark Manger
### How to run it on your own machine
sudo nano install-Bookmarkapp.sh
#
Then copy the contents of this file and run the script.
###
### Docker template:
/bookmark-app
├── app.py
├── Dockerfile
├── docker-compose.yml
└── templates/
    └── index.html
# File:- install-Bookmarkapp.sh 

#!/bin/bash
#sudo nano install-Bookmarkapp.sh
# Then copy the contents of this file and run the script.
# sudo ./install-Bookmarkapp.sh
# Provide execute access to the script file
#sudo chmod +x install-Bookmarkapp.sh
#remove previous versions if any.
sudo rm -rf  Bookmark-Doc-app/
sudo git clone https://github.com/NASdonald5/Bookmark-Doc-app.git
cd Bookmark-Doc-app/
sudo docker compose up --build -d
sudo docker ps

