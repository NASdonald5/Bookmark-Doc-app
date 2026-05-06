# A simple Book Mark Manger
### How to run it on your own machine
sudo nano install-Bookmarkapp.sh <br/>
Then copy the contents of this file and run the script.<br/>
###
### Docker template:
/bookmark-app <br/>
├── app.py<br/>
├── Dockerfile<br/>
├── docker-compose.yml<br/>
└── templates/<br/>
    └── index.html<br/>

# File:- install-Bookmarkapp.sh <br/>

Create the file install-Bookmarkapp.sh <br/>
Then copy the contents below. <br/>
:~# sudo nano install-Bookmarkapp.sh  <br/>
Provide execute access to the script file <br/>


#!/bin/bash
#sudo nano install-Bookmarkapp.sh <br/>
#Then copy the contents of this file and run the script. <br/>
#sudo ./install-Bookmarkapp.sh <br/>
#Provide execute access to the script file <br/>
#sudo chmod +x install-Bookmarkapp.sh <br/>
#remove previous versions if any.<br/>

sudo rm -rf  Bookmark-Doc-app/
sudo git clone https://github.com/NASdonald5/Bookmark-Doc-app.git
cd Bookmark-Doc-app/
sudo docker compose up --build -d
sudo docker ps

