import os
import sambahelper as sh

def __main__():
    user = ''
    password = ''
    nameProject = ''
    version = ''
    user = os.environ.get('BUILDER_USER','admin')
    password = os.environ.get('BUILDER_PASSWORD','test')
    nameProject = os.environ.get('NAME_PROJECT','test')
    version = os.environ.get('VERSION_PROJECT','0.0.1')

    smbHelper = sh.SambaHelpers(user, password)
    smbHelper.md5sums(nameProject+"/"+version)
    smbHelper.PublicArtifact(nameProject+"/"+version)
    smbHelper.CloseConnection()

__main__()