from queue import SimpleQueue

from PyQt6.QtCore import pyqtSignal, pyqtSlot, QObject, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow
import socket

from reg_gui import Ui_MainRegistration
from threading import Thread
import pickle
import struct
from room_gui import Ui_MainRoom
from game_gui import Ui_MainGame
from ban_gui import Ui_MainBan


class Communication(QObject):
    message_received = pyqtSignal(str)
    start_signal = pyqtSignal()
    end_signal = pyqtSignal()


class Registration(QMainWindow, Ui_MainRegistration):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle('Registration')
        self.setWindowIcon(QIcon('reg_icon.jpg'))
        self.comm = Communication()
        self.sock = Socket('127.0.0.1', 8080, self.comm)
        self.input_name.setPlaceholderText('Enter your name...')

        self.send_btn.setEnabled(False)
        self.check_btn.clicked.connect(self.check)
        self.send_btn.clicked.connect(self.send)

        self.show()

    @pyqtSlot()
    def check(self):
        if self.input_name.text() == '':
            self.check_label.setText('Please enter your name!')
        elif self.input_name.text() not in self.sock.names:
            self.check_label.setText('Available name!')
            self.send_btn.setEnabled(True)
        else:
            self.check_label.setText('Wrong name!')

    @pyqtSlot()
    def send(self):
        name = self.input_name.text()
        self.input_name.clear()
        self.check_label.setText(' ')
        self.sock.queue.put({'type': 'name', 'body': name})
        self.hide()

        self.room = Room(self, name, self.comm, self.sock)


class Room(QMainWindow, Ui_MainRoom):
    def __init__(self, main_window, name, comm, sock):
        super().__init__()
        self.setupUi(self)
        self.main_window = main_window
        self.name = name
        self.comm = comm
        self.sock = sock

        self.setWindowTitle(f'Welcome, {self.name}!')
        self.setWindowIcon(QIcon('room_icon.jpg'))
        self.show()
        self.rooms = ['Word Wanderers', 'City Slickers', 'Urban Odyssey',
                                  'Alphabet Avenue', 'Metropolis Minds']
        self.combo_room.addItems(self.rooms)

        self.join_btn.setEnabled(False)

        self.pushButton.clicked.connect(self.check_room)
        self.join_btn.clicked.connect(self.join_game)

    @pyqtSlot()
    def check_room(self):
        room = self.combo_room.currentText()
        if room not in self.sock.restricted_rooms and self.sock.lens[self.rooms.index(room)] < 2:
            self.label.setText('Available room!')
            self.join_btn.setEnabled(True)
        else:
            self.label.setText('You are restricted to ' + room)

    @pyqtSlot()
    def join_game(self):
        room = self.combo_room.currentText()

        self.sock.queue.put({'type': 'room', 'body': room})
        self.label.setText(' ')
        self.hide()

        self.game = WordsGame(self.main_window, self.name, self.comm, self.sock, room)


class WordsGame(QMainWindow, Ui_MainGame):
    def __init__(self, main_window, name, comm, sock, room):
        super().__init__()
        self.setupUi(self)
        self.main_window = main_window
        self.name = name
        self.comm = comm
        self.sock = sock
        self.room = room

        self.setWindowTitle(room)
        self.setWindowIcon(QIcon('game_icon.jpg'))
        self.chat_history = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.time_out)
        self.timer.setSingleShot(True)

        self.show()

        self.send_btn.setEnabled(False)
        self.ban_btn.setEnabled(False)

        self.exit_btn.clicked.connect(self.exit)
        self.room_btn.clicked.connect(self.change_room)
        self.ban_btn.clicked.connect(self.ban)
        self.send_btn.clicked.connect(self.send)

        self.comm.message_received.connect(self.chat_update)
        self.comm.start_signal.connect(self.start)
        self.comm.end_signal.connect(self.end_game)

    @pyqtSlot()
    def exit(self):
        self.close()
        self.sock.queue.put({'type': 'exit', 'body': ' '})
        self.sock.sock.close()

    @pyqtSlot()
    def change_room(self):
        self.sock.ready = False
        self.close()
        self.sock.queue.put({'type': 'change_room', 'body': ' '})
        self.comm.message_received.disconnect()
        self.comm.start_signal.disconnect()
        self.comm.end_signal.disconnect()
        self.main_window.show()

    @pyqtSlot()
    def ban(self):
        self.ban = BanWindow(self.main_window, self.name, self.comm, self.sock)

    @pyqtSlot()
    def send(self):
        text = self.input_chat.text()
        self.sock.queue.put({'type': 'chat', 'body': text})
        self.input_chat.clear()
        self.send_btn.setEnabled(False)

        self.timer.stop()

    @pyqtSlot()
    def time_out(self):
        self.sock.queue.put({'type': 'time_out', 'body': self.name})

    @pyqtSlot(str)
    def chat_update(self, txt):
        self.ban_btn.setEnabled(True)
        self.chat_history.append(txt)
        self.chat_wind.setText('\n'.join(self.chat_history))
        print('Чат обновлен')

        if not self.chat_history[-1].startswith('Your city') and self.chat_history[-1] != 'Game started!' and self.chat_history[-1] != 'You win!!':
            if self.chat_history[-1] != 'You were banned' and not self.chat_history[-1].startswith('Game over'):
                if not self.chat_history[-1].endswith('left the game.') and not self.chat_history[-1].startswith('Timed out!'):
                    self.chat_history.append('Your turn. Enter your city:')
                    self.chat_wind.setText('\n'.join(self.chat_history))
                    self.send_btn.setEnabled(True)

                    self.timer.start(40000)

    @pyqtSlot()
    def start(self):
        self.chat_history.append('Your turn. Enter your city:')
        self.chat_wind.setText('\n'.join(self.chat_history))
        self.send_btn.setEnabled(True)

        self.timer.start(40000)

    @pyqtSlot()
    def end_game(self):
        self.timer.stop()
        self.send_btn.setEnabled(False)
        self.chat_history.append("Game over! Return to room selection after 20 seconds.")
        self.chat_wind.setText('\n'.join(self.chat_history))

        self.timer2 = QTimer(self)
        self.timer2.timeout.connect(self.change_room)
        self.timer2.setSingleShot(True)
        self.timer2.start(20000)


class BanWindow(QMainWindow, Ui_MainBan):
    def __init__(self, main_window, name, comm, sock):
        super().__init__()
        self.setupUi(self)
        self.main_window = main_window
        self.name = name
        self.comm = comm
        self.sock = sock
        self.setWindowTitle('Ban Window')
        self.setWindowIcon(QIcon('ban_icon.jpg'))
        self.ban_user_btn.setEnabled(False)
        self.pushButton.clicked.connect(self.check_name)
        self.ban_user_btn.clicked.connect(self.ban)
        self.show()

    @pyqtSlot()
    def check_name(self):
        if self.name_input.text() in self.sock.room_clients:
            print(self.name_input.text())
            self.label.setText('This player will be banned!')
            self.ban_user_btn.setEnabled(True)
        else:
            self.label.setText('Wrong username!')

    @pyqtSlot()
    def ban(self):
        username = self.name_input.text()
        self.name_input.clear()
        self.sock.queue.put({'type': 'ban', 'body': username})
        self.hide()


class Socket:
    def __init__(self, host, port, communication: Communication):
        self.queue = SimpleQueue()
        self.communication = communication
        self.names = []
        self.ready = False
        self.restricted_rooms = []
        self.lens = []
        self.room_clients = []

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        Thread(target=self.send_pickle_thread, daemon=True).start()
        Thread(target=self.rec_pickle_thread, daemon=True).start()

    def send_pickle_thread(self):
        while True:
            data = self.queue.get()
            serialized_data = pickle.dumps(data)
            data_length = len(serialized_data)
            print(f"Send data: {data}, length: {data_length}")
            self.sock.sendall(struct.pack("!I", data_length))
            self.sock.sendall(serialized_data)

    def rec_pickle(self):
        length_bytes = self.sock.recv(4)
        if not length_bytes:
            print("Error: couldn't get the length of the data.")
            return None
        data_length = struct.unpack("!I", length_bytes)[0]
        print(f"We are expecting data of length: {data_length}")

        data = b""
        while len(data) < data_length:
            packet = self.sock.recv(data_length - len(data))
            if not packet:
                print("Error: the connection is terminated.")
                return None
            data += packet

        deserialized_data = pickle.loads(data)
        print(f"Data received: {deserialized_data}")
        return deserialized_data

    def rec_pickle_thread(self):
        while True:
            try:
                data = self.rec_pickle()
                if data is None:
                    continue

                type = data['type']
                body = data['body']

                if type == 'chat':
                    self.communication.message_received.emit(body)
                elif type == 'ban':
                    self.restricted_rooms.append(body)
                elif type == 'names':
                    self.names = body
                elif type == 'start_game':
                    self.ready = True
                    self.communication.start_signal.emit()
                elif type == 'end_game':
                    self.ready = False
                    self.communication.end_signal.emit()
                elif type == 'len_clients':
                    self.lens = body
                elif type == 'clients':
                    self.room_clients = body
                    print(self.room_clients)
                else:
                    continue

            except Exception as e:
                print(f"Error in the data receipt flow: {e}")
                break


app = QApplication([])
window = Registration()
app.exec()