# rtsp_streamer
## Docker Setup
1. Clone the repository and open a terminal in its directory.
2. Build docker image by following command.
```
docker build . --tag my_image:rtsp_streamer
```
This will result in following output.
Successfully tagged my_image:rtsp_streamer   
3. Build a container from my_image
```
docker run --gpus all -it --net=host --privileged -v /tmp/.X11-unix:/tmp/.X11-unix -e DISPLAY=$DISPLAY -w /home/rtsp_streamer --name my_rtsp_streamer_v1 my_image:rtsp_streamer
```
4. Run app by following command
```
python3 main.py <rtsp input address> <rtsp output port> <mount point>
```
It will take some time on first run for setup.

## Steps to Re-run application:
1. Start docker if it is not already running
```
docker start my_rtsp_streamer_v1
```
2. Enter into the docker
```
docker exec -it my_rtsp_streamer_v1 /bin/bash
```
3.Run the application as follows
```
python3 main.py <rtsp input address> <rtsp output port> <mount point>
```

Example command:
```
python3 main.py rtsp://root:pass@192.168.1.212/axis-media/media.amp 8554 test
```
THis will give you rtsp stream at rtsp://localhost:8554/test
