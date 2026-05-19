# A simple Book Mark Manger
### Docker template:
/bookmark-app <br/>
├── app.py<br/>
├── Dockerfile<br/>
├── docker-compose.yml<br/>
└── templates/<br/>
    └── index.html<br/>
### How to run it on your own machine

#Create the file install-Bookmarkapp.sh <br/>
:~# sudo nano install-Bookmarkapp.sh  <br/>
#Then copy the contents below. <br/>

#Provide execute access to the script file <br/>
:~# sudo chmod +x install-Bookmarkapp.sh <br/>

#run the script using ./<filename>.sh<br/>
:~# sudo ./install-Bookmarkapp.sh <br/>
****************************************<br/>

# File:- install-Bookmarkapp.sh <br/>
#!/bin/bash <br/>
#remove previous versions if any.<br/>
sudo rm -rf  Bookmark-Doc-app<br/>
sudo git clone https://github.com/NASdonald5/Bookmark-Doc-app.git <br/>
cd Bookmark-Doc-app <br/>
sudo docker compose up --build -d <br/>
sudo docker ps <br/>

