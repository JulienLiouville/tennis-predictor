Deployment
Local Environment
Windows
PyCharm
SQLite
Production Environment
Google Cloud VM
Ubuntu 22.04
e2-micro
tmux session
Deployment Steps
Copy Database
scp data/tennis.db user@vm-ip:~/tennis-predictor/data/
Copy Model
scp data/model.pkl user@vm-ip:~/tennis-predictor/data/
Start Session
tmux new -s tennis
Start Scheduler
python main.py run