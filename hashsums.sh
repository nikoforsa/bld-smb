#!/bin/bash

git config --global http.sslVerify "false"

mkdir -p ${PACKAGE_DIRECTORY}

cd ${HOME_DIRECTORY}

if [ ! -z "${GITSSHKEY}" ]; then
    git config --global core.sshCommand "ssh -i ${HOME_DIRECTORY}/.ssh/id_rsa -F /dev/null -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
    git clone git@git.com:project1/bld-smb.git
else
    git clone https://${GIT_USERNAME}:${GIT_PASSWORD}@git@git.com:project1/bld-smb.git
fi

yes | cp -i ${HOME_DIRECTORY}/conandata.yml ./bld-smb/

if [[ "${PUBLISH}" == true ]]; then
    cd ./bld-smb/
    python3 ./hash_product.py
fi

