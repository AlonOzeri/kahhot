import socket
import tkinter as tk
import json
from tkinter import simpledialog
import threading
import time
import Secure

HOST = '127.0.0.1'  # Define the server's IP address.
PORT = 65431  # Define the port on which the server is listening.
BUTTON_COLOR = {'new': "green", 'joinable': "light blue", 'in_progress': "light coral"}
CHOSEN_ANSWER_SIZE = 45

#bla bla
class QuizClient:
    def __init__(self, master):
        """
        Initialize the QuizClient class, establish a connection to the server,
        and trigger user authentication.
        """
        self.client_answered = False
        self.username = None
        self.timer_event_id = None
        self.init_time_left = 10
        self.time_left = self.init_time_left
        self.master = master
        self.master.title("Quiz Game")
        self.content_frame = tk.Frame(master)  # Main content area for dynamic UI updates.
        self.content_frame.pack(fill="both", expand=True)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((HOST, PORT))  # Establish a connection to the server.
        # Establish a connection to the server.
        self.available_quizzes = []
        self.is_admin = False  # The default for the user is to be an
        self.current_quiz = None
        self.start()  # main entry point

    def start(self):
        self.display_auth_ui()
        # Start a new thread to handle server communication without blocking the UI
        threading.Thread(target=self.handle_server_response, daemon=True).start()

    def handle_server_response(self):
        print('Waiting for server response...')
        approve = False
        while not approve:
            try:
                self.socket, response = Secure.receive_data(self)
                print(response)
                if response.get('approved'):
                    approve = True
                    print('get list')
                    self.socket = Secure.send_data(self, json.dumps({'Command': 'get_quiz_list'}))
                    self.socket, quizzes = Secure.receive_data(self)
                    # Use `after` to run UI updates on the main thread
                    self.master.after(0, self.create_main_menu_after_auth, quizzes)
                else:
                    # Use `after` to show a message box on the main thread
                    self.master.after(0, lambda: tk.messagebox.showinfo("Authentication Failed", "Please try again."))
            except Exception as e:
                print(f"Connection error: {e}")
                self.attempt_reconnect()
                break

    def attempt_reconnect(self):
        pass
        """while True:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.connect((HOST, PORT))
                print("Reconnection successful.")
                self.handle_reconnection()
                break
            except socket.error:
                print("Reconnection failed. Retrying in 5 seconds...")
                time.sleep(5)"""

    def handle_reconnection(self):
        print("Handling reconnection...")
        # Send a reconnection request or any other necessary data to resume the session
        self.socket = Secure.send_data(self, json.dumps({'Command': 'Reconnect', 'username': self.username}))
        # Wait for server response to acknowledge reconnection and possibly send any missed updates
        self.socket, response = Secure.receive_data(self)
        if response.get('status') == 'reconnected':
            self.master.after(0, self.create_main_menu_after_auth, response.get('quizzes', []))
        else:
            print("Failed to resume session. Please restart the client.")

    def create_main_menu_after_auth(self, quizzes):
        self.available_quizzes = quizzes
        self.create_main_menu()

    def clear_content_frame(self):
        """Clear all widgets from the content frame to refresh the UI."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    # TODO: need to fix - not changing to red or blue- The main menue need to listen to changes from the server so if a room status has been change in the server the client will be notify
    def create_main_menu(self):
        self.clear_content_frame()  # Clear the frame to prepare for the main menu content.

        # Button to create a new quiz.
        create_quiz_button = tk.Button(self.content_frame, text="Create Quiz", command=self.create_quiz)
        create_quiz_button.pack()

        # Set up a canvas and scrollbar for the quizzes.
        canvas = tk.Canvas(self.content_frame)
        scrollbar = tk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        # Configure the canvas to use the scrollbar.
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # Display quizzes in the scrollable frame, 3 per line with color coding.
        print(self.available_quizzes)
        for i, quiz_info in enumerate(self.available_quizzes):
            quiz_name, quiz_status = quiz_info['name'], quiz_info['status']
            button_color = BUTTON_COLOR[quiz_status]
            if quiz_status == 'in_progress':
                command = lambda: tk.messagebox.showinfo("Notice",
                                                         "This quiz is currently in progress and cannot be joined.")
            else:
                command = lambda q=quiz_name: self.select_quiz(q)
            button = tk.Button(scrollable_frame, text=quiz_name + '\n' + quiz_status, width=20, height=10,
                               fg=button_color, font=("Helvetica", 20), command=command)
            button.grid(row=i // 3, column=i % 3, padx=10, pady=10)

        # Pack everything into the content frame.
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_quiz(self):
        """Placeholder method for creating a new quiz."""
        pass

    def select_quiz(self, quiz):
        """
        Triggered when the user selects a quiz. Prompts for a username and sends
        information to the server to join the quiz room.
        """
        self.clear_content_frame()
        #self.username = simpledialog.askstring("Username", "Enter your username:", parent=self.master)
        if self.username:
            self.socket = Secure.send_data(self, json.dumps({'Command': 'Join Quiz', 'quiz': quiz, 'username': self.username}))
            self.socket, response = Secure.receive_data(self)  # get status - the join in status and is_admin - the admin status
            #  The player can join the quiz room - response['status'] == 'joined
            self.is_admin = response['is_admin']
            self.enter_quiz_lobby(quiz, response['is_admin'])

    def enter_quiz_lobby(self, quiz_name, is_admin):
        self.current_quiz = quiz_name
        print(f"{self.username} has entered the {quiz_name} loby")
        self.clear_content_frame()
        # Initialize and display the quiz label
        quiz_label = tk.Label(self.content_frame, text=quiz_name, font=("Helvetica", 30))
        quiz_label.pack()
        # Initialize the participants frame - setup for dynamically updated participants list
        self.participants_frame = tk.Frame(self.content_frame)
        self.participants_frame.pack()

        # Display the start button only if the user is the admin
        if is_admin:
            start_button = tk.Button(self.content_frame, text="Start", command=self.start_quiz, font=("Helvetica", 14))
            start_button.pack()

        # Initiate listening for lobby updates
        threading.Thread(target=self.listen_for_lobby_updates, daemon=True).start()

    def listen_for_lobby_updates(self):
        while True:
            try:
                # Receive data from the server
                print(self.socket)
                self.socket, message = Secure.receive_data(self)
                print(message)
                if message:
                    if message['game_started']:
                        self.master.after(0, self.initiate_game_window)
                        break
                    else:
                        print(message['participants'])
                        self.update_participants_list(message['participants'])
            except socket.error as e:
                print(f"Socket error: {e}")
                self.attempt_reconnect()
                break  # Exit the loop and try to reconnect
            except BlockingIOError as e:
                # Non-blocking mode exception when no data is available
                continue
            except Exception as e:
                print(f"Error receiving lobby updates: {e}")
                break

    def update_participants_list(self, participants):
        # Clear the existing participants frame
        for widget in self.participants_frame.winfo_children():
            widget.destroy()
        # Update with new participant list
        for participant in participants:
            tk.Label(self.participants_frame, text=participant, font=("Helvetica", 20)).pack()

        # Update the participant count
        # Check if the participant count label exists, update it, or create it
        if hasattr(self, 'participants_count_label') and self.participants_count_label.winfo_exists():
            self.participants_count_label.config(text=f"Total Participants: {len(participants)}")
        else:
            self.participants_count_label = tk.Label(self.content_frame,
                                                     text=f"Total Participants: {len(participants)}",
                                                     font=("Helvetica", 16))
            self.participants_count_label.pack()

    def verify_admin_credentials(self, admin_password):
        self.socket = Secure.send_data(self, json.dumps({'Command': 'verify admin credentials', 'username': self.username,
                        'admin_password': admin_password}))
        self.socket, approval_response = Secure.receive_data(self)
        if approval_response.get('approved'):
            self.is_admin = True

    def start_quiz(self):
        print(f"The quiz is starting")
        # Perform GUI operations on the main thread
        self.socket = Secure.send_data(self, json.dumps({'Command': 'Start Quiz', 'current_quiz': self.current_quiz}))

    def display_auth_ui(self):
        self.clear_content_frame()  # Clear the frame to display new elements.

        # Create UI elements for username and password input
        username_label = tk.Label(self.content_frame, text="Username:")
        username_label.pack()
        username_entry = tk.Entry(self.content_frame)
        username_entry.pack()

        password_label = tk.Label(self.content_frame, text="Password:")
        password_label.pack()
        password_entry = tk.Entry(self.content_frame, show="*")
        password_entry.pack()

        # Buttons for registration and login
        register_button = tk.Button(self.content_frame, text="Register",
                                    command=lambda: self.handle_registration(username_entry.get(),
                                                                             password_entry.get()))
        register_button.pack()

        login_button = tk.Button(self.content_frame, text="Login",
                                 command=lambda: self.handle_login(username_entry.get(), password_entry.get()))
        login_button.pack()

    def handle_registration(self, username, password):
        # Send registration request to the server
        self.username = username
        self.socket = Secure.send_data(self, json.dumps({'Command': 'Register', 'username': username, 'password': password}))

    def handle_login(self, username, password):
        # Send login request to the server
        self.username = username
        self.socket = Secure.send_data(self, json.dumps({'Command': 'Login', 'username': username, 'password': password}))

    def initiate_game_window(self):
        # This method will be responsible for setting up the game view
        print("Initializing game window...")
        self.clear_content_frame()

        # Create a frame for the question
        self.question_frame = tk.Frame(self.content_frame)
        self.question_frame.pack(fill="both", expand=True)
        self.question_label = tk.Label(self.question_frame, text="", font=("Helvetica", 36))
        self.question_label.pack()

        # Create a frame for the answers
        self.answer_frame = tk.Frame(self.content_frame)
        self.answer_frame.pack(fill="both", expand=True)

        # Listen for quiz data
        threading.Thread(target=self.listen_for_quiz_data, daemon=True).start()

        # Create a timer label
        self.timer_label = tk.Label(self.content_frame, text="10", font=("Helvetica", 30))
        self.timer_label.pack()
        self.question_display_time = time.time()  # Capture the time when the question is displayed

        # Start the timer
        self.time_left = self.init_time_left
        self.start_timer()

    def update_quiz_ui(self, quiz_data):
        print("update ui")
        if quiz_data['type'] == 'question':
            self.client_answered = False
            # Reinitialize question_frame if it doesn't exist
            if not hasattr(self, 'question_frame') or not self.question_frame.winfo_exists():
                self.question_frame = tk.Frame(self.content_frame)
                self.question_frame.pack(fill="both", expand=True)
                self.question_label = tk.Label(self.question_frame, font=("Helvetica", 36))
                self.question_label.pack()

                self.time_left = self.init_time_left
                self.start_timer()

            self.question_label.config(text=quiz_data['question'])

            # Reinitialize answer_frame if it doesn't exist
            if not hasattr(self, 'answer_frame') or not self.answer_frame.winfo_exists():
                self.answer_frame = tk.Frame(self.content_frame)
                self.answer_frame.pack(fill="both", expand=True)

            # Clear previous answers
            for widget in self.answer_frame.winfo_children():
                widget.destroy()

            # Update answers
            for answer in quiz_data['answers']:
                button = tk.Button(self.answer_frame, text=answer, font=("Helvetica", 26),
                                   command=lambda ans=answer: self.send_answer(ans))
                button.pack(side="top", fill="x", pady=5)
                # Reset and start the timer for the new question
            self.question_display_time = time.time()  # Capture the time when the question is displayed

        elif quiz_data['type'] == 'score_update':
            self.stop_timer()
            self.display_scores(quiz_data)
        elif quiz_data['type'] == 'end':
            self.display_final_leaderboard(quiz_data)
        else:
            print(f"Received unhandled message type: {quiz_data['type']}")

    def stop_timer(self):
        # Cancel the timer if it's running
        if self.timer_event_id:
            self.master.after_cancel(self.timer_event_id)
            self.timer_event_id = None
        self.time_left = 0

    def listen_for_quiz_data(self):
        # Ask for question
        if self.is_admin:
            self.get_question()
        while True:
            try:
                # Receive quiz data from the server
                self.socket, quiz_data = Secure.receive_data(self)
                print(quiz_data)
                if quiz_data:
                    # Update the UI with new quiz data
                    self.update_quiz_ui(quiz_data)
            except socket.error as e:
                print(f"Socket error: {e}")
                self.attempt_reconnect()
                break  # Exit the loop and try to reconnect
            except Exception as e:
                print(f"Error receiving quiz data: {e}")
                break

    def start_timer(self):
        # Start a new timer
        if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
            if self.time_left > 0:
                self.timer_label.config(text=str(self.time_left))
                self.time_left -= 1
                self.timer_event_id = self.master.after(1000, self.start_timer)
            else:
                self.timer_label.config(text="Time's up!")
                if not self.client_answered:
                    self.send_time_up()

    def send_time_up(self):
        self.socket = Secure.send_data(self, json.dumps({
            'Command': 'quiz_answer',
            'quiz_name': self.current_quiz,
            'username': self.username,
            'answer': None,  # Indicating no answer was selected
            'answer_time': None  # Or the max time allocated per question
        }))
        print(f"Time's up for {self.username} on question in quiz {self.current_quiz}")

    def listen_for_game_updates(self):
        self.get_question()
        while True:
            try:
                self.socket, message = Secure.receive_data(self)
                print(message)
                if message['type'] == 'score_update':
                    # Update the client UI with the new scores
                    self.master.after(0, self.display_scores, message)
                elif message['type'] == 'question':
                    self.update_game_window(message['question'], message['answers'])
                elif message['type'] == 'end':
                    self.master.after(0, self.display_final_leaderboard, message)

                    break
            except socket.error as e:
                print(f"Socket error: {e}")
                self.attempt_reconnect()
                break  # Exit the loop and try to reconnect
            except Exception as e:
                print(f"Error receiving game updates: {e}")
                break

    def update_game_window(self, question, answers):
        # Before updating, check if the necessary widgets exist
        if hasattr(self, 'question_label') and self.question_label.winfo_exists():
            self.question_label.config(text=question)

        # Clear previous answers safely
        if hasattr(self, 'answer_frame') and self.answer_frame.winfo_exists():
            for widget in self.answer_frame.winfo_children():
                widget.destroy()

            # Create new answer buttons
            for i, answer in enumerate(answers):
                button = tk.Button(self.answer_frame, text=answer, font=("Helvetica", 26),
                                   command=lambda ans=answer: self.send_answer(ans))
                button.pack(side="top", fill="x", pady=5)

    def get_question(self):
        self.socket = Secure.send_data(self, json.dumps({'Command': 'get_question', 'quiz': self.current_quiz, 'username': self.username}))
        pass

    def send_answer(self, answer):
        answer_time = time.time() - self.question_display_time  # Calculate how long it took to answer
        self.socket = Secure.send_data(self, json.dumps({
            'Command': 'quiz_answer',
            'quiz_name': self.current_quiz,
            'username': self.username,
            'answer': answer,
            'answer_time': answer_time
        }))
        print(f"Answer sent: {answer} after {answer_time} seconds")
        # Send the selected answer to the server
        if hasattr(self, 'chosen_answer_label') and self.chosen_answer_label.winfo_exists():
            self.chosen_answer_label.config(text=f"Your choice: {answer}")
        else:
            self.chosen_answer_label = tk.Label(self.content_frame, text=f"Your choice: {answer}",
                                                font=("Helvetica", CHOSEN_ANSWER_SIZE, "bold"))
            self.chosen_answer_label.pack()

        self.client_answered = True

        # Disable answer buttons after making a choice
        for widget in self.answer_frame.winfo_children():
            widget.config(state=tk.DISABLED)

    def display_scores(self, message):
        if self.time_left > 0:
            return
        # Clear the existing frame or use a separate frame to display scores
        self.clear_content_frame()
        print("Display score")
        # Display the top players
        for i, (username, score) in enumerate(message['top_players']):
            label = tk.Label(self.content_frame, text=f"Top {i + 1}: {username} with {score} points",
                             font=("Helvetica", 20))
            label.pack()

        # Display the user's score
        your_score_label = tk.Label(self.content_frame, text=f"Your score: {message['Your Score']}",
                                    font=("Helvetica", 20))
        your_score_label.pack(side='bottom')

        # Use timer_label for the countdown
        if not hasattr(self, 'timer_label') or not self.timer_label.winfo_exists():
            self.timer_label = tk.Label(self.content_frame, text="10", font=("Helvetica", 20))
            self.timer_label.pack(side='bottom', fill='x')

        self.timer_label.config(text="Next question in: 10")
        self.update_countdown()  # Start the countdown

    def update_countdown(self):
        if self.time_left > 0:
            self.timer_label.config(text=f"Next question in: {self.time_left}")
            self.time_left -= 1
            self.master.after(1000, self.update_countdown, id="update_countdown_id")
        else:
            self.timer_label.config(text="Loading next question...")
            print('Loading next question...')
            self.request_next_question()

    def request_next_question(self):
        # Send a request to the server to get the next question
        self.socket = Secure.send_data(self, json.dumps({'Command': 'get_question', 'quiz': self.current_quiz}))

    def display_final_leaderboard(self, data):
        self.clear_content_frame()
        tk.Label(self.content_frame, text="Final Leaderboard", font=("Helvetica", 30)).pack()
        for i, (username, score) in enumerate(data['leaderboard']):
            tk.Label(self.content_frame, text=f"{i + 1}. {username} - {score}", font=("Helvetica", 20)).pack()

        # Ensure the "Return to Main Menu" button is visible and functional
        return_button = tk.Button(self.content_frame, text="Return to Main Menu", command=self.reset_and_show_main_menu,
                                  font=("Helvetica", 14))
        return_button.pack(side='bottom')

    def reset_and_show_main_menu(self):
        # Reset relevant client-side variables
        self.current_quiz = None
        self.is_admin = False
        self.current_quiz = None
        try:
            self.socket = Secure.send_data(self, json.dumps({'Command': 'get_quiz_list'}))
        except socket.error as e:
            print(f"Socket error: {e}")
            self.attempt_reconnect()
        self.socket, self.available_quizzes = Secure.receive_data(self)
        self.create_main_menu()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x600")  # Set the window size.
    client = QuizClient(root)  # Instantiate the QuizClient.
    root.mainloop()  # Start the Tkinter main loop.
