import socket
import threading
import json
import select
import time
import mysql.connector
from random import randint
import sys

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

IP = socket.gethostbyname(socket.gethostname())
print(IP)

sock.bind((IP, 4567))
sock.listen()

FREE_PORTS = [x for x in range(7000, 10000) if x != 8000]

REGISTERED_CLIENTS = []

ID_TO_CONNECTION_MAP = {}

_SET_FLAG_ = {}

_MODE_ = ''

TEMP_SERVER_FOR_REQUESTED_CLIENT_ADDRESS = ''
TEMP_SERVER_FOR_REQUESTED_CLIENT_PORT = 0

class RequestHandlerServer:

    def __init__(self):
        global FREE_PORTS
        global IP
        self.REQUEST_ADDRESS = ''
        self.CLIENT_POOL = []
        self.AVAILABLE_IP = IP
        self.AVAILABLE_PORT = 0
        #self.portAllocator()


    def portAllocator(self):
        global FREE_PORTS
        if len(FREE_PORTS) > 0:
            self.AVAILABLE_PORT = FREE_PORTS[0]
            print('Port allocated to the game server ', self.AVAILABLE_PORT)
            FREE_PORTS.remove(self.AVAILABLE_PORT)
        else:
            print('ALL PORTS OCCUPIED')

    ''' Remove clients no longer available '''
    def filterClients(self):
        start_time = 0
        while True:
            if start_time <= time.time():
                global ID_TO_CONNECTION_MAP
                print('Current CLients : ', ID_TO_CONNECTION_MAP.keys(), '   ----  Filtering Clients')
                temp_iterateable = ID_TO_CONNECTION_MAP.copy()
                temp = []
                for x in temp_iterateable:
                    try:
                        temp_iterateable[x].send(b'_PING_')
                    except socket.error as e:
                        print("ERROR -> _PING_ for Person : ", x)
                        temp.append(x)
                
                for x in temp:
                    if x in ID_TO_CONNECTION_MAP:
                        temp_iterateable[x].close()
                        del ID_TO_CONNECTION_MAP[x]
                        print(f'OFFLINE CLIENT {x} REMOVED FROM ID_TO_CONNECTION_MAP')
                time.sleep(0.3)

    ''' Handle incoming request '''
    def handle(self):
        # self.filterClients()
        print('CONNECTED_CLIENTS -> ', ID_TO_CONNECTION_MAP.keys())
        print('connection from : {}'.format(self.REQUEST_ADDRESS))
        # print('Waiting for another player')
        
        if len(self.CLIENT_POOL) == 2:
            local_pool = self.CLIENT_POOL
            self.CLIENT_POOL = []
            print('Player found')
            self.setupGameServer(local_pool)
    
    ''' Dummy Method No Use '''
    def peerOnRequestListener(self):
        global FREE_PORTS
        global TEMP_SERVER_FOR_REQUESTED_CLIENT_ADDRESS
        global TEMP_SERVER_FOR_REQUESTED_CLIENT_PORT
        IP = self.AVAILABLE_IP
        TEMP_SERVER_FOR_REQUESTED_CLIENT_ADDRESS = IP
        self.portAllocator()
        PORT = self.AVAILABLE_PORT
        TEMP_SERVER_FOR_REQUESTED_CLIENT_PORT = PORT
        temp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_server.bind((IP, PORT))
        temp_server.settimeout(200)
        temp_server.listen(2)

        connections = []

        while True:
            try:
                conn, addr = temp_server.accept()
                connections.append(conn)
                if len(connections) == 2:
                    self.peerOnRequest(connections)
                    temp_server.close()
                    temp_server.shutdown(0)
                    if self.AVAILABLE_PORT not in FREE_PORTS:
                        FREE_PORTS.append(self.AVAILABLE_PORT)
                        print('Port released by temp await server')
            except socket.error:
                temp_server.close()
                temp_server.shutdown(0)
                if self.AVAILABLE_PORT not in FREE_PORTS:
                    FREE_PORTS.append(self.AVAILABLE_PORT)
                    print('Port released by temp await server')
                break


    def peerOnRequest(self, peer_list):

        if len(peer_list) == 2:
            local_pool = peer_list
            self.CLIENT_POOL = []
            print('Initiating game server with the requested peer')
            self.setupGameServer(local_pool)


    def setupGameServer(self, local_pool):
        self.portAllocator()
        IP = self.AVAILABLE_IP
        PORT = self.AVAILABLE_PORT
        address_obj = {
            'IP': IP,
            'PORT': PORT
        }
        server_addr = json.dumps(address_obj).encode('utf-8')

        for request in local_pool:
            try:
                request.send(server_addr)
            except socket.error:
                print('Error inviting the clients')

        try:    
            # self.CLIENT_POOL = []
            GameServerObj = GameSessionServerInit(IP, PORT)
            cThread = threading.Thread(target=GameServerObj.gameServerInit)
            cThread.daemon = True
            cThread.start()
            #GameServerObj.gameServerInit()
        except socket.error as e:
            print(e)



class GameSessionServerInit:

    def __init__(self, ip, port):
        self.IP = ip
        self.PORT = port
        self.connections = []
        self.game_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection_addresses = []
        self.time_up = 0
        self.local_player_uId = {}
        self.local_player_avatar = {}
        self.local_player_connections = {}
        self.graceful = False
        self.global_counter = 0


    ''' Updating UID in dictionary mentaining UID '''
    def listenForFlag(self, connection):
        global ID_TO_CONNECTION_MAP
        try:
            flag = connection.recv(1024)
            
            if not flag:
                print('Flag error at game server')
                return
            
            flag = json.loads(flag)

            ID_TO_CONNECTION_MAP[flag['UID']] = connection
            
            self.local_player_uId[flag['UID']] = 0
            self.local_player_avatar["AVATAR_ID_" + flag['UID']] = flag["AVATAR_ID"]
            self.local_player_connections[flag['UID']] = connection
        
        except socket.error:
            print('Socket error at listening for flag in game server')

    ''' Initializing game server '''
    def gameServerInit(self):      
        try:

            self.game_server.bind((self.IP, self.PORT))
            self.game_server.listen(2)
            self.game_server.settimeout(15)
            print('Game server up and listening..')

            try:
                ts = []
                if len(self.connections) < 2:
                    for i in range(2):
                        connection, address = self.game_server.accept()
                        self.listenForFlag(connection)
                        self.connections.append(connection)
                        self.connection_addresses.append(address)

                if len(self.connections) == 2:
                    for i in range(len(self.connections)):
                        cThread = threading.Thread(target=self.processReply, args=(self.connections[i],))
                        ts.append(cThread)
                        print('I/O Thread Started for : ', self.connection_addresses[i])
                
                cThread_reqHand = threading.Thread(target=self.requestHandler)
                ts.append(cThread_reqHand)

                 # Start all threads
                for x in ts:
                    x.start()

                # Wait for all of them to finish
                for x in ts:
                    x.join()

                time.sleep(1)
                # self.gameUpMsg()
                
                # self.determineWinner()
                self.serverDisposer()

            except socket.timeout:
                print('Game server timed out because of zero connections')
                self.serverDisposer()
                
        except socket.error as e:
            print(e)
    
    ''' Score board for a game '''
    def sendScoreObj(self, gameUp):
        letters = self.letterBord()
        score_obj = self.local_player_uId
        score_obj['AVATARS'] = self.local_player_avatar
        score_obj['_BOARD_'] = letters

        if gameUp:
            score_obj['_STATUS_'] = '1'
        else:
            score_obj['_STATUS_'] = '0'
        score_obj = json.dumps(score_obj, ensure_ascii=False).encode('utf-8')

        try:
            for conn in self.connections:
                conn.sendall(score_obj)
        except socket.error:
            print('ERROR AT sendScoreObj')
            self.serverDisposer()
        print(score_obj)
    
    ''' Set of letters to be sent to each player '''
    def letterBord(self):
        with open('letters_table.json', encoding='utf-8') as letters_file:
            letters_data = json.load(letters_file)
        letters = ''
        for _ in range(16):
            key = str(randint(1, 16))
            index = randint(0, 5)
            letters += letters_data[key][index]
        letters = list(letters)
        for x in range(len(letters)):
            letters[x] = letters[randint(0, len(letters)-1)]
        
        letters = str(letters)
        print("Board ------------------> ", letters)
        return letters


    ''' Assign score to respective player '''
    def assignScore(self, uID):
        # score = self.checkWordsFormed(word)
        self.local_player_uId[uID] += 10 

    ''' Evaluate the words that each player formed legacy method '''
    def checkWordsFormed(self, word):
        with open('words.json') as words_file:
            words_data = json.load(words_file)
        
        correct_word_list = words_data['keys'][self.global_counter][1]['words']
        if word in correct_word_list:
            score = 10
        else:
            score = 0
        return score

    ''' Determine winner and send #WON flag to it '''
    def determineWinner(self):
        players = []
        for x in self.local_player_uId:
            players.append(x)

        try:
            if len(self.local_player_uId) > 1:
                try:
                    if self.local_player_uId[players[0]] == self.local_player_uId[players[1]]:
                        print('DRAW')
                        for conn in self.connections:
                            conn.sendall(b'#DRAW')
                    
                    elif self.local_player_uId[players[0]] > self.local_player_uId[players[1]]:
                        self.local_player_connections[players[0]].sendall(b'#WON')
                        self.local_player_connections[players[1]].sendall(b'#LOOSE')
                    
                    elif self.local_player_uId[players[0]] < self.local_player_uId[players[1]]:
                        self.local_player_connections[players[0]].sendall(b'#LOOSE')
                        self.local_player_connections[players[1]].sendall(b'#WON')
                
                except socket.error as e:
                    print('ERROR AT determineWinner SENDING WINNING # TO USERS : ', e)
                    self.serverDisposer()
        except socket.error as e:
            print('ERROR AT determineWinner SENDING WINNING # TO USERS : ', e)
            self.serverDisposer()

    ''' Time initialization'''
    def initTime(self):
        print('server clock initialized')
        self.time_up = time.time() + 10


    ''' This method frees the port occupied by the game server at termination '''
    def releasePort(self):
        global FREE_PORTS
        if self.PORT not in FREE_PORTS:
            print('Freeing port {}'.format(self.PORT))
            FREE_PORTS.append(self.PORT) 

    """ Dummy Method legacy method """
    def checkForConnections(self):
        try:
            read, write, error = select.select(self.connections, self.connections, self.connections, 10)
        except select.error:
            print('client dropped...')
            self.game_server.shutdown(2)
            self.game_server.close()

        # if ready_to_read and ready_to_write:
        #     return True
        # else:
        #     return False
    """ Dummy Method legacy method """
    def peerAddressData(self):
        data = {
            'Peer1': self.connection_addresses[0],
            'Peer2': self.connection_addresses[1]
            }
        data = json.dumps(data).encode('utf-8')
        return data

    ''' Legacy mrhod '''
    def sendConstantPing(self):
        for connection in self.connections:
            connection.send('_PING_'.encode('utf-8'))

    
    # serverDisposer    override
    def clientDissconnected_intenional(self, conn):
        try:
            print("---------- CLiENT DISCONNECT INTENTIONAL --------")
            if self.PORT in FREE_PORTS:
                print('Server Already Closes')
                return
            
            for __conn in self.connections:
                if __conn != conn:
                    print(__conn, " ------- WOOOONNN ------------")
                    __conn.send("#WON".encode('utf-8'))
            
            try:
                for _conn in self.connections:
                    _conn.close()
            except socket.timeout:
                print("Error in Closing the connection of Disconnecting Client ----- ClientIntentionalDisconnection")
            self.connections = []
            
            #Disposing the server
            self.serverDisposer()
        except socket.error as e:
            print("Socket's Already Closed :)")


    ''' Dispose server after game end '''
    def serverDisposer(self):
        print('Shutting down game server')
        self.game_server.close()
        self.releasePort()

    """ Ending connection with client gracefully """
    def gracefulEndConnection(self):
        print('Gracefully ending client connection')
        for conn in self.connections:
            conn.close()
        self.graceful = True

    # handleDroppedPeer
    def handleDroppedPeer(self, conn):
        self.game_server.settimeout(20)
        
        try:
            print("Waiting for same client reconnection..")
            conn_renew, addr = self.game_server.accept()
            if conn_renew in self.connections:
                print("CLIENT RECONNECTED")


        except socket.timeout:
            print('Peer did not reconnect in time......................')
            self.clientDissconnected_intenional(conn)
    

    """ Notify client of game ending """
    def gameUpMsg(self):
        msg_game_up = '_GAMEUP_'
        try:
            for conn in self.connections:
                conn.send(msg_game_up.encode('utf-8'))
        except socket.error:
            print('ERROR AT gameUpMsg')

    """ Process answers from user """
    def processReply(self, connection):
        while True:
            try:
                data = connection.recv(1024)

                if not data:    #if person disconnects intentionally
                    self.clientDissconnected_intenional(connection)
                    break
                else:
                    data = data.decode('utf-8')
                    if data == '#1':
                        for x in self.local_player_connections:
                            if self.local_player_connections[x] == connection:
                                self.assignScore(x)
            except socket.error:
                self.clientDissconnected_intenional(connection)
                break


    ''' Handle timing '''
    def requestHandler(self):
        print('handling requests at game server...')
        self.sendScoreObj(True)
        time.sleep(0.5)

        try:
            print("----------WELCOME TO GAME------------")
            
            print("-------------sleep for 60 seconds------------")
            time.sleep(25)
                
            print('-------------Game up-------------')
            self.sendScoreObj(False)


            time.sleep(1)
            self.determineWinner()
            time.sleep(2)

            self.gracefulEndConnection()

        except socket.error as e:
            print('error at game server handler ', e)
            self.serverDisposer()
        


''' Method that deals with players coming in for random mathches '''
def mainRequestHandlerForRandom(connection, addr, local_client_list):
    try:
        try:
            for conn in local_client_list:
                conn.sendall(b'_PING_')
        except socket.error:
            print('PLAYERS IN local_client_list disconnected')
            return False
        request_server.CLIENT_POOL = local_client_list
        cThread = threading.Thread(target=request_server.handle)
        cThread.daemon = True
        cThread.start()
    except KeyboardInterrupt:
        sock.close()
        #break

def checkMode(flag):
    global _MODE_
    mode = flag['MODE']
    _MODE_ = mode
    print(mode)
        
def collectPeers(flag, connection, main_server):
    global ID_TO_CONNECTION_MAP
    temp_iterateable = ID_TO_CONNECTION_MAP.copy()
    requesting_player_uID = ''
    for x in temp_iterateable:
        if temp_iterateable[x] == connection:
            requesting_player_uID = x
            break
    
    peer_list = []
    peer_list.append(connection)
    for x in temp_iterateable:
        if x == flag['PEER']:
            print('requested peer match')
            try:
                temp_iterateable[x].send(b'_PEER_REQ_' + requesting_player_uID.encode('utf-8'))
                temp_iterateable[x].settimeout(15)

            except socket.error:
                print('ERROR ASKING PEER TO JOIN')
                break
            try:
                data = temp_iterateable[x].recv(1024)
                if not data:
                    break
                else:
                    if data.decode('utf-8') == '_YES_':
                        print('PEER ACCEPTED REQUEST')
                        peer_list.append(temp_iterateable[x])
                        main_server.peerOnRequest(peer_list)
                        break
                    else:
                        print('PEER DECLINED REQUEST')
                        connection.send(b'#PEER DECLINED')
                        break

            except socket.timeout:
                print('Peer taking to long to response')            
                    
            except socket.error:
                print('Error connecting to requested peer')
            

            


# def queryDbForRegisteredClients(user_name, table_name, database_name):
#     global REGISTERED_CLIENTS
#     db = mysql.connector.connect(
#         host = 'localhost',
#         user = 'root',
#         passwd = '',
#         database = database_name
#     )

#     cursor = db.cursor()

#     cursor.execute(f"select user_name from {table_name} where user_name = '{user_name}'")
#     client = ''
    
#     for x in cursor:
#         client = x[0]
    
#     if client == user_name:
#         return True
    
#     return False


def varifyByFlag(connection):
    global ID_TO_CONNECTION_MAP
    # global REGISTERED_CLIENTS
    global _SET_FLAG_
    connection.settimeout(10)
    while True:
        try:
            flag_recv = connection.recv(1024)
            
            if flag_recv.decode('utf-8')[0] != '{':
                print("\n", flag_recv.decode('utf-8'))
                pass
            elif not flag_recv:
                print('Flag Error')
                return False
            else:
                #print("FROM CLIENT : ", flag_recv.decode('utf-8'))
                flag = json.loads(flag_recv.decode('utf-8'))
                _SET_FLAG_ = flag
                if flag['UID'] not in ID_TO_CONNECTION_MAP:
                    if True:                                              # queryDbForRegisteredClients(flag['UID'], 'USERS', 'wordsfight'):
                        # _SET_FLAG_ = flag
                        ID_TO_CONNECTION_MAP[flag['UID']] = connection
                        # print('MAPPER -> ', ID_TO_CONNECTION_MAP)
                        checkMode(flag)
                        # print('Flag varified')
                        return True
                    else:
                        #print('Invalid ID')
                        connection.close()
                        return False
                else:
                    checkMode(flag)
                    #print('Flag varified')
                    return True
        except socket.timeout as e:
            connection.close()
            print("\nNO FLAG SENT BY CLIENT.....\n")
            return False
        except socket.error as e:
            print('Error in flag varification ', e)
            return False



if __name__ == '__main__':
    try:
        request_server = RequestHandlerServer()
        cThread_filterClients = threading.Thread(target=request_server.filterClients)
        cThread_filterClients.start()
        print('Request server running...')
        local_client_list = []
        while True:
            conn, addr = sock.accept()
            
            if varifyByFlag(conn):

                ID_TO_CONNECTION_MAP[_SET_FLAG_['UID']] = conn

                if _MODE_ == '_RAND_':
                    
                    local_client_list.append(conn)
                    if len(local_client_list) == 2:
                        
                        if local_client_list[0] in ID_TO_CONNECTION_MAP.values():
                            if mainRequestHandlerForRandom(conn, addr, local_client_list) == False:
                                local_client_list = [conn]
                            else:
                                local_client_list = []
                        else:
                            local_client_list.pop(0)
                    else:
                        print('Waiting for another player')

                elif _MODE_ == '_REQ_':

                    cThread_collectPeers = threading.Thread(target=collectPeers, args=(_SET_FLAG_, conn, request_server))
                    cThread_collectPeers.start()

                elif _MODE_ == '_CONEC_':
                        print('CONNECTED_CLIENTS -> ', ID_TO_CONNECTION_MAP.keys())
                
                else:
                    print('INVALID FLAG')
            
            else:
                print('Error in main')
    
    except KeyboardInterrupt:
        sys.exit()