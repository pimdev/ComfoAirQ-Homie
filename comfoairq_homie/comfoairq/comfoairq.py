import time
import logging

from pycomfoconnect import *

logger = logging.getLogger(__name__)

class ComfoAirQ(object):


    comfoconnect_settings = {}
    comfoconnect_bridge = None
    comfoconnect = None
    callback_sensor = None
    connection_event : threading.Event = None
    registered_sensors = {}
    _stay_connected = False
    _exit = False

    state_callbacks = []


    def __init__(self, comfoconnect_settings = None):

        assert comfoconnect_settings

        self.comfoconnect_settings = comfoconnect_settings
        self.connection_event = threading.Event()

        self._init_thread = threading.Thread(target=self._thread_loop,name="ComfoAirQThread")
        self._init_thread.start()




    def bridge_discovery(self,host = None):
        ## Bridge discovery ################################################################################################

        # Method 1: Use discovery to initialise Bridge
        # bridges = Bridge.discover(timeout=1)
        # if bridges:
        #     bridge = bridges[0]
        # else:
        #     bridge = None

        # Method 2: Use direct discovery to initialise Bridge
        bridges = Bridge.discover(host)
        if bridges:
            bridge = bridges[0]
        else:
            bridge = None

        # Method 3: Setup bridge manually
        # bridge = Bridge(args.ip, bytes.fromhex('0000000000251010800170b3d54264b4'))

        if bridge is None:
            logger.warning("No bridges found!")
            return None

        logger.info("Bridge found: %s (%s)" % (bridge.uuid.hex(), bridge.host))

        bridge.debug = False

        return bridge
    
    def callback_sensor_function(self,var,value):
        if self.callback_sensor is not None:
            self.callback_sensor(var,value)

    def register_sensor(self, sensor_id, sensor_type = None):
        self.registered_sensors[sensor_id] = sensor_type
        if self.comfoconnect:
            if self.comfoconnect.is_connected():
                self.comfoconnect.register_sensor(sensor_id,sensor_type)


    def exit(self):
        self._exit = True
        self.connection_event.set()
        pass
    
    def disconnect(self):
        logger.info("Disconnection request")
        self._stay_connected = False
        self.connection_event.set()

    def connect(self):
        logger.info("Connection request")
        self._stay_connected = True
        self.connection_event.set()

    def _thread_loop(self):
        while not self._exit:
            logger.info("Threads :{} - {} ".format(threading.active_count(),threading.enumerate()))
            if self._stay_connected:
                logger.info("_stay connected is True - {}".format(self._stay_connected))
                if self.comfoconnect_bridge is None:
                    self.comfoconnect_bridge = self.bridge_discovery(self.comfoconnect_settings['COMFOCONNECT_HOST'])
                    if  self.comfoconnect_bridge is not None:
                        self.comfoconnect = ComfoConnect(self.comfoconnect_bridge, 
                                                        bytes.fromhex(self.comfoconnect_settings['COMFOCONNECT_UUID']), 
                                                        self.comfoconnect_settings['COMFOCONNECT_NAME'],
                                                        self.comfoconnect_settings['COMFOCONNECT_PIN'])
                        self.comfoconnect.callback_sensor = self.callback_sensor_function
                        try:
                            logger.info("Trying to connect")
                            self.comfoconnect.connect(True)
                            for sensor in self.registered_sensors:
                                self.comfoconnect.register_sensor(sensor,self.registered_sensors[sensor])
                        except (Exception) as ex:
                            logger.warning("Comfoairq Could not connect to the bridge")
                            logger.warning(ex)
                            logger.info("Threads :{} - {} ".format(threading.active_count(),threading.enumerate()))
                            self.comfoconnect_bridge = None                    
                else:
                    logger.info("comfoconnect.is_connected is : {}".format(self.comfoconnect.is_connected()))
                    if not self.comfoconnect.is_connected():
                        logger.info("Disconnection attempt ")
                        self.comfoconnect.disconnect()
                        self.comfoconnect_bridge = None
            else:                
                logger.info("_stay connected is False - {}".format(self._stay_connected))
                if self.comfoconnect_bridge is not None:
                    if self.comfoconnect.is_connected():
                        logger.info("Disconnection after request")
                        self.comfoconnect.disconnect()
                    self.comfoconnect_bridge = None
            self.run_on_state_change_callbacks()
            if self.connection_event.wait(60):
                logger.info("connection event recieved")
                self.connection_event.clear()
        #_exit == True       
        if self.comfoconnect_bridge is not None:
            if self.comfoconnect.is_connected():
                self.comfoconnect.disconnect()
                self.comfoconnect_bridge = None
        self.run_on_state_change_callbacks()

    def add_on_state_change_callback(self, callback):
        self.state_callbacks.append(callback)

    def run_on_state_change_callbacks(self):
        for callback in self.state_callbacks:
            try:
                callback()
            except Exception as e:
                pass