#!/usr/bin/env bash

# Copy the current git repo to the container, edit/build in vscode in the container, then on closing vscode, copy them back to the host.
# 23oct2022 - put most of the functionality of this task within lxdev

container="incus_elec-dev"
workingdir="${0%/*}" 
incusdev open_workspace_in $container $workingdir
