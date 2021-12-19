import numpy as np
from PIL import ImageGrab

from client_sockets import *
import zlib
from datetime import time
import cv2
from socket import *
import threading
import pyaudio
import struct
import pickle
import time
from pynput.mouse import Button, Controller
from CONSTANTS import *
import os

'''
    We provide a base class here.
    You can create new sub classes based on it.
'''


class ClientSocket():
    '''
        The main process of the ClientSocket is:
        Receive: receive data -> analyze the data -> take actions (send data or others)
        Send: construct data -> send data -> (optional) wait for reply (i.e., receive data)  
    '''

    def __init__(self, addr, client, sport=None):
        '''
            @Parameters
                addr: server address
                client: the registed client
                sport: the binded port of this socket
        '''
        # Create socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addr = addr
        # You can bind the certain port with the client
        if sport is not None:
            self.sock.bind(('', sport))
        # The registered client
        self.client = client
        # Protocol related - Header
        # If they are with the same format, you can use
        # self.header_format = None
        # self.header_size = 0  
        # Instead
        self.rheader_format = None  # The receiving header format
        self.rheader_size = 0  # The size of the receiving header
        self.sheader_format = None  # The sending header format
        self.sheader_size = 0  # The size of the sending header

        # If you want to connect to the server right now
        while True:
            try:
                self.sock.connect(self.addr)
                print("Connected")
                break
            except:
                print("Could not connect to the server" + str(self.addr))
        # Create a receive_server_data threading
        self.receive_thread = threading.Thread(target=self.receive_server_data)
        # If you want to start to receive data right now
        self.receive_thread.start()

    def receive_server_data(self):
        '''
            Receive the data from the sever
            It should be a threading function
        '''
        pass

    def analyze_receive_data(self, header, data):
        '''
            Analyze the received data
            You can also combine this function within 
            the "receive_server_data", so you can ignore this function
        '''
        pass

    def send_data(self, header, data):
        '''
            This function is used to send data to the server
            It can be a threading or a normal function depend
            on different purpose
        '''
        pass

    def construct_sending_data(self, *args):
        '''
            Construct the sending data
            @Returns
                header: The header of the msg
                data: The data of the msg
        '''
        pass


class videoReceiver(threading.Thread):
    def __init__(self, port, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = ('', port)
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)

    def __del__(self):
        self.sock.close()
        try:
            cv2.destroyAllWindows()
        except:
            pass

    def run(self):
        print("videoReceiver starts...")
        self.sock.bind(self.ADDR)
        self.sock.listen(1)
        conn, addr = self.sock.accept()
        print("videoReceiver connected...")
        data = "".encode("utf-8")
        payload_size = struct.calcsize("L")  # 结果为4
        cv2.namedWindow('Remote', cv2.WINDOW_NORMAL)
        while True:
            while len(data) < payload_size:
                data += conn.recv(81920)
            packed_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_size)[0]
            while len(data) < msg_size:
                data += conn.recv(81920)
            zframe_data = data[:msg_size]
            data = data[msg_size:]
            frame_data = zlib.decompress(zframe_data)
            frame = pickle.loads(frame_data)
            cv2.imshow('Remote', frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break


class videoSender(threading.Thread):
    def __init__(self, addr, level, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = addr
        if level <= 3:
            self.interval = level
        else:
            self.interval = 3
        self.fx = 1 / (self.interval + 1)
        if self.fx < 0.3:  # 限制最大帧间隔为3帧
            self.fx = 0.3
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.cap = cv2.VideoCapture(0)

    def __del__(self):
        self.sock.close()
        self.cap.release()

    def run(self):
        print("videoSender starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("videoSender connected...")
        while self.cap.isOpened():
            ret, frame = self.cap.read()
            sframe = cv2.resize(frame, (0, 0), fx=self.fx, fy=self.fx)
            data = pickle.dumps(sframe)
            zdata = zlib.compress(data, zlib.Z_BEST_COMPRESSION)
            try:
                self.sock.sendall(struct.pack("L", len(zdata)) + zdata)
            except:
                break
            for i in range(self.interval):
                self.cap.read()
        print("videoSender connection lost...")


class audioReceiver(threading.Thread):
    def __init__(self, port, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = ('', port)
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.p = pyaudio.PyAudio()  # 实例化PyAudio,并于下面设置portaudio参数
        self.stream = None

    def __del__(self):
        self.sock.close()  # 关闭套接字
        if self.stream is not None:
            self.stream.stop_stream()  # 暂停播放 / 录制
            self.stream.close()  # 终止流
        self.p.terminate()  # 终止会话

    def run(self):
        print("audioReceiver starts...")
        self.sock.bind(self.ADDR)
        self.sock.listen(1)
        conn, addr = self.sock.accept()
        print("audioReceiver connected...")
        data = "".encode("utf-8")
        payload_size = struct.calcsize("L")  # 返回对应于格式字符串fmt的结构，L为4
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  output=True,
                                  frames_per_buffer=CHUNK
                                  )
        while True:
            while len(data) < payload_size:
                data += conn.recv(81920)
            packed_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("L", packed_size)[0]
            while len(data) < msg_size:
                data += conn.recv(81920)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            frames = pickle.loads(frame_data)
            for frame in frames:
                self.stream.write(frame, CHUNK)
        print("audioReceiver connection lost...")


class audioSender(threading.Thread):
    def __init__(self, addr, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = addr
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.p = pyaudio.PyAudio()
        self.stream = None

    def __del__(self):
        self.sock.close()
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

    def run(self):
        print("audioSender starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("audioSender connected...")
        self.stream = self.p.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  input=True,
                                  frames_per_buffer=CHUNK)
        while self.stream.is_active():
            frames = []
            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = self.stream.read(CHUNK)
                frames.append(data)
            senddata = pickle.dumps(frames)
            try:
                self.sock.sendall(struct.pack("L", len(senddata)) + senddata)
            except:
                break
        print("audioSender connection lost...")


class screenSharingSender(threading.Thread):
    def __init__(self, addr, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = addr
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.quality = 25
        self.encodeParam = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]

    def __del__(self):
        self.sock.close()

    def run(self):
        print("screenSharingSender starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("screenSharingSender connected...")
        while True:
            im = ImageGrab.grab()
            imm = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)  # 转为opencv的BGR格式
            imm = cv2.resize(imm, (1535, 863))
            img_encode = cv2.imencode(".jpg", imm, self.encode_param)[1]
            data_encode = np.array(img_encode)
            str_encode = data_encode.tostring()
            # print(len(str_encode))
            # 向服务器发送消息
            self.sock.send(str_encode)
        print("screenSharingSender connection lost...")


class screenSharingReceiver(threading.Thread):
    def __init__(self, addr, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = addr
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)

    def __del__(self):
        self.sock.close()

    def run(self):
        print("screenSharingReceiver starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("screenSharingReceiver connected...")
        while True:
            # 接受客户端消息,设置一次最多接受10240字节的数据
            recv_msg = self.sock.recv(102400)
            # 把接收到的东西解码
            msg = np.fromstring(recv_msg, np.uint8)
            img_decode = cv2.imdecode(msg, cv2.IMREAD_COLOR)
            try:
                s = img_decode.shape
                img_decode = img_decode
                temp = img_decode
            except:
                img_decode = temp
                pass
            cv2.imshow('SERVER', img_decode)
        print("screenSharingReceiver connection lost...")


class screenControlSender(threading.Thread):
    def __init__(self, addr, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = addr
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)

    def __del__(self):
        self.sock.close()

    def mouse_click(event, x, y, flags, para):
        if event == cv2.EVENT_LBUTTONDOWN:  # 左边鼠标点击
            f = open("1.txt", "w")
            f.write(str(x) + "," + str(y))
            f.close()

    def run(self):
        print("screenControlReceiver starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("screenControlReceiver connected...")
        while True:
            cv2.setMouseCallback("SERVER", self.mouse_click)
            try:
                f = open("1.txt")
                txt = f.read()
                f.close()
                reply = txt
                print(reply)
                self.sock.send(reply.encode('utf-8'))
                os.remove("1.txt")
            except:
                pass
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        print("screenControlReceiver connection lost...")


class screenControlReceiver(threading.Thread):
    def __init__(self, addr, version):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.ADDR = addr
        if version == 4:
            self.sock = socket(AF_INET, SOCK_STREAM)
        else:
            self.sock = socket(AF_INET6, SOCK_STREAM)
        self.controller = Controller()

    def __del__(self):
        self.sock.close()

    def run(self):
        print("screenControlReceiver starts...")
        while True:
            try:
                self.sock.connect(self.ADDR)
                break
            except:
                time.sleep(3)
                continue
        print("screenControlReceiver connected...")
        while True:
            msg = self.sock.recv(1024)
            msg = msg.decode('utf-8')
            print(msg)
            key = msg.split(",")
            xp = int(key[0])
            yp = int(key[1])
            self.controller.position = (xp, yp)
            self.controller.click(Button.left, 1)
        print("screenControlReceiver connection lost...")
