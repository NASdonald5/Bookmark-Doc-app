#!/bin/bash
#sudo nano install-Bookmarkapp.sh
# Then copy the contents and run the script.
# sudo ./install-Bookmarkapp.sh
sudo chmod +x install-Bookmarkapp.sh
#remove previous versions if any.
sudo rm -rf  Bookmark-Doc-app/
sudo git clone https://github.com/NASdonald5/Bookmark-Doc-app.git
cd Bookmark-Doc-app/
sudo docker compose up --build -d
sudo docker ps