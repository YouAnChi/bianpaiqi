#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python3 -m yinqing.main run "$@"
