#----------------------------------------------------------------------------------------------------------------------
# Flags
#----------------------------------------------------------------------------------------------------------------------
SHELL:=/bin/bash
CURRENT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))


#----------------------------------------------------------------------------------------------------------------------
# Docker Settings
#----------------------------------------------------------------------------------------------------------------------
DOCKER_IMAGE_NAME=hecbench-image
export DOCKER_BUILDKIT=1
export UID=$(id -u)
export GID=$(id -g)

DOCKER_RUN_PARAMS= \
	-it --rm -a stdout -a stderr -e DISPLAY=${DISPLAY} -e NO_AT_BRIDGE=1  \
	--privileged -v /dev:/dev \
	-v ${CURRENT_DIR}:/workspace \
	-v /tmp/.X11-unix:/tmp/.X11-unix   -v ${HOME}/.Xauthority:/home/root/.Xauthority \
	-e OverrideDefaultFP64Settings=1 -e IGC_EnableDPEmulation=1 \
	-e MPLCONFIGDIR="/tmp" \
	-w /workspace \
	--user $(shell id -u):$(shell id -g) \
	${DOCKER_IMAGE_NAME}


MIN_INDEX ?= "accuracy"
MAX_INDEX ?= "ace"
INCLUDE ?= ""
EXCLUDE ?= "aop burger bonds cm atomicPerf bn ced gamma-correction \
			amgmk ans axhelm b+tree backprop b+tree  backprop  bfs  cfd \
			dwt2d  gaussian  heartwall  hotspot  hotspot3D  huffman  hybridsort  \
			kmeans  lavaMD  leukocyte  lud  mummergpu  myocyte  nn  nw  \
			particlefilter  pathfinder  srad  streamcluster"

#----------------------------------------------------------------------------------------------------------------------
# Targets
#----------------------------------------------------------------------------------------------------------------------
default: syclomatic
.PHONY:  

patch:
	@$(call msg, Patching HeCBench  ...)
	@cd ./HeCBench && git checkout . 1>& /dev/null && \
		patch -p1 -i ../patches/*.patch > /dev/null

build:
	@$(call msg, Building Docker image ${DOCKER_IMAGE_NAME} ...)
	@docker build --rm . -t ${DOCKER_IMAGE_NAME}

syclomatic: build
	@$(call msg, Syclomatic Processing  ...)
	@xhost + > /dev/null
	@docker run ${DOCKER_RUN_PARAMS} bash -c '\
		source /opt/intel/oneapi/setvars.sh --force > /dev/null && \
		python3 ./syclomatic.py \
			--in_root=/workspace/HeCBench/src/ \
			--include=${INCLUDE} \
			--exclude=${EXCLUDE} \
			--min_index=${MIN_INDEX} \
			--max_index=${MAX_INDEX} \
		'

bash: build
	@$(call msg, Loging  ...)
	@docker run ${DOCKER_RUN_PARAMS} bash -c 'source /opt/intel/oneapi/setvars.sh --force > /dev/null && bash'
	

#----------------------------------------------------------------------------------------------------------------------
# helper functions
#----------------------------------------------------------------------------------------------------------------------
define msg
	tput setaf 2 && \
	for i in $(shell seq 1 120 ); do echo -n "-"; done; echo  "" && \
	echo "         "$1 && \
	for i in $(shell seq 1 120 ); do echo -n "-"; done; echo "" && \
	tput sgr0
endef

