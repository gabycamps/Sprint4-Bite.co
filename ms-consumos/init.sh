#!/bin/bash
cd /home/ubuntu/ms-consumos
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "MONGO_URL=mongodb://localhost:27017" > .env

nohup venv/bin/python main.py > app.log 2>&1 &
echo "MS-Consumos corriendo en puerto 8001"