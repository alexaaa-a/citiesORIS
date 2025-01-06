import socket
import threading
import pickle
import struct


class Room:
    def __init__(self, name):
        self.name = name
        self.clients = {}
        self.used_cities = []
        self.turn = 0
        self.is_active = False

    def add_client(self, client, player_name):
        self.clients[client] = player_name

    def remove_client(self, client, reason=None):
        if client not in self.clients:
            return
        name = client.name
        if client in self.clients:
            if reason == 'ban':
                client.send_pickle({'type': 'chat', 'body': 'You were banned'})
                client.send_pickle({'type': 'end_game', 'body': "Game over!"})
                del self.clients[client]
            elif reason == 'time_out':
                client.send_pickle({'type': 'chat', 'body': 'Timed out! You lose!'})
                client.send_pickle({'type': 'end_game', 'body': "Game over!"})
                del self.clients[client]
                list(self.clients.keys())[0].send_pickle({'type': 'chat', 'body': "You win!!"})
            self.broadcast({'type': 'chat', 'body': f"{name} left the game."})
            if len(self.clients) < 2:
                self.end_game()

    def broadcast(self, message, exclude_client=None):
        for client in self.clients:
            if client != exclude_client:
                try:
                    client.send_pickle(message)
                except Exception as e:
                    print(f"Ошибка отправки сообщения: {e}")

    def start_game(self):
        if self.is_active:
            print("Игра уже началась!")
            return
        self.is_active = True
        self.broadcast({'type': 'chat', 'body': 'Game started!'})
        list(self.clients.keys())[0].send_pickle({'type': 'start_game', 'body': ' '})

    def end_game(self):
        self.is_active = False
        self.used_cities = []
        self.turn = 0
        self.broadcast({'type': 'end_game', 'body': "Game over!"})
        self.clients = {}


class ClientThread(threading.Thread):
    def __init__(self, sock, addr, rooms):
        super().__init__()
        self.sock = sock
        self.addr = addr
        self.rooms = rooms
        self.room = None
        self.name = ''

        self.start()

    def run(self):
        while True:
            data = self.recv()
            print('Данные получены')

            if not data:
                break

            match data['type']:
                case 'name':
                    self.name = data['body']
                    names[self] = self.name
                    print('Имя получено')

                    rooms_clients = []
                    for i in self.rooms:
                        rooms_clients.append(len(i.clients))
                    self.send_pickle({'type': 'len_clients', 'body': rooms_clients})
                case 'room':
                    print(f'Комната получена: {data['body']}')
                    self.join_room(data['body'])

                    if len(self.room.clients) > 1 and not self.room.is_active:
                        self.room.start_game()
                        self.room.broadcast({'type': 'clients', 'body': list(self.room.clients.values())})
                        print('Начинаем игру')
                case 'chat':
                    city = data['body'].strip().lower()
                    if self.check_city(city):
                        self.room.used_cities.append(city)
                        self.send_pickle({'type': 'chat', 'body': f'Your city: {city}.'})
                        self.room.broadcast({'type': 'chat', 'body': f"{self.name}'s city: {city}."}, self)
                case 'ban':
                    username = data['body']
                    client = self.get_client_by_name(username)
                    self.room.remove_client(client, 'ban')
                    client.send_pickle({'type': 'ban', 'body': self.room.name})
                    print(self.get_client_by_name(username))
                case 'change_room':
                    self.disconnect()
                case 'exit':
                    self.room.remove_client(self)
                case 'time_out':
                    self.room.remove_client(self, 'time_out')


    def join_room(self, room_name):
        for room in self.rooms:
            if room.name == room_name:
                self.room = room
                room.add_client(self, self.name)
                print(f"{self.name} joined the room {room.name}.")
                return

        self.send_pickle({'type': 'chat', 'body': "The room was not found!"})

    def disconnect(self):
        print(f"Client {self.addr} has disconnected.")
        if self.room:
            self.room.remove_client(self)

    def send_pickle(self, data):
        try:
            serialized_data = pickle.dumps(data)
            self.sock.sendall(struct.pack("!I", len(serialized_data)))
            self.sock.sendall(serialized_data)
        except Exception as e:
            print(f"Error sending data to the client {self.addr}: {e}")
            self.disconnect()

    def recv(self):
        try:
            length_bytes = self.sock.recv(4)
            if not length_bytes:
                return None
            data_length = struct.unpack("!I", length_bytes)[0]
            data = b""
            while len(data) < data_length:
                packet = self.sock.recv(data_length - len(data))
                if not packet:
                    return None
                data += packet
            return pickle.loads(data)
        except Exception as e:
            print(f"Error receiving data from the client {self.addr}: {e}")
            return None

    def get_client_by_name(self, name):
        for client in list(self.room.clients.keys()):
            if self.room.clients[client] == name:
                return client
        return None

    def check_city(self, city):
        if not city:
            self.send_pickle({"type": "chat", "body": "The name of the city cannot be empty."})
            return False

        elif city in self.room.used_cities:
            self.send_pickle({"type": "chat", "body": "This city has already been named."})
            return False

        elif self.room.used_cities and self.room.used_cities[-1][-1] != city[0]:
            self.send_pickle({"type": "chat",
                                        "body": f"The city must begin with the letter '{self.room.used_cities[-1][-1]}'. Try again."})
            return False

        return True


names = {}


class Server:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.listen()
        self.rooms = [Room('Word Wanderers'), Room('City Slickers'), Room('Urban Odyssey'),
                                  Room('Alphabet Avenue'), Room('Metropolis Minds')]

    def serve_forever(self):
        while True:
            client_sock, client_addr = self.sock.accept()
            print(f"The client has connected: {client_addr}")
            client_thread = ClientThread(client_sock, client_addr, self.rooms)
            client_thread.send_pickle({'type': 'names', 'body': list(names.values())})


if __name__ == "__main__":
    server = Server("127.0.0.1", 8080)
    server.serve_forever()
