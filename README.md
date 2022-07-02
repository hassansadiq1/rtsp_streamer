# rtsp_streamer
## Steps to run:
1. Start docker if it is not already running
```
docker start 3d1464092e90
```
2. Enter into the docker and go to project directory
```
docker exec -it 3d1464092e90 /bin/bash
cd /home/rtsp_streamer/
```
3.Run the application as follows
```
python3 main.py <rtsp input address> <rtsp output port>
```

Example command:
```
python3 main.py rtsp://root:pass@192.168.1.212/axis-media/media.amp 8554
```
