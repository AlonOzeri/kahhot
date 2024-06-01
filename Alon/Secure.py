from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
import json
import socket
import time
import client

# Define constants
FORMAT = 'utf-8'
HOST = '127.0.0.1'  # Define the server's IP address.
PORT = 65431  # Define the port on which the server is listening.

# Generate a key and IV (Initialization Vector)
key = b'\x04\x03|\xeb\x8dSh\xe0\xc5\xae\xe5\xe1l9\x0co\xca\xb1"\r-Oo\xbaiYa\x1e\xd1\xf7\xa2\xdf'
iv = b'#\xb59\xee\xa7\xc4@n\xe5r\xac\x97lV\xff\xf1'


# Function to encrypt plaintext using AES-CBC
def encrypt(plaintext):
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode(FORMAT)) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    return ciphertext


# Function to decrypt ciphertext using AES-CBC
def decrypt(ciphertext):
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    decrypted_data = unpadder.update(decrypted_padded_data) + unpadder.finalize()
    return decrypted_data.decode(FORMAT)


def send_data(client, data):
    try:
        sock = client.socket
        encrypted_data = encrypt(data)
        client.socket.send(encrypted_data)
        time.sleep(0.01)
        if not receive_ack(client.socket):
            print("No acknowledgment received. The connection might be broken.")
            sock = reconnect(client)
            #send_data(client, data)  # Retry sending data after reconnection
    except socket.error as e:
        print(f"Socket error occurred: {e}")
        sock = reconnect(client)
        send_data(sock, data)  # Retry sending data after reconnection
    return sock


def receive_data(client):
    try:
        encrypted_data = client.socket.recv(1024)
        if not encrypted_data:
            raise socket.error("Socket connection broken.")
        data = decrypt(encrypted_data)
        data = json.loads(data)
        send_ack(client.socket)  # Send acknowledgment after receiving data
        return client.socket, data
    except socket.error as e:
        print(f"Socket error occurred during receive: {e}")
        sock = reconnect(client)
        return sock, receive_data(sock)[1]


def send_ack(sock):
    print('Send ACK')
    ack = {'status': 'ACK'}
    encrypted_ack = (json.dumps(ack))
    try:
        sock.send(encrypted_ack)
    except socket.error as e:
        print(f"Error sending acknowledgment: {e}")


def receive_ack(sock):
    print('Receive ACK')
    try:
        encrypted_ack = sock.recv(1024)
        if encrypted_ack:
            ack = json.loads(decrypt(encrypted_ack))
            return ack.get('status') == 'ACK'
    except Exception as e:
        print(f"Error receiving acknowledgment: {e}")
    return False


def reconnect(client):
    """Attempt to reconnect to the server, creating a new socket."""
    attempt = 0
    while True:
        try:
            new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_sock.connect((HOST, PORT))
            print("Reconnected to the server successfully.")
            client.socket = new_sock
            client.time_left = client.init_time_left
            send_data(client, json.dumps({'Command': 'Reconnect', 'username': client.username}))
            return new_sock  # Return the new socket if connection is successful
        except socket.error as e:
            attempt += 1
            print(f"Reconnection attempt {attempt} failed. Error: {e}")
            time.sleep(1)  # Wait a bit before retrying (adjust as necessary)


def server_send_data(sock, data):
    try:
        encrypted_data = encrypt(data)
        sock.send(encrypted_data)
        if not server_receive_ack(sock):
            print("No acknowledgment received. The connection might be broken.")
    except socket.error as e:
        print(f"Socket error occurred: {e}")
        # Note: Server does not attempt reconnection


def server_receive_data(sock):
    try:
        encrypted_data = sock.recv(1024)
        if not encrypted_data:
            raise socket.error("Socket connection broken.")
        data = decrypt(encrypted_data)
        data = json.loads(data)
        server_send_ack(sock)  # Send acknowledgment after receiving data
        return sock, data
    except socket.error as e:
        print(f"Socket error occurred during receive: {e}")
        # Note: Server does not attempt reconnection
        return sock, None


def server_send_ack(sock):
    print('Server sending ACK')
    ack = {'status': 'ACK'}
    encrypted_ack = encrypt(json.dumps(ack))
    sock.send(encrypted_ack)


def server_receive_ack(sock):
    print('Receive ACK')
    try:
        encrypted_ack = sock.recv(1024)
        if encrypted_ack:
            ack = json.loads(encrypted_ack)
            return ack.get('status') == 'ACK'
    except Exception as e:
        print(f"Error receiving acknowledgment: {e}")
    return False
