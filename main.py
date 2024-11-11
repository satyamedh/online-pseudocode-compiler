import threading

from flask import Flask, render_template
from flask_socketio import SocketIO
import subprocess
import os
import select
import secret_keys

app = Flask(__name__)
app.config['SECRET_KEY'] = secret_keys.SECRET_KEY
# socketio = SocketIO(app, logger=True, engineio_logger=True, async_mode='gevent')
socketio = SocketIO(app, async_mode='gevent')

processes = {}


@app.route('/')
def index():
    return render_template("index.html")

def ack():
    print('message was received!')

def read_pipe_without_blocking(pipe):
    poll_obj = select.poll()
    poll_obj.register(pipe, select.POLLIN)
    if poll_obj.poll(0):
        return pipe.readline().decode('utf-8')
    return ''

@socketio.on('run')
def run_code(data):
    global processes
    socketio.emit('output2', {'data': 'Running code...', 'id': data['id'], 'type': 'info'}, callback=ack)
    code = data['code']
    # store the code in a file in the /tmp directory
    filename = str(data['id'])

    # git clone the compiler - https://github.com/satyamedh/CIE-Pseudocode-compiler
    os.mkdir(f'/tmp/{filename}')
    prc = subprocess.Popen(['git', 'clone', 'https://github.com/satyamedh/CIE-Pseudocode-compiler', f'/tmp/{filename}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    prc.wait()
    socketio.emit('output2', {'data': prc.stdout.read().decode('utf-8'), 'id': data['id'], 'type': 'info'}, callback=ack)
    socketio.emit('output2', {'data': prc.stderr.read().decode('utf-8'), 'id': data['id'], 'type': 'error'}, callback=ack)

    # copy the code to the compiler directory
    with open(f'/tmp/{filename}/code.psc', 'w') as f:
        f.write(code)

    def compile_stuff():
        # run the program in a subprocess. Have live input and output using socketio
        # python3 main.py code.psc -rd
        # cwd = f'/tmp/{filename}'
        # 'firejail', '--noprofile',  f'--private=/tmp/{data["id"]}', '--net=none', '--whitelist=/usr/bin/python3', '--whitelist=/usr/bin/g++', '--rlimit-as=1024000', '--timeout=00:05:00',
        process = subprocess.Popen(['python3', 'main.py', 'code.psc', '-rd'], cwd=f'/tmp/{filename}', stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        processes[filename] = process
        while True:
            output = read_pipe_without_blocking(process.stdout)
            if output == '' and process.poll() is not None:
                socketio.emit('output2', {'data': 'Program exited...\n Session over', 'id': data['id'], 'type': 'info'}, callback=ack)
                # delete files
                os.remove(f'/tmp/{filename}/code.psc')
                break
            if output:
                socketio.emit('output2', {'data': output, 'id': data['id'], 'type': 'pgout'}, callback=ack)
            # If there is an error, send it to the client
            err = read_pipe_without_blocking(process.stderr)
            if err:
                socketio.emit('output2', {'data': err, 'id': data['id'], 'type': 'pgerr'}, callback=ack)
    socketio.emit('output2', {'data': 'Starting program...', 'id': data['id'], 'type': 'info'}, callback=ack)

    threading.Thread(target=compile_stuff).start()


@socketio.on('input')
def input_code(data):
    global processes
    process = processes[data['id']]
    process.stdin.write(data['to_send'].encode('utf-8') + b'\n')
    # echo the data
    socketio.emit('output2', {'data': data['to_send'], 'id': data['id'], 'type': 'echo'}, callback=ack)
    process.stdin.flush()



if __name__ == '__main__':
    # If the environment variable DBG is set, use port 6969
    port = 6969 if 'DBG' in os.environ else 5000
    socketio.run(app, host='0.0.0.0', port=port)
