# -*- coding: utf-8 -*-

import os, sys, subprocess
from pathlib import Path
import shutil

import tempfile

#pip install pyyaml
#import pyaml
import yaml
#pip install pysmb
from smb.SMBConnection import SMBConnection
#from smb.base.SharedFile import SharedFile

import hashlib

import argparse

# for key, value in os.environ.items():
#     print(f'{key}: {value}')

def createParser ():
    parser = argparse.ArgumentParser()
    parser.add_argument ('-n', '--name', required=True)
 
    return parser

class SambaHelpers(object):
    def __init__(self, user, password):
        self.__username = user
        self.__password = password
        self.service_name = None
        self.storageConfig = {} 
        self.fullPublicPath = ""
        self.package_dir = ""
        self.servername = None
        self.dest_path = ""
        self.dirs , self.nondirs = [], []
        self.SetData()
        self.__connect(self.servername)
        self.service_name, self.dest_path = self.CheckShareName(str(self.storageConfig.get('publication_path',None)),None)

    def __connect(self, serverName):
        IS_DIRECT_TCP = False
        SMB_PORT = 139 if IS_DIRECT_TCP is False else 445
        self.conn = SMBConnection(self.__username, self.__password, '','',use_ntlm_v2 = True, is_direct_tcp=IS_DIRECT_TCP)
        self.conn.connect(serverName, 139)
        #print("Connected")

    def list_shares(self):
        '''
            получить список всех доступных ресурсов на сервере
        '''
        #print(self.conn)
        #self.__connect(self.servername)
        return [x.name for x in self.conn.listShares()]
    
    def list(self, path):
        ' список файлов на ресурсе '
        #print("list --------",self.service_name, path)
        filelist = self.conn.listPath(self.service_name, path, pattern='*')
        if len(filelist) > 0:
            #print("Found listed files")
            #return [x.name for x in self.conn.listShares()]
            for name in filelist:
                if name.isDirectory:
                    if name.filename not in [u'.', u'..']:
                        self.dirs.append(name.filename)
                else:
                    self.nondirs.append(name.filename)
            return self.nondirs
            #return [x.filename for x in filelist]
            # for f in filelist:
            #     print(f.filename)
        else:
            print("No files to list, this a problem. Exiting...")
            exit(255)
        #return filelist
    
    def CreateRemoteDir(self, fullpath, path, nameproject):
        '''
            создание директории на сервере
        '''
        self.error = None
        #print(self.CheckExistsDirectory(self.service_name, path))
        #print('createRemoteDir - ENTER', self.service_name, path, nameproject)
        if not self.CheckExistsDirectory(self.service_name, path, nameproject):
            #print('createRemoteDir - TRUE', self.service_name, path, nameproject)
            self.conn.createDirectory(self.service_name, path+nameproject)
            #else:
            #    print("Path exists")

    def CheckExistsDirectory(self, fullpath, path, nameproject):
        # working connection ... to check if a directory exists, ask for its attrs
        #attrs = self.conn.getAttributes(self.service_name, path, timeout=30)
        #print("CheckExistsDirectory",self.service_name, path, nameproject )
        #filelist = self.conn.listPath(self.service_name,path)
        #print(fullpath)
        #print(path)
        #print(nameproject)
        self.list(path)
        #dirlist = self.dirs
        #print(dirlist)
        #return x.name for x in self.conn.listShares()
        result=0
        for f in self.dirs:
            if nameproject == f:
                result+=1
            #         print("Directory: ",f.filename , nameproject)
            # if f.isDirectory:
            #     #print("Directory: ", nameproject, f.filename)
            #     if nameproject == f.filename :
            #         result+=1
            #         print("Directory: ",f.filename , nameproject)
            #     #return False
            # else:
            #     print("File: ", f)
        if result > 0:
            return True
        return False

    def CheckShareName(self, path, service_name=None):
        '''
            проверка доступности общего ресурса заданного в storagedata.yml
        '''
        #print('service_name ',service_name)
        if service_name:
            return service_name, path
        available_shares = [x.name for x in self.conn.listShares()]
        #available_shares = self.list(path)
        #print('CheckShareName ', available_shares)
        #print('CheckShareName-path ', path)
        if not service_name:
            first_dir = path.split("/")[1].lower()
            #print(first_dir)
            if first_dir in available_shares:
                #logger.info("Path {} matches share name {}".format(
                #    path, first_dir))
                service_name, path = self.FindSmbPath(path)
            elif self.service_name:
                service_name = self.service_name
        return service_name, path

    # def CheckShareName(self, path, service_name=None):
    #     '''
    #         проверка доступности общего ресурса заданного в storagedata.yml
    #     '''
    #     if service_name:
    #         return service_name, path
    #     available_shares = [x.lower() for x in self.list_shares()]
    #     print('CheckShareName', available_shares)
    #     if not service_name:
    #         first_dir = path.split("/")[1].lower()
    #         #print(first_dir)
    #         if first_dir in available_shares:
    #             #logger.info("Path {} matches share name {}".format(
    #             #    path, first_dir))
    #             service_name, path = self.FindSmbPath(path)
    #         elif self.service_name:
    #             service_name = self.service_name
    #     return service_name, path
    
    def FindSmbPath(self, path):
        split_path = path.split("/")
        #print("split_path: %s  --------- path: %s",split_path, path)
        #print("split+path+join %s ------ %s ",split_path[1], "/".join(split_path[2:]))
        return split_path[1], "/".join(split_path[2:])
    
    def CopyFileToSambaShare(self, fileName, shareName):
        file_obj=open(fileName, 'rb')
        #print(file_obj.name)
        self.conn.storeFile(self.service_name, "{0}/{1}".format(shareName,file), file_obj)
    
    def CopyFilesToSambaShare(self, inputDir, shareName):
        '''
            копирование всех файлов (deb) на удаленный сервер
            inputDir - локальная текущая директория с артефактами сборки 
            self.service_name - общая папка c доступом по самбе (public)
            shareName - полный путь к публикации файлов на сторадж сервер относительно self.service_name
        '''
        #print('CopyFilesToSambaShare',inputDir ,shareName, self.service_name)
        files = os.listdir(inputDir)
        print(files)
        for file in files:
            if file.endswith('.deb') or file.endswith('.7z') or file.endswith('.dat'):
                #print(file)
                try:
                    with open(inputDir+file, 'rb') as file_obj:
                    #    print(file)
                    #file_obj=open(file, 'rb')
                    #print(os.path.isfile(inputDir+file))
                        if os.path.isfile(inputDir+file):
                        #    print('------------------------------', file)
                        #    file_obj = open(inputDir+file, 'rb')
                        #    file_obj.seek(0)
                            #self.conn.storeFile(remote_path, FILE_NAME, f)
                            print("//{0}/{1}/{2}/{3}".format( self.servername, self.service_name, shareName, file))
                            count_byte=self.conn.storeFile(self.service_name, "/{0}/{1}".format(shareName, file), file_obj)
                            print("Передано: %d bytes" % count_byte)
                    #    file_obj.close()
                except Exception as e:
                    raise Exception('[SMB] An error occurred while loading the result: '+str(e))
            # else: 
            #     print("не deb: ",file)
                # try:
                #     with open(inputDir+file, 'rb') as file_obj:
                #         if os.path.isfile(inputDir+file):
                #             print("//{0}/{1}/{2}/{3}".format( self.servername, self.service_name, shareName, file))
                #             count_byte=self.conn.storeFile(self.service_name, "/{0}/{1}".format(shareName, file), file_obj)
                #             print("Передано: %d bytes" % count_byte)
                # except Exception as e:
                #     raise Exception('[SMB] An error occurred while loading the result: '+str(e))

            # try:
            #     self.conn.close()
            # except:
            #     print("[SMB]: Can not close connection")
 
    def opener(path, flags):
        return os.open(path, flags, dir_fd=dir_fd)
    
    def GetSystemPlatform(self):
        return True if sys.platform.startswith('linux') else False
    
    #def PublicArtifact(self, fullPublicPath, dest_path, np_v_path):
    def PublicArtifact(self, np_v_path):
        #if self.GetSystemPlatform():
            #print("\nName of the OS system:", platform.system())
        dest_path_copy = self.dest_path
        split_path = np_v_path.split("/")
        #split_path[0], "/".join(split_path[1:])
        for x in split_path:
            #print(self.dest_path, '1---', x+'\n')
            #print(dest_path_copy, '2---', x+'\n')
            self.CreateRemoteDir(self.fullPublicPath, dest_path_copy, x)
            dest_path_copy=dest_path_copy+x+'/'
        self.CopyFilesToSambaShare(self.package_dir, dest_path_copy)
        #self.CopyFilesToSambaShare(self.package_dir, self.dest_path+np_v_path)
        #else:
        #    package_dir = os.environ.get('PACKAGE_DIRECTORY','/home/user/package/')
        #    self.CreateRemoteDir(fullPublicPath, dest_path, nameProject)
        #    self.CopyFilesToSambaShare(package_dir, dest_path+nameProject)
            #package_dir = os.environ.get('PACKAGE_DIRECTORY','c:/home/user/package/')
            #self.CreateRemoteDir(fullPublicPath, dest_path, nameProject+'.'+version+'/'+os.environ.get('TYPE_BUILD','Release'))
            #self.CopyFilesToSambaShare(package_dir, dest_path+nameProject+'.'+version+'/'+os.environ.get('TYPE_BUILD','Release'))
    #    #smbHelper.CopyFilesToSambaShare(os.path.dirname(__file__)+'\\',dest_path+nameProject)

    def md5sum(self, f, block_size=None):
        """Returns the MD5 checksum"""
        if block_size is None:
            block_size = 4096
        hash = hashlib.md5()
        # def download(self,file):
        # fileobj = open(file,'wb')
        # self.server.retrieveFile(self.sharename,fileobj)
        # print "file has been downloaded in current dir"
        with tempfile.NamedTemporaryFile() as file_obj:
             self.conn.retrieveFile(self.service_name, f, file_obj)
             file_obj.seek(0)
             content = file_obj.read()
             #.decode('utf-8', 'ignore').translate({ord('\u0000'): None})
        #with open(f, 'rb') as fh:
            #block = fh.read(block_size)
        #    self.conn.retrieveFile(f,fh)
             while content:
                hash.update(content)
                content = file_obj.read(block_size)
        return hash.hexdigest()
    
    def md5sums(self, basedir=None, block_size=None):
        print(self.dest_path)
        filelist = self.list(self.dest_path+basedir)
        print(filelist)
        for f in filelist:
            #ff = "//"+self.servername+'/'+self.service_name+'/'+self.dest_path+basedir+'/'+f
            ff = '/'+self.dest_path+basedir+'/'+f
            print( self.md5sum(ff, block_size=block_size), f)
            with open(self.package_dir+'sums.dat', 'a+') as fsums:
                fsums.write(self.md5sum(ff, block_size=block_size)+'\t'+f+'\n')
                    
        #return x.name for x in self.conn.listShares()
        #result=0
        #for f in filelist:
        #    if nameproject == f:


    # def md5sums(self, basedir=None, block_size=None):
    #     """Yields (, ) tuples for files within the basedir.
    #     """
    #     basedir = self.fullPublicPath+basedir
    #     print(basedir)
    #     for f in list_files(basedir=basedir):
    #         yield (f, md5sum(f, block_size=block_size))

    def GetDataStorage(self):
        '''
            получение данных для копирования на сторадж сервер 
        '''
        with open(os.path.realpath('conandata.yml')) as file:
        #with open('/home/user/'+'conandata.yml') as file:
            try:
                self.storageConfig = yaml.safe_load(file) 
                #print(storageConfig)
            except yaml.YAMLError as exc:
                print(exc)
        return self.storageConfig["storage"]
            #print(storageConfig[f'{server}'])
    
    def SetData(self):
        self.storageConfig = self.GetDataStorage()
        self.fullPublicPath = "//"+str(self.storageConfig.get('server','127.0.0.1')) +str(self.storageConfig.get('publication_path',None))
        self.servername = str(self.storageConfig.get('server','127.0.0.1'))
        self.package_dir = os.environ.get('PACKAGE_DIRECTORY','/home/user/package/')
        #print(self.fullPublicPath)

    def CloseConnection(self):
        self.conn.close()
