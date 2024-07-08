import threading

from flask import Flask, render_template
from flask_socketio import SocketIO
import subprocess
import os
import select

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, logger=True, engineio_logger=True, async_mode='gevent')

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
    os.mkdir(f'/tmp/{filename}')
    with open(f'/tmp/{filename}/code.psc', 'w') as f:
        f.write(code)

    # copy dockerfile to folder
    # os.system(f'cp docker/Dockerfile tmp/{filename}/')
    prc = subprocess.Popen(['cp', 'docker/Dockerfile', f'/tmp/{filename}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    prc.wait()
    socketio.emit('output2', {'data': prc.stdout.read().decode('utf-8'), 'id': data['id'], 'type': 'info'}, callback=ack)
    socketio.emit('output2', {'data': prc.stderr.read().decode('utf-8'), 'id': data['id'], 'type': 'error'}, callback=ack)

    def docker_stuff():
        # build the docker image
        # os.system(f'docker build -t {filename} /tmp/{filename}')
        prc = subprocess.Popen(['docker', 'build', '-t', filename, f'/tmp/{filename}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        prc.wait()
        socketio.emit('output2', {'data': prc.stdout.read().decode('utf-8'), 'id': data['id'], 'type': 'info'}, callback=ack)
        socketio.emit('output2', {'data': prc.stderr.read().decode('utf-8'), 'id': data['id'], 'type': 'error'}, callback=ack)

        socketio.emit('output2', {'data': '\n\nDocker build done...', 'id': data['id'], 'type': 'info'}, callback=ack)
        # run the docker image in a subprocess. Have live input and output using socketio
        # f'docker run --rm -i -e PYTHONUNBUFFERED=1 {filename}'
        process = subprocess.Popen(['docker', 'run', '--rm', '-i', '-e', 'PYTHONUNBUFFERED=1', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        processes[filename] = process
        while True:
            output = read_pipe_without_blocking(process.stdout)
            if output == '' and process.poll() is not None:
                socketio.emit('output2', {'data': 'Docker exited...\n Session over', 'id': data['id'], 'type': 'info'}, callback=ack)
                break
            if output:
                socketio.emit('output2', {'data': output, 'id': data['id'], 'type': 'pgout'}, callback=ack)
            # If there is an error, send it to the client
            err = read_pipe_without_blocking(process.stderr)
            if err:
                socketio.emit('output2', {'data': err, 'id': data['id'], 'type': 'pgerr'}, callback=ack)
    socketio.emit('output2', {'data': 'Starting Docker...', 'id': data['id'], 'type': 'info'}, callback=ack)

    threading.Thread(target=docker_stuff).start()


@socketio.on('input')
def input_code(data):
    global processes
    process = processes[data['id']]
    process.stdin.write(data['to_send'].encode('utf-8') + b'\n')
    # echo the data
    socketio.emit('output2', {'data': data['to_send'], 'id': data['id'], 'type': 'echo'}, callback=ack)
    process.stdin.flush()



if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
