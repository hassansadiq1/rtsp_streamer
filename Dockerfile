FROM nvcr.io/nvidia/deepstream:6.1-devel

RUN apt-get update
RUN apt install -y git python3 python3-pip python3.8-dev cmake g++ build-essential libglib2.0-dev libglib2.0-dev-bin python-gi-dev libtool m4 autoconf automake
WORKDIR /home/rtsp_streamer
COPY ./ ./
RUN pip3 install pyds-1.1.3-py3-none-linux_x86_64.whl
RUN CUDA_VER=11.6 make -C nvdsinfer_custom_impl_Yolo


