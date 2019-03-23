#!/usr/bin/env python

from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit
from multiprocessing import Process, Array
import numpy as np
import ctypes as c 
import sys, os, timeit, time, socket, struct, fcntl
import RPi.GPIO as IO

# IO.setwarnings(False)  # do not show any warnings
IO.setmode(IO.BOARD)  

col_select = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20]
row_select = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x100, 0x200]
row_pins = [40, 37, 38, 35, 36, 33, 32, 31, 29, 23]
col_pins = [22, 21, 19, 18, 15, 16]
for pin in row_pins+col_pins:
    IO.setup(pin, IO.OUT)

all_ones = 10*[0b111111]
numbers = [[0b001100,0b010010,0b100001,0b100001,0b100001,0b100001,0b100001,0b100001,0b010010,0b001100], # 0
           [0b000100,0b000100,0b000100,0b000100,0b000100,0b000100,0b000100,0b000100,0b000100,0b000100], # 1
           [0b011110,0b100001,0b000001,0b000001,0b000010,0b001100,0b010000,0b100000,0b100000,0b111111], # 2
           [0b111111,0b000001,0b000010,0b000100,0b001110,0b000001,0b000001,0b000001,0b100001,0b011110], # 3
           [0b000001,0b000011,0b000101,0b001001,0b010001,0b100001,0b111111,0b000001,0b000001,0b000001], # 4
           [0b111111,0b100000,0b100000,0b010000,0b001100,0b000010,0b000001,0b000001,0b100001,0b011110], # 5
           [0b000010,0b000100,0b001000,0b010000,0b111110,0b100001,0b100001,0b100001,0b100001,0b011110], # 6
           [0b111111,0b000001,0b000010,0b000010,0b000010,0b000100,0b000100,0b000100,0b001000,0b001000], # 7
           [0b011110,0b100001,0b100001,0b010010,0b001100,0b010010,0b100001,0b100001,0b100001,0b011110], # 8
           [0b011110,0b100001,0b100001,0b100001,0b100001,0b011111,0b000010,0b000100,0b001000,0b010000]] # 9

dot = [0,0,0,0,0,0,0,0,0b001100,0b001100]

def reverseBits(num): 
     reverse = bin(int(num))[-1:1:-1]
     reverse = reverse + (6 - len(reverse))*'0'
     return int(reverse, 2) 

for number in numbers:
    for i in xrange(len(number)):
        number[i] = reverseBits(number[i])

def reset_rows():
    for pin in row_pins:
        IO.output(pin, 0)

def set_row(val):
    if (val == 0x01): IO.output(row_pins[9], 0); IO.output(row_pins[0], 1);
    elif (val == 0x02): IO.output(row_pins[0], 0); IO.output(row_pins[1], 1);
    elif (val == 0x04): IO.output(row_pins[1], 0); IO.output(row_pins[2], 1);
    elif (val == 0x08): IO.output(row_pins[2], 0); IO.output(row_pins[3], 1);
    elif (val == 0x10): IO.output(row_pins[3], 0); IO.output(row_pins[4], 1);
    elif (val == 0x20): IO.output(row_pins[4], 0); IO.output(row_pins[5], 1);
    elif (val == 0x40): IO.output(row_pins[5], 0); IO.output(row_pins[6], 1);
    elif (val == 0x80): IO.output(row_pins[6], 0); IO.output(row_pins[7], 1);
    elif (val == 0x100): IO.output(row_pins[7], 0); IO.output(row_pins[8], 1);
    else: IO.output(row_pins[8], 0); IO.output(row_pins[9], 1);

def set_cols(val):
    val = int(val)
    if (val&0x01 == 0x01): IO.output(col_pins[0], 0)
    else: IO.output(col_pins[0], 1)
    if (val&0x02 == 0x02): IO.output(col_pins[1], 0)
    else: IO.output(col_pins[1], 1)
    if (val&0x04 == 0x04): IO.output(col_pins[2], 0)
    else: IO.output(col_pins[2], 1)
    if (val&0x08 == 0x08): IO.output(col_pins[3], 0)
    else: IO.output(col_pins[3], 1)
    if (val&0x10 == 0x10): IO.output(col_pins[4], 0)
    else: IO.output(col_pins[4], 1)
    if (val&0x20 == 0x20): IO.output(col_pins[5], 0)
    else: IO.output(col_pins[5], 1)

def show(list_of_vals, cycles=5, t_on=0.0005, t_off=0):
    for i in xrange(cycles):
        for y in xrange(len(list_of_vals)):
            set_cols(list_of_vals[y])
            set_row(row_select[y])
            time.sleep(t_on)
            reset_rows()
            time.sleep(t_off)

def show_pulse(list_of_vals):
    for j in range(20)+range(19,-1,-1):
        show(list_of_vals, cycles=3, t_on=0.002-j*0.0001, t_off=j*0.0001)

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None # gevent only works actually

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None

n, m = 2, 10
mp_arr = Array(c.c_double, n*m)
arr = np.frombuffer(mp_arr.get_obj())
main_data = arr.reshape((n,m))


def data_logger(main_data):
    while True:
        # print main_data[1,0], main_data[1,1]
        # socketio.sleep(1)
        # show_pulse(main_data[0,:])
        show(main_data[0,:], t_on=main_data[1,0], t_off=main_data[1,1])
    
def background_thread():
    global main_data
    count = 0
    main_data[1,0] = 0.002
    main_data[1,1] = 0.000
    while True:
        # show(main_data)
        socketio.sleep(10)
        count += 1
		# socketio.emit('my_response', {'data': main_data.tolist(), 'count': count}, namespace='/test')

@app.route('/')
def index():
	return render_template('index.html', async_mode=socketio.async_mode)

@socketio.on('my_event', namespace='/test')
def test_message(message):
    global main_data
    # print message['data']
    if len(message['data']) == 10:
        main_data[0,:] = message['data']
        for j in xrange(main_data.shape[1]):
            main_data[0,j] = reverseBits(main_data[0,j])
    else: 
        main_data[1,0] = 0.002 - int(message['data'][0])*0.0001
        main_data[1,1] = int(message['data'][0])*0.0001

    session['receive_count'] = session.get('receive_count', 0) + 1
	# emit('my_response',{'data': message['data'], 'count': session['receive_count']})

@socketio.on('connect', namespace='/test')
def test_connect():
    global thread
    if thread is None:
        thread = socketio.start_background_task(target=background_thread)
    emit('my_response', {'data': 'Connected!', 'count': 0})

@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(s.fileno(),0x8915,struct.pack('256s', ifname[:15]))[20:24])

if __name__ == '__main__':
    local_ip = get_ip_address('wlan0')
    process0 = Process( target=data_logger, args=(main_data,) )
    process0.start()
    # process0.join()

    socketio.run(app, host=local_ip, port=8888) #, debug=True)
