from __future__ import unicode_literals

import json
import threading
import time
from datetime import datetime, timedelta
from socket import *

import daemon
import chain
import config
import misc
from  shell_wrap import *

lock = threading.Lock()


# Message Class #
class Message:
    def __init__(self, msg_type, msg=None):
        self.msg_type = msg_type
        self.msg = msg

    def __repr__(self):
        return json.dumps(self, cls=misc.ComplexEncoder)

    def prep_tcp(self):
        return misc.append_len(self.__repr__())

    def repr_json(self):
        return self.__dict__


# Send a request to the target with the block hash
# Target should return all subsequent blocks not including source of block_hash
def block_sync(target, block_hash=None):
    misc.log_message("Requesting blocks from {0}".format(target), misc.Level.MEDIUM)

    chain_message = Message(config.MSG_TYPE_CHAIN, block_hash).prep_tcp()
    thread = TCPMessageThread(target, chain_message)
    thread.start()
    thread.join()

    message = json.loads(thread.message, object_hook=misc.message_decoder)

    # Add received blocks to our chain
    if daemon.chain is None:
        daemon.chain = chain.Chain()
    try:
        for block in message.msg:
            print(block.message)
            run_shell_process(block.message)
            daemon.chain.append(block)

    except ValueError as e:
        misc.log_message(e)

    misc.log_message("Successfully synchronized {} block(s) from {}".format(len(message.msg), target), misc.Level.HIGH)


def peer_sync(target):
    misc.log_message("Requesting peers from {0}".format(target), misc.Level.MEDIUM)

    chain_message = Message(config.MSG_TYPE_PEER, None).prep_tcp()
    thread = TCPMessageThread(target, chain_message)
    thread.start()
    thread.join()

    message = json.loads(thread.message, object_hook=misc.message_decoder)

    for peer in message.msg:
        daemon.peers[peer] = datetime.now()

    daemon.peers[target[0]] = datetime.now()

    misc.log_message("Successfully synchronized {} peer(s) from {}".format(len(message.msg), target), misc.Level.MEDIUM)


# TCP Thread Classes #

# Persistent TCP Listener thread that listens for messages
class TCPListener(threading.Thread):
    def __init__(self, ip=config.BIND_IP, port=config.BIND_PORT):
        super(TCPListener, self).__init__()
        with lock:
            misc.log_message("Starting TCP Listener Thread")
        self.daemon = True
        self._port = port
        self._ip = ip
        self.stop = threading.Event()
        self.stop.clear()

        self.tcp_server_socket = socket(AF_INET, SOCK_STREAM)

    def run(self):
        # Listen for chain client connection requests
        with lock:
            misc.log_message("Listening for chain messages on port {0}".format(self._port))

        try:
            self.tcp_server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.tcp_server_socket.setblocking(False)
            self.tcp_server_socket.bind((self._ip, self._port))
            self.tcp_server_socket.listen(5)

            # List for managing spawned threads
            socket_threads = []

            # Non-blocking socket loop that can be interrupted with a signal/event
            while True and not self.stop.is_set():
                try:
                    client_socket, address = self.tcp_server_socket.accept()

                    # Spawn thread
                    client_thread = TCPConnectionThread(client_socket)
                    client_thread.start()
                    socket_threads.append(client_thread)

                except Exception as e:
                    continue

            # Clean up all the threads
            for thread in socket_threads:
                thread.join()

        except Exception as e:
            print("Could not bind to port: {0}".format(e))
        finally:
            self.tcp_server_socket.close()


# Generic outbound TCP connection handler
class TCPMessageThread(threading.Thread):
    def __init__(self, target, message, timeout=5):
        super(TCPMessageThread, self).__init__()
        with lock:
            misc.log_message("Sending Message to {0} {1}: {2}{3}"
                              .format(target[0], target[1], message[:10], '...'),
                              misc.Level.MEDIUM)
        self._target = target

        self.message = message
        self._timeout = timeout

    def run(self):
        tcp_message_socket = socket(AF_INET, SOCK_STREAM)
        tcp_message_socket.settimeout(self._timeout)

        try:
            tcp_message_socket.connect(self._target)
            tcp_message_socket.sendall(self.message.encode())

            # Get response
            self.message = ''
            message_size = None

            while True:
                if message_size is None:
                    data = tcp_message_socket.recv(config.MSG_SIZE_BYTES)
                    # Convert first message size to an integer
                    message_size = int(data.decode())
                elif len(self.message) < message_size:
                    data = tcp_message_socket.recv(4096)
                    self.message += data.decode()
                else:
                    break

        except ValueError as e:
            with lock:
                misc.log_message('Received invalid response from {0}'.format(tcp_message_socket.getsockname()))

        except Exception as e:
            with lock:
                misc.log_message('Could not send or receive message to or from the chain at {0}:\n{1}\n{2}'.format(
                    tcp_message_socket.getsockname()[0], self.message, e))

        else:
            with lock:
                misc.log_message(
                    "Received Response from {0} {1}: {2}{3}"
                        .format(self._target[0], self._target[1], self.message[:10], '...'),
                    misc.Level.MEDIUM)

        finally:
            tcp_message_socket.close()


# Generic inbound TCP connection handler
class TCPConnectionThread(threading.Thread):
    def __init__(self, socket):
        super(TCPConnectionThread, self).__init__()
        with lock:
            misc.log_message("Spawning TCP Connection Thread from {0}".format(socket.getsockname()))
        self._socket = socket

    def run(self):

        # Get message
        message = ''
        message_size = None
        try:
            while True:
                if message_size is None:
                    data = self._socket.recv(config.MSG_SIZE_BYTES)
                    # Convert first message size to an integer
                    message_size = int(data.decode())
                elif len(message) < message_size:
                    data = self._socket.recv(4096)
                    message += data.decode()
                else:
                    break
        except ValueError as e:
            misc.log_message('Received invalid packet from {0}'.format(self._socket.getsockname()))
            return

        with lock:
            misc.log_message("Received message from {0}:\n{1}".format(self._socket.getsockname(), message), misc.Level.MEDIUM)

        message = json.loads(message, object_hook=misc.message_decoder)

        # JOIN CHAIN
        if message.msg_type == config.MSG_TYPE_JOIN:
            if message.msg == daemon.chain.id:
                # Respond with success and the root key
                response = Message(config.MSG_TYPE_SUCCESS, daemon.chain.root.message).prep_tcp()
                self._respond(response)
                return
            else:
                self._respond_error()
                return
        elif message.msg_type == config.MSG_TYPE_PEER:
            # Respond with list of peers
            peer_list = list(daemon.peers.keys())

            target = self._socket.getsockname()
            if target in peer_list:
                peer_list.remove(target)

            response = Message(config.MSG_TYPE_SUCCESS, peer_list).prep_tcp()
            self._respond(response)
            return

        elif message.msg_type == config.MSG_TYPE_CHAIN:
            # Respond with the chain
            chain_list = daemon.chain.slice_chain(message.msg)

            if chain_list is None:
                self._respond_error()
                return

            response = Message(config.MSG_TYPE_SUCCESS, chain_list).prep_tcp()
            self._respond(response)
            return

        # No response, send error status
        else:
            self._respond_error()
            return

    def _respond_error(self):
        response = Message(config.MSG_TYPE_FAILURE).prep_tcp()
        self._respond(response)

    def _respond(self, message):
        with lock:
            misc.log_message("Responded with message to {}".format(self._socket.getsockname()))
            misc.log_message(message, misc.Level.MEDIUM)
        self._socket.sendall(message.encode())
        self._socket.shutdown(SHUT_WR)
        self._socket.recv(4096)
        self._socket.close()


# UDP Threading Classes
# Persistent UDP Listener thread that listens for discovery and heartbeat messages
class UDPListener(threading.Thread):
    def __init__(self, ip, port):
        super(UDPListener, self).__init__()
        with lock:
            misc.log_message("Starting UDP Listener Thread")
        self.daemon = True
        self._port = port
        self._ip = ip
        self.stop = threading.Event()

    def run(self):
        # Listen for chain client connection requests
        with lock:
            misc.log_message("Listening for chain discovery queries on port {0}".format(self._port), misc.Level.MEDIUM)

        discovery_socket = socket(AF_INET, SOCK_DGRAM)
        discovery_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        discovery_socket.bind((self._ip, self._port))
        discovery_socket.setblocking(False)

        # Non-blocking socket loop that can be interrupted with a signal/event
        while True and not self.stop.is_set():
            try:
                data, addr = discovery_socket.recvfrom(1024)
            except (OSError, IOError) as e:
                continue
            else:
                message = json.loads(data.decode(), object_hook=misc.message_decoder)
                # Decode Message Type
                if message.msg_type == config.MSG_TYPE_DISCOVER:
                    # Discovery Message
                    with lock:
                        misc.log_message("Received discovery inquiry from {0}, responding...".format(addr),
                                          misc.Level.MEDIUM)
                    response = Message(config.MSG_TYPE_SUCCESS, daemon.chain.id).__repr__()
                    discovery_socket.sendto(response.encode(), addr)

                elif message.msg_type == config.MSG_TYPE_HB:
                    # Heartbeat Message
                    if "chain" in message.msg and message.msg["chain"] == daemon.chain.id:

                        # Add the source address and port to our list of peers and update the date
                        daemon.peers[addr[0]] = datetime.now()

                        # Possible Scenarios:
                        # Heartbeat tail is same as local tail: Do nothing (in sync)
                        # Heartbeat tail is in our chain: Do nothing (out of sync)
                        # Heartbeat tail is not in our chain: Synchronize with peer (out of sync)
                        if "tail" in message.msg:
                            tail = message.msg["tail"]

                            # Check for presence of heartbeat tail in our chain
                            idx, blocks = daemon.chain.search(tail)

                            # If heartbeat tail is in our chain, do nothing
                            # If heartbeat tail isn't in our chain, synchronize with peer
                            if len(idx) <= 0:
                                block_sync((addr[0], config.BIND_PORT), daemon.chain.tail.hash)



                        with lock:
                            misc.log_message("Received heartbeat from {0}".format(addr), misc.Level.LOW)

        discovery_socket.close()


# Persistent UDP Heartbeat Thread; sends hb to peers
class UDPHeartbeat(threading.Thread):
    def __init__(self):
        super(UDPHeartbeat, self).__init__()
        with lock:
            misc.log_message("Starting UDP Heartbeat Thread")
        self.daemon = True
        self.stop = threading.Event()

    def run(self):

        # Loop through the list of peers and send heartbeat messages
        while True and not self.stop.is_set():

            for target, last_beat in list(daemon.peers.items()):

                if (last_beat + timedelta(seconds=config.MSG_HB_TTL)) < datetime.now():
                    # Check for dead peers
                    with lock:
                        misc.log_message("Removing dead peer {0}".format(target), misc.Level.MEDIUM)

                    del daemon.peers[target]
                else:
                    # Send heartbeat with root id and tail id to peers
                    s = socket(AF_INET, SOCK_DGRAM)

                    message_body = {"chain": daemon.chain.id,
                                    "tail": daemon.chain.tail.hash}

                    message = Message(config.MSG_TYPE_HB, message_body).__repr__()

                    s.sendto(message.encode(), (target, config.BIND_PORT))
                    misc.log_message("Heartbeat sent to {0}".format(target), misc.Level.LOW)
                    s.close()

            # Sleep the required time between heartbeats
            time.sleep(config.MSG_HB_FREQ)
