import json
import hashlib
from quiz_server import QuizRoom, Player
import os

QUIZ_FOLDER = 'quizzes'


def save_state(rooms, file_path="server_state.json"):
    room_data = {room.quiz_name: serialize_room(room) for room in rooms.values()}
    data_to_save = {
        'rooms': room_data,
    }
    json_data = json.dumps(data_to_save, indent=4)
    hash_digest = hashlib.sha256(json_data.encode()).hexdigest()

    with open(file_path, 'w') as f:
        json.dump({"data": data_to_save, "hash": hash_digest}, f, indent=4)


# Convert room states into a serializable format. This method should be called whenever the server want to save the room state.
def serialize_room(room):
    return {
        'quiz_name': room.quiz_name,
        'current_question': room.current_question,
        'users': [user.username for user in room.users],
        'scores': {user.username: user.score for user in room.users},
        'admin': room.admin.username if room.admin else None
    }


def load_state(file_path="server_state.json"):
    try:
        with open(file_path, 'r') as f:
            saved_data = json.load(f)

            if 'hash' not in saved_data or 'data' not in saved_data:
                print("Saved state is missing required keys.")
                return {}

            data_hash = saved_data['hash']
            data = saved_data['data']
            rooms_data = data.get('rooms', {})

            # Validate hash to check data integrity
            json_data = json.dumps(data, indent=4)
            if hashlib.sha256(json_data.encode()).hexdigest() != data_hash:
                print("Data integrity check failed.")
                return {}

            rooms = {}
            for quiz_name, room_data in rooms_data.items():
                room = QuizRoom(quiz_name, filepath=os.path.join(QUIZ_FOLDER, quiz_name + '.json'))
                room.current_question = room_data.get('current_question', 0)
                room.users = [Player(username) for username in room_data.get('users', [])]
                rooms[quiz_name] = room
                # Assign scores to users
                scores_data = room_data.get('scores', {})
                for user in room.users:
                    user.score = scores_data.get(user.username, 0)

                # Set the admin
                admin_username = room_data.get('admin')
                if admin_username:
                    room.admin = next((user for user in room.users if user.username == admin_username), None)

                rooms[quiz_name] = room
            print("Server state loaded successfully.")

            return rooms

    except json.JSONDecodeError:
        print("Error decoding JSON. File might be corrupted.")
        return {}