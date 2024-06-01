import os
import json
import socket
import threading
import select
import time
import Secure
import hashlib
import db_mgmt

QUIZ_FOLDER = 'quizzes'
USERS_FILE = 'users.json'


class Player:
    def __init__(self, username, socket=None):
        self.username = username
        self.is_admin = False
        self.has_answered = False
        self.score = 0
        self.socket = socket

    def set_admin(self, is_admin):
        self.is_admin = is_admin

    def update_score(self, score):
        self.score += score


class QuizRoom:
    def __init__(self, quiz_name, filepath):
        self.quiz_name = quiz_name
        self.quiz_path = filepath
        self.quiz_file = None
        self.users = []
        self.current_question = 0
        self.read_quiz_file()
        self.status = 'new'  # new, joinable or in_progress
        self.admin = None

    def read_quiz_file(self):
        # Opening JSON file
        f = open(self.quiz_path)
        # returns JSON object as a dictionary
        self.quiz_data = json.load(f)
        f.close()

    def get_admin_username(self):
        if self.admin:
            return self.admin.username
        return None

    def reset_room(self):
        self.quiz_file = None
        self.users.clear()
        self.current_question = 0
        self.read_quiz_file()
        self.status = 'new'  # new, joinable or in_progress
        self.admin = None


def handle_client(client_socket, address, rooms):
    print(f"Notice: Connection established with {address}")
    while True:
        # Wait for the client to send data or for the timeout to expire
        ready = select.select([client_socket], [], [], 300)  # 300 seconds = 5 minutes

        if ready:  # If the client sent data
            #message = json.loads(Secure.decrypt(client_socket.recv(1024)))
            #Secure.send_ack(client_socket)
            message = Secure.server_receive_data(client_socket)[1]
            if message:
                print(f"Notice: Message received from {address}, Data: {message}")
                COMMANDS[message.pop('Command')](client_socket, message, rooms)
        else:
            # If no data is received within 5 minutes, close the connection
            print("Closing connection due to inactivity.")
            client_socket.close()
            break

    client_socket.close()


class QuizServer:
    def __init__(self, host='127.0.0.1', port=65431):
        """
        Initialize the QuizServer with host, port, and quiz folder.
        Load the quizzes from the specified folder on initialization.

        :param host: The IP address for the server.
        :param port: The port number for the server.
        :param quiz_folder: The directory containing quiz JSON files.
        """
        self.host = host
        self.port = port
        self.clients = []  # List to track connected clients - thread for each client
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))  # bind the socket to the server's IP and PORT
        self.rooms = db_mgmt.load_state()  # dictionary of quiz_name:QuizRoom type - an object for each quiz in the DB
        #self.load_quizzes()  # Load quizzes on server initialization


    def load_quizzes(self):
        """
        Load quizzes from JSON files in the specified directory.
        Each quiz file should be a JSON array of questions and answers.
        """
        for filename in os.listdir(QUIZ_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(QUIZ_FOLDER, filename)
                with open(filepath, 'r') as f:
                    quiz_name = filename[:-5]  # Extract quiz name from filename
                    self.rooms[quiz_name] = QuizRoom(quiz_name, filepath)
        db_mgmt.save_state(self.rooms)

    def start(self):
        """
        Start the server to listen for incoming connections.
        For each new connection, create a new thread to handle the client.
        """
        self.server_socket.listen()
        print(f"Notice: Server listening on {self.host}:{self.port}")
        while True:
            client_socket, address = self.server_socket.accept()
            self.clients.append(client_socket)
            thread = threading.Thread(target=handle_client, args=(client_socket, address, self.rooms))
            thread.start()

def get_quiz_list(client_socket, message, rooms):
    quiz_list = [
        {"name": room.quiz_name, "status": room.status, "participants": [user.username for user in room.users],
         "admin": room.get_admin_username()}
        for room in rooms.values()
    ]
    Secure.server_send_data(client_socket, (json.dumps(quiz_list)))
    print('sent')


def retrieve_user_state(username, rooms):
    # Placeholder function to retrieve a user's state
    # You need to implement the logic to find the user's current room, score, etc.
    for room in rooms.values():
        for user in room.users:
            if user.username == username:
                return {
                    'current_quiz': room.quiz_name,
                    'score': user.score,
                    # Add more state information as needed
                }
    return {}


def get_all_users(rooms):
    # Utility function to get all users from all rooms
    users = []
    for room in rooms.values():
        users.extend([user.username for user in room.users])
    return users


def handle_reconnection(client_socket, message, rooms):
    username = message.get('username')
    # Find the user and the room they belong to
    user_found = False
    user_room = None
    user_instance = None

    for room in rooms.values():
        print(room.users)
        for user in room.users:
            if user.username == username:
                user_found = True
                user_room = room
                user_instance = user
                break
        if user_found:
            break

    if user_found and user_instance:
        # Update the user's socket
        user_instance.socket = client_socket
        print(f"User {username} reconnected in room {user_room.quiz_name}.")

        # Retrieve and send the user's current state
        user_state = {
            'current_quiz': user_room.quiz_name,
            'score': user_instance.score,
            'current_question': user_room.current_question,
            'is_admin': user_instance.is_admin,
        }
        Secure.server_send_data(client_socket, json.dumps({'status': 'reconnected', **user_state}))
    else:
        print(f"Reconnection failed for user {username}.")
        Secure.server_send_data(client_socket, json.dumps({'status': 'reconnect_failed'}))


def find_user_room_and_instance(username, rooms):
    for room_name, room in rooms.items():
        for user in room.users:
            if user.username == username:
                return room, user
    return None, None


def load_user_data():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_user_data(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(client_socket, message, rooms):
    users = load_user_data()
    username = message['username']
    password = message['password']
    if username in users:
        Secure.server_send_data(client_socket, json.dumps({'approved': False}))
    else:
        users[username] = hash_password(password)
        save_user_data(users)
        Secure.server_send_data(client_socket, json.dumps({'approved': True}))


def authenticate_user(client_socket, message, rooms):
    users = load_user_data()
    username = message['username']
    password = message['password']
    hashed_password = hash_password(password)
    Secure.server_send_data(client_socket, json.dumps({'approved': users.get(username) == hashed_password}))


def verify_admin_credentials(client_socket, credentials):
    user = credentials['username']
    if credentials['admin_password']:
        print(f'Notice: User {user}, is now an admin!')
        Secure.server_send_data(client_socket, json.dumps({'approved': True}))


def join_quiz(client_socket, data, rooms):
    player = Player(data['username'], socket=client_socket)
    quiz_name = data['quiz']
    # Check if the room is empty
    if not rooms[quiz_name].users:
        rooms[quiz_name].admin = player
        player.is_admin = True
        rooms[quiz_name].users.append(player)
        print(f"Notice: {player.username} is now the room admin in room {quiz_name}")
        print(f"Notice: room {quiz_name} status changed to joinable")
        rooms[quiz_name].status = 'joinable'
        # Response to the client after new admin has ben joined
        Secure.server_send_data(client_socket, json.dumps({'status': 'joined', 'is_admin': True}))
        update_room_users(rooms, quiz_name, {"type": "user_joined", "username": player.username})
        # Save state after updating the room
        db_mgmt.save_state(rooms)
    else:  # Check if the quiz is joinable and the username is unique
        if rooms[quiz_name].status != 'in_progress':
            if not any(user.username == player.username for user in rooms[quiz_name].users):
                print(f" {player.username} has joined to {quiz_name} quiz")
                rooms[quiz_name].users.append(player)
                Secure.server_send_data(client_socket, json.dumps({'status': 'joined', 'is_admin': False}))
                update_room_users(rooms, quiz_name, {"type": "user_joined", "username": player.username})
                # Save state after updating the room
                db_mgmt.save_state(rooms)
            else:  # The player need to choose a new username
                Secure.server_send_data(client_socket, json.dumps({'status': 'choose_different_username'}))


def start_quiz(client_socket, data, rooms):
    quiz_name = data['current_quiz']
    rooms[quiz_name].status = 'in_progress'
    print(f"{quiz_name} is starting")
    print(f"Notice: room {quiz_name} status changed to in_progress")
    userList = [user.username for user in rooms[quiz_name].users]
    for player in rooms[quiz_name].users:
        # Assuming each user has an associated socket stored as user.socket
        Secure.server_send_data(player.socket, json.dumps({'participants': userList, 'game_started': True}))


def update_room_users(rooms, quiz_name, message):
    # Iterate over all users in the specified room
    userList = [user.username for user in rooms[quiz_name].users]
    print(userList)
    # Wait for the last player to enter the room before send everyone (and him) the user list
    time.sleep(0.01)
    for player in rooms[quiz_name].users:
        # Assuming each user has an associated socket stored as user.socket
        Secure.server_send_data(player.socket, json.dumps({'participants': userList, 'game_started': False}))


def get_question(client_socket, data, rooms):
    quiz_name = data['quiz']
    quiz_room = rooms[quiz_name]
    if quiz_room.current_question < len(quiz_room.quiz_data):
        question = quiz_room.quiz_data[quiz_room.current_question]['question']
        answers = quiz_room.quiz_data[quiz_room.current_question]['answers']
        print(f"Notice: Room {quiz_name} is currently in question {quiz_room.current_question}, {question}")
        for player in quiz_room.users:
            # Assuming each user has an associated socket stored as user.socket
            player.has_answered = False
            Secure.server_send_data(player.socket, json.dumps({'type': 'question', 'question': question, 'answers': answers}))
            time.sleep(0.1)
    else:
        end_game_logic(quiz_room)
        db_mgmt.save_state(rooms)


def get_player_answer(client_socket, data, rooms):
    print(f"Notice: {data['username']} answer for quiz {data['quiz_name']} is {data['answer']}, answer_time = {data['answer_time']}")
    quiz_room = rooms[data['quiz_name']]
    print(quiz_room.users)
    player = next((user for user in quiz_room.users if user.username == data['username']), None)
    if data['answer'] is not None:

        player.has_answered = True
        check_answer(rooms, player, data['answer'], data['quiz_name'], data['answer_time'])
    else:
        print(f"Notice: question timeout for {data['username']}")
        player.has_answered = True
    # After all answers are collected or time is up, calculate top 3
    if all_answers_collected_or_time_up(quiz_room):
        # Save state after updating the room
        db_mgmt.save_state(rooms)
        broadcast_scores(quiz_room)


def check_answer(rooms, player, answer, quiz_name, answer_time):
    correct_answer = rooms[quiz_name].quiz_data[rooms[quiz_name].current_question]['correct_answer']
    print(f"Notice: The correct answer is: {correct_answer}")
    if answer == correct_answer:
        # Calculate score based on answer time
        if answer_time < 10:
            score = (10 - answer_time) * 100
        else:
            score = 0
    else:
        score = 0
    player.update_score(score)
    print(f"Notice: {player.username} got {score} points, total is now {player.score}")


def all_answers_collected_or_time_up(quiz_room):
    # Check if all players have answered or if time is up
    if all(player.has_answered for player in quiz_room.users):
        print(f"Notice: all players answered")
        quiz_room.current_question += 1
        #broadcast_scores(quiz_room, update_message)
        return True
    return False


def get_leaderboard(quiz_room):
    return sorted(quiz_room.users, key=lambda user: user.score, reverse=True)[:3]


def broadcast_scores(quiz_room):
    # Calculate top 3 scores and prepare the score update message
    top_players = get_leaderboard(quiz_room)
    score_update_message = {
        'type': 'score_update',
        'top_players': [(p.username, p.score) for p in top_players]
    }
    # Send score update to all users in the room
    for player in quiz_room.users:
        score_update_message.update({'Your Score': player.score})
        Secure.server_send_data(player.socket, json.dumps(score_update_message))
        time.sleep(0.1)


# Server-side pseudo-code
def end_quiz(quiz_room):
    leaderboard = [(p.username, p.score) for p in get_leaderboard(quiz_room)]
    print(f"Notice: leaderboard is: {leaderboard}")
    end_message = json.dumps({'type': 'end', 'leaderboard': leaderboard})
    for player in quiz_room.users:
        Secure.server_send_data(player.socket, end_message)
        time.sleep(0.1)


# In the server logic where the game ends
def end_game_logic(quiz_room):
    # Wait for all player (network and process delay)
    # send end game message, etc.
    print(f"Notice: Reset room - {quiz_room.quiz_name}")
    end_quiz(quiz_room)
    time.sleep(1)
    quiz_room.reset_room()
    # if you're using threads, make sure the thread that handles the game loop exits here


COMMANDS = {
    'Login': authenticate_user,
    'Register': register_user,
    'verify admin credentials': verify_admin_credentials,
    'get_quiz_list': get_quiz_list,
    'Join Quiz': join_quiz,
    'Start Quiz': start_quiz,
    'get_question': get_question,
    'quiz_answer': get_player_answer,
    'Reconnect': handle_reconnection
}

if __name__ == "__main__":
    server = QuizServer()
    server.start()
