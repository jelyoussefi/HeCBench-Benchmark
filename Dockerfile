FROM intel/oneapi:latest

ARG DEBIAN_FRONTEND=noninteractive

USER root
RUN apt update -y  --allow-insecure-repositories
RUN apt install -y python3-pip
RUN pip3 install pandas fire

RUN apt install -y --allow-unauthenticated intel-oneapi-dpcpp-ct 

RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
RUN mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
RUN wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda-repo-ubuntu2204-11-8-local_11.8.0-520.61.05-1_amd64.deb
RUN dpkg -i cuda-repo-ubuntu2204-11-8-local_11.8.0-520.61.05-1_amd64.deb
RUN cp /var/cuda-repo-ubuntu2204-11-8-local/cuda-*-keyring.gpg /usr/share/keyrings/
RUN apt-get update --allow-insecure-repositories
RUN apt-get -y install cuda-toolkit-11-8

RUN echo "icpx -fsycl \$@" > /opt/intel/oneapi/dpcpp-ct/latest/bin/clang-tool && chmod +x /opt/intel/oneapi/dpcpp-ct/latest/bin/clang-tool
RUN apt install -y libgl1 libglib2.0-0  libx11-dev  python3-tk libcanberra-gtk-module libcanberra-gtk3-module libqt5widgets5
RUN pip3 install tqdm matplotlib PyQt5 cprint
RUN apt install -y rename
ENV XDG_RUNTIME_DIR='/tmp/runtime-root'


