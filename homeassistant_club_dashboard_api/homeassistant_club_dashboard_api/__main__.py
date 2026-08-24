import os
from flask import Flask, request, render_template
from flask_cors import CORS
from threading import Thread
from flask_socketio import SocketIO, send, emit

import json
import signal
import logging
import threading
import requests
import time
import paho.mqtt.client as mqtt
import ssl
import sys
import uuid
import websockets
import asyncio
import uuid
# import socketio

import homeassistant_club_dashboard_api.db as db
import homeassistant_club_dashboard_api.dashboard_api as api
from homeassistant_club_dashboard_api.middleware import Middleware as auth


app = Flask(__name__)
CORS(app)
# sio = socketio.Client()
logging.basicConfig(level=logging.DEBUG)

app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins='*')

#Variables-----------------------------------------------------------------------------------------------------------------------
club_uuid = ""
club_name = ""
home_assistant_access_key = ""
mqtt_user_name = ""
mqtt_user_password = ""
mqtt_broker = ""
mqtt_port = ""
api_genaration_url = 'https://pro.syltek.com/hermes/api/v1/Lights/plcnext/register?'
home_assistant_url = 'http://homeassistant.local:8123'
global_tenant = ''
global_idTerminal=''
global_cardCode = ''
global_doorState = ''
ok_cloud_access_token =""
club_id = ""
back_end_url = ""
integrated_club = False
integrated_club_type = ""
facility_id = 0

# Stable Home Assistant entity mapping -------------------------------------------------------------
# MQTT/backend IDs can change per club (66, 70, 72...) but Home Assistant should expose
# stable entities for automations and dashboards: binary_sensor.pista_1, binary_sensor.pista_2...
# and binary_sensor.puerta_1, binary_sensor.puerta_2...
LIGHT_ENTITY_MAP = {}          # backend/MQTT light id -> HA entity suffix (pista_N)
LIGHT_ENTITY_REVERSE_MAP = {}  # HA entity suffix (pista_N) -> backend light id
DOOR_ENTITY_MAP = {}           # backend/MQTT door id -> HA entity suffix (puerta_N)
DOOR_ENTITY_REVERSE_MAP = {}   # HA entity suffix (puerta_N) -> backend door id

def _entity_suffix(entity_id):
    return str(entity_id).replace('binary_sensor.', '')

def get_stable_light_entity_id(light_id):
    return LIGHT_ENTITY_MAP.get(str(light_id), str(light_id))

def get_original_light_id(entity_id):
    suffix = _entity_suffix(entity_id)
    return LIGHT_ENTITY_REVERSE_MAP.get(suffix, suffix)

def get_stable_door_entity_id(door_id):
    return DOOR_ENTITY_MAP.get(str(door_id), 'door{}'.format(door_id))

def get_original_door_id(entity_id):
    suffix = _entity_suffix(entity_id)
    return DOOR_ENTITY_REVERSE_MAP.get(suffix, suffix.replace('door', ''))

# Home Assistant state normalization -------------------------------------------------------------
# Different OK Cloud connectors can encode an OFF light state using different values:
# "off", "false", 0, False, "closed", etc. Home Assistant binary sensors must receive
# an explicit "off"/"on" state. Any positive/dimmed light level is treated as "on".
OFF_LIGHT_VALUES = {"off", "false", "0", "none", "null", "", "closed"}

def normalize_ha_light_state(state, brightness_pct=None):
    normalized_state = str(state).strip().lower()

    if normalized_state in OFF_LIGHT_VALUES:
        return "off"

    if normalized_state == "dim":
        try:
            return "on" if int(brightness_pct or 0) > 0 else "off"
        except Exception:
            return "on"

    return "on"

def normalize_ha_light_brightness(state, brightness_pct=None):
    if normalize_ha_light_state(state, brightness_pct) == "off":
        return 0
    try:
        return int(brightness_pct) if brightness_pct is not None else 100
    except Exception:
        return 100


#Ignore sun light status-----------------------------------------------------------------------------------------------------------------------
def checkIgnoreSunLight():
    key = 'ignore_sun_time' 
    if(db.getConfigurationByKey(key) == '1'):
        logging.info('ignore_sun_time = True')
        return True
    else:
        logging.info('ignore_sun_time = Fales')
        return  False

#Use extra periods-----------------------------------------------------------------------------------------------------------------------
def checkUseExtraPeriods():
    key = 'extra_periods'
    if(db.getConfigurationByKey(key) == '1'):
        logging.info('use_extras_periods = True')
        return True
    else:
        logging.info('use_extras_periods = Fales')
        return False

#API Routes-----------------------------------------------------------------------------------------------------------------------
def createTables():
    logging.info('Tables Creating')
    return db.createTables()

def getTenant():
    response = {"tenant": global_tenant}
    if(club_name!=''):
        response = {"tenant": club_name}
    return response, 200

def getDoorsForDB():
    logging.info('Doors from DB')
    return db.getDoors()

@app.route('/api/check-access', methods=['GET'])
def validate_access_token():
    return api.checkAccess()

@app.route('/api/get-club_uuid', methods=['GET'])
def get_club_uuid():
    return (sys.argv[1])

@app.route('/api/create-tables', methods=['GET'])
def create_tables():
    return db.createTables()

@app.route('/api/get-config', methods=['GET'])
def get_config():
    return (api.getConfig())

@app.route('/api/get-doors', methods=['GET'])
def get_doors():
    return (api.getDoors(sys.argv[6],sys.argv[7],sys.argv[8],sys.argv[9]))

@app.route('/api/get-lights', methods=['GET'])
def get_lights():
    return (api.getLights(sys.argv[6],sys.argv[7],sys.argv[1],sys.argv[8],sys.argv[9],sys.argv[10],sys.argv[11]))

@app.route('/api/get-tenant', methods=['GET'])
def get_tenant():
    # return (getTenant())
    return (db.getClubName(sys.argv[7], sys.argv[6], sys.argv[8]))


@app.route('/api/get-entity-state', methods=['POST'])
def get_entity_state():
    return (getEntityState())


@app.route('/api/update-config', methods=['POST'])
def update_config():
    return (api.updateConfig())

@app.route('/api/add-door', methods=['POST'])
def add_door():
    return (api.addDoor())

@app.route('/api/delete-door', methods=['POST'])
def delete_door():
    return (api.deleteDoor())

@app.route('/api/update-door-id', methods=['POST'])
def update_door_id():
    return (api.updateDoorId())

@app.route('/api/update-door-entity-id', methods=['POST'])
def update_door_entity_id():
    return (api.updateDoorEntityId())

@app.route('/api/update-door-name', methods=['POST'])
def update_door_name():
    return (api.updateDoorName())

@app.route('/api/update-door-mode', methods=['POST'])
def update_door_mode():
    return (api.updateDoorMode(sys.argv[6],sys.argv[7],sys.argv[8]))

@app.route('/api/update-light-mode', methods=['POST'])
def update_light_mode():
    return (api.updateLightMode(sys.argv[6], sys.argv[7], sys.argv[8]))

@app.route('/api/update-light-limited-option', methods=['POST'])
def update_limited_option():
    return (api.updateLightLimitedOption(sys.argv[6], sys.argv[7], sys.argv[8]))

@app.route('/api/update-min-light-level', methods=['POST'])
def update_min_light_level():
    return (api.updateMinLightLevel(sys.argv[6], sys.argv[7], sys.argv[8]))

@app.route('/api/update-max-light-level', methods=['POST'])
def update_max_light_level():
    return (api.updateMaxLightLevel(sys.argv[6], sys.argv[7], sys.argv[8]))

@app.route('/api/update-entity-state', methods=['POST'])
def update_entity_state():
    return (updateEntityState(sys.argv[8]))

# WebSocket------------------------------------------------------------------------------------------------------------------------------
# async def handle_websocket(websocket, path):
#     logging.info("WebSocket Handler Started")

#     while True:
#         try:
#             message = await websocket.recv()
#             logging.info(f"Received message: {message}")

#             message_dict = json.loads(message)
#             type = message_dict['type']
#             platform = message_dict['platform']
#             entity_id = message_dict['entity_id']
#             token = message_dict['access_token']
#             device_class = message_dict.get('device_class')

#             isAuthorized = auth.validateAccessToken(f"Bearer {token}")
#             logging.info(f"Token valid: {isAuthorized}")

#             if not isAuthorized:
#                 await websocket.send(json.dumps({"message": "Unauthorized, token invalid"}))
#                 continue

#             access_token = sys.argv[2]
#             url = "ws://homeassistant.local:8123/api/websocket"

#             async with websockets.connect(url) as websocket_ha:
#                 await websocket_ha.recv()
#                 await websocket_ha.send(json.dumps({
#                     "type": "auth",
#                     "access_token": access_token
#                 }))
#                 auth_response = await websocket_ha.recv()
#                 auth_result = json.loads(auth_response)

#                 if auth_result["type"] != "auth_ok":
#                     await websocket.send(json.dumps({"message": "HA Authentication Failed"}))
#                     continue

#                 # Subscribe to specific triggers (off→on, on→off, etc.)
#                 id_counter = int(time.time() * 1000)
#                 valid_light_transitions = [
#                     ("off", "on"),
#                     ("on", "off"),
#                     ("on", "dim"),
#                     ("dim", "on"),
#                     ("dim", "off"),
#                     ("off", "dim"),
#                 ]

#                 for i, (from_state, to_state) in enumerate(valid_light_transitions if device_class == "light" else [("off", "on"), ("on", "off")]):
#                     trigger_msg = {
#                         "id": id_counter + i,
#                         "type": "subscribe_trigger",
#                         "trigger": {
#                             "platform": platform,
#                             "entity_id": entity_id,
#                             "from": from_state,
#                             "to": to_state
#                         }
#                     }
#                     await websocket_ha.send(json.dumps(trigger_msg))

#                 while True:
#                     trigger_event = await websocket_ha.recv()
#                     event_data = json.loads(trigger_event)

#                     if event_data.get("type") == "event":
#                         payload = event_data["event"]["variables"]

#                         if device_class == "light":
#                             old_meta = payload["trigger"]["from_state"]["attributes"].get("meta_state")
#                             new_meta = payload["trigger"]["to_state"]["attributes"].get("meta_state")

#                             if (old_meta, new_meta) in valid_light_transitions:
#                                 logging.info(f"Light {entity_id} meta_state changed: {old_meta} -> {new_meta}")
#                                 await websocket.send(trigger_event)

#                         elif device_class == "door":
#                             logging.info(f"Door {entity_id} changed: {payload['trigger']['from_state']['state']} -> {payload['trigger']['to_state']['state']}")
#                             await websocket.send(trigger_event)

#                     elif event_data.get("type") == "auth_invalid":
#                         logging.warning("HA WebSocket token invalid")
#                         await websocket.send(json.dumps({"message": "HA WebSocket auth failed"}))
#                         break

#         except Exception as e:
#             logging.error(f"WebSocket error: {e}")
#             await websocket.send(json.dumps({"message": "Internal server error"}))

async def handle_websocket(websocket, path):
    logging.info('WebSocket Handler--------------------------------------------------------------------------------------------------------')
    # connected = True
    while True:
       
        message = await websocket.recv()
        logging.info(f"Received message: {message}")

        access_token = sys.argv[2]
        url = "ws://homeassistant.local:8123/api/websocket"

        async with websockets.connect(url) as websocket_ha:

            auth_response = await websocket_ha.recv()
            logging.info(f"Requesting authentication response : {auth_response}")
         
            auth_payload = json.dumps({"type": "auth", "access_token": access_token})
            await websocket_ha.send(auth_payload)

            
            auth_response = await websocket_ha.recv()
            logging.info(f"Authentication response: {auth_response}")
            # await websocket.send(auth_response)
            response_dict = json.loads(auth_response)
            response_type = response_dict['type']

            message_dict = json.loads(message)
            type = message_dict['type']
            platform = message_dict['platform']
            entity_id = message_dict['entity_id']
            token = message_dict['access_token']
            device_type = message_dict['device_type']
            logging.info(token)

            try:
                isAuthorized = auth.validateAccessToken(f"Bearer {token}")
                # isAuthorized = False
                logging.info(isAuthorized)
                if(isAuthorized):
                    if (response_type == "auth_ok"):
                        
                        milli_sec = int(round(time.time() * 1000))

                        if (device_type == "light"):
                            msg = json.dumps({
                                "id": milli_sec,
                                "type": type,
                                "trigger": {
                                    "platform": platform,
                                    "entity_id": entity_id,
                                    "attribute": "meta_state"
                                    }
                                })
                            
                            await websocket_ha.send(msg)
                        else:
                            msg = json.dumps({
                                "id": milli_sec,
                                "type": type,
                                "trigger": {
                                    "platform": platform,
                                    "entity_id": entity_id,
                                    "from": "off",
                                    "to": "on"
                                    }
                                })
                            
                            await websocket_ha.send(msg)
    
                            msg = json.dumps({
                                "id": milli_sec+1,
                                "type": type,
                                "trigger": {
                                    "platform": platform,
                                    "entity_id": entity_id,
                                    "from": "on",
                                    "to": "off"
                                    }
                                })
                            
                            await websocket_ha.send(msg)
                            
                        while True:
                            msg_response = await websocket_ha.recv()
                            logging.info(f" {msg_response}")
                            response_dict2 = json.loads(message)
                            response2_type = response_dict2['type']

                            if(response2_type == "event"):
                                await websocket.send(msg_response)

                            elif(response2_type == "auth_invalid"):
                                logging.info("Unauthorized")
                                await websocket.send(auth_response)
                                break
                            else:
                                logging.info("+++++++++++++++++++")
                                await websocket.send(msg_response)
                            
                    elif(response_type == "auth_invalid"):
                        logging.info("Unauthorized")
                        await websocket.send(auth_response)
                        break
                else:
                    return {"message": "Unauthorized, token invalid"}
            except Exception as e:
                logging.info("Message Not sent successfully")
                return  501 
            
            logging.info("Message sent successfully")
        
       
        # message = await websocket.recv()
        # logging.info(f"Received message: {message}")
        # await websocket.send(f"Server received: {message}")
        
def start_websocket_server():
    logging.info("start_websocket_server ================================================================")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(handle_websocket, "0.0.0.0", 5001)
        logging.info("WebSocket run Successfully")

        loop.run_until_complete(start_server)
        loop.run_forever()
    except:
        logging.info("WebSocket failed")


#----------------------------------------------------------------------------------------------------------------------------------------

# def start_socketio():
#     logging.info('3333333333333333333333333333333333')

#     try:
#         @sio.event
#         def connect():
#             logging.info('Socket.IO connection established')

#         @sio.event
#         def disconnect():
#             logging.info('Socket.IO disconnected')

#         sio.connect('0.0.0.0:5002')
    
#     except:
#         logging.info("SocketIO failed")

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')



def send_data(event, data):
    logging.info("Sending data in SocketIO")
    logging.info(event)
    logging.info(data)

    try:
        logging.info("SENDING!!!!!")
        # sio.emit(event, data)
        socketio.emit(event, data)
        # @socketio.on(event)
        # def handle_my_custom_event(data):
        #     socketio.emit('message', data)
        logging.info("SENDING!!!!!")
        
    except:
        logging.info("Data send to SocketIO failed")

#----------------------------------------------------------------------------------------------------------------------------------------

def fetch_court_ids():
    # club_uuid = sys.argv[1]

    try:
        # publisher_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        # publisher_client.username_pw_set(mqtt_user_name, mqtt_user_password)
        # publisher_client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        # publisher_client.connect(mqtt_broker, mqtt_port, 60)
        # publisher_client.loop_start()

        # responce = requests.get('http://127.0.0.1:4000/api/resourcesids/?uuid={}'.format(uuid))
        # responce = requests.get(f"{back_end_url}api/resourcesids/?uuid={club_uuid}")
        lights = db.getLights(ok_cloud_access_token,back_end_url,club_uuid,club_id, facility_id,integrated_club,integrated_club_type)
        court_ids = [d[1] for d in lights]
        c_ids = [d[0] for d in lights]

        # Build stable mapping for HA entities while keeping MQTT/backend IDs unchanged.
        # Examples: backend/MQTT 66 -> binary_sensor.pista_1, 67 -> binary_sensor.pista_2
        global LIGHT_ENTITY_MAP, LIGHT_ENTITY_REVERSE_MAP
        LIGHT_ENTITY_MAP = {}
        LIGHT_ENTITY_REVERSE_MAP = {}
        for index, light in enumerate(lights, start=1):
            stable_entity_id = f"pista_{index}"
            # light[1] is the ID normally used in MQTT/state topics; light[0] is the backend DB id.
            LIGHT_ENTITY_MAP[str(light[1])] = stable_entity_id
            LIGHT_ENTITY_MAP[str(light[0])] = stable_entity_id
            # For writes back to OK Cloud, use the backend DB id.
            LIGHT_ENTITY_REVERSE_MAP[stable_entity_id] = str(light[0])

        # create lights in HA
        for index, light in enumerate(lights, start=1):
            logging.info(f"LightID: {light[1]}, State: {light[4]}")
            light_id = get_stable_light_entity_id(light[1])
            friendly_name = light[3]
            state = light[4]
            min_level = light[5]
            max_level = light[6]
            
            api_url = home_assistant_url+"/api/states/binary_sensor.{}"
            access_token = home_assistant_access_key
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            
            if normalize_ha_light_state(state) == "off":
                brightness_pct = 0
            elif str(state).strip().lower() == "on":
                brightness_pct = max_level
            else:
                brightness_pct = min_level

            sensor_data = {
                "entity_id": light_id,
                "state": normalize_ha_light_state(state, brightness_pct),
                "attributes": {
                    "friendly_name": friendly_name,
                    "device_class": "light", 
                    "brightness": normalize_ha_light_brightness(state, brightness_pct),   
                    "meta_state": state         
                },
            }
            
            data_from_mqtt = sensor_data['entity_id']
            logging.info('entity id form mqtt:'+str(data_from_mqtt))

            api_url_sensor = api_url.format(data_from_mqtt)
            response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

            if response4.status_code == 200:
                logging.info(f"Light entity {data_from_mqtt} updated successfully!") 
                
            elif response4.status_code == 201:
                logging.info(f"Light entity {data_from_mqtt} created successfully!") 
            else:
                logging.info(f"Error creating light entity {data_from_mqtt}: {response4.status_code} - {response4.text}")
            
            # logging.info(f"Publishing discovery for light {light_id}")
            # publish_light_discovery(publisher_client, light_id, friendly_name)
            # logging.info(f"Discovery published for light {light_id}")
            
            # time.sleep(0.5)

            # publish_light_state(publisher_client, light_id, state, brightness_pct)
            # logging.info(f"Light state published for light {light_id}")

        # listen_mqtt_light_topics(court_ids)
        # listen_mqtt_light_mode_topics(court_ids)

        light_state_thread = threading.Thread(target=listen_mqtt_light_topics, args=(court_ids,))
        light_mode_thread = threading.Thread(target=listen_mqtt_light_mode_topics, args=(court_ids, c_ids,))
        min_light_level_thread = threading.Thread(target=listen_mqtt_min_light_level_topics, args=(court_ids, c_ids,))
        max_light_level_thread = threading.Thread(target=listen_mqtt_max_light_level_topics, args=(court_ids, c_ids,))
        light_limited_mode_thread = threading.Thread(target=listen_mqtt_light_limited_mode_topics, args=(court_ids, c_ids,))

        # Start both threads
        light_state_thread.start()
        light_mode_thread.start()
        min_light_level_thread.start()
        max_light_level_thread.start()
        light_limited_mode_thread.start()

        # Wait for both threads to finish
        light_state_thread.join()
        light_mode_thread.join()
        min_light_level_thread.join()
        max_light_level_thread.join()
        light_limited_mode_thread.join()

        # logging.info(responce.json())
        # if responce.status_code == 200:
        #     data = responce.json()
        #     # court_ids = [int(id) for id in data['resourceIds'].split(",")]
        #     court_ids = data['resourceIds']
        #     logging.info(court_ids)
        #     listen_mqtt_light_topics(court_ids)
        # else:
        #     logging.info(f"Error while fetching resources: {responce.status_code} - {responce.text}")

    except Exception as e:
          logging.info(f"An error occurr while fetching court ids: {e}")
          
# def publish_light_discovery(mqtt_client, light_id, friendly_name):
#     discovery_topic = f"homeassistant/light/{light_id}/config"
#     config_payload = {
#         "name": friendly_name,
#         "unique_id": f"ok_cloud_light_{light_id}", 
#         "command_topic": f"ok_cloud/light/{light_id}/set",
#         "state_topic": f"ok_cloud/light/{light_id}/state",
#         "brightness": True,
#         "schema": "json",
#         "device": {  
#             "identifiers": [f"ok_cloud_device_{light_id}"],
#             "manufacturer": "OK Cloud",
#             "model": "Smart Light",
#             "name": f"{friendly_name} Light"
#         }
#     }
    
#     info = mqtt_client.publish(discovery_topic, json.dumps(config_payload), retain=True)

#     for attempt in range(5):
#         if info.is_published():
#             logging.info(f"✅ Discovery published for light ID: {light_id}")
#             return True
#         else:
#             logging.debug(f"⏳ Waiting for publish to complete for light ID: {light_id} (Attempt {attempt+1})")
#             time.sleep(0.3)

#     logging.warning(f"❌ Failed to publish discovery for light ID: {light_id}")
#     return False
    
# def publish_light_state(mqtt_client, light_id, state, brightness_pct):
#     state_topic = f"ok_cloud/light/{light_id}/state"
#     payload = {
#         "state": state.upper(),
#         "brightness": int(brightness_pct * 2.55)
#     }

#     info = mqtt_client.publish(state_topic, json.dumps(payload))

#     # Wait a short time for publish to complete
#     for attempt in range(5):
#         if info.is_published():
#             logging.info(f"✅ State published for light ID: {light_id}, state: {state}, brightness: {brightness_pct}")
#             return True
#         else:
#             logging.debug(f"⏳ Waiting to publish state for light ID: {light_id} (Attempt {attempt+1})")
#             time.sleep(0.3)

#     logging.warning(f"❌ Failed to publish state for light ID: {light_id}")
#     return False



#---------------------------------------------------------------------------------------------------------

def listen_mqtt_light_topics(court_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
            # print("Connected with result code "+str(rc))
            # for court_id in court_ids:
            #         topic = f"ok_cloud/reservation/{club_id}/{facility_id}/{court_id}"
            #         logging.info(f"Lights Topics: {topic}")

            #         client.subscribe(topic)
                    # fetch_data_with_light_id('false',court_id)

            # for slytek intergrated
            if integrated_club:
                topic = f"ok_cloud/reservation/{integrated_club_type}/{club_uuid}"
                logging.info(f"Lights Topics: {topic}")
                client.subscribe(topic)

                for court_id in court_ids:

                    topic = f"ok_cloud/reservation/{club_uuid}/0/{court_id}"
                    logging.info("0000000000000000000000000000000000000")
                    logging.info(f"Lights Topics: {topic}")
                    logging.info("0000000000000000000000000000000000000")

                    client.subscribe(topic)
                    # fetch_data_with_light_id('false',court_id)


            # For local courts
            else:
                topic = f"ok_cloud/reservation/local/{club_id}"
                logging.info(f"Lights Topics: {topic}")
                client.subscribe(topic)

                for court_id in court_ids:
                    topic = f"ok_cloud/reservation/{club_id}/{facility_id}/{court_id}"
                    logging.info(f"Lights Topics: {topic}")
                    client.subscribe(topic)
                    # fetch_data_with_light_id('false',court_id)

            


        def on_message(client, userdata, msg):
            logging.info("************************Message Recived************************")
            topic_in_msg = msg.topic
            logging.info(f"Receive data for topic: {topic_in_msg}")
            payload = msg.payload.decode('utf-8')
            logging.info(f"Payload: {payload}")
            parsed_payload = json.loads(payload)
            logging.info(f"Parsed payload: {parsed_payload}")

            topic_length =  len(topic_in_msg.split('/'))
            logging.info(f"Topic length: {topic_length}")
            if topic_length == 4:
                if integrated_club:
                    # array_of_payload = [{'court_id': int(key), 'state': value} for key, value in parsed_payload.items()]
                    
                    array_of_payload = [
                        {
                            'court_id': int(key),
                            'state': value.get('state'),
                            'brightness_pct': value.get('brightness_pct')
                        }
                        for key, value in parsed_payload.items()
                    ]

                    for courts in array_of_payload:
                        court_id = courts['court_id']
                        state = courts['state']
                        brightness_pct = courts['brightness_pct']
                        
                        logging.info(f"court_id: {court_id} , state: {state} , brightness_pct: {brightness_pct}")
                        fetch_data_with_light_id(state,court_id,brightness_pct)


                else:
                    array_of_payload = [{'court_id': int(key), 'state': value[0], 'facility_id': value[1]} for key, value in parsed_payload.items()]
                    filtered_array_of_payload = [{k: v for k, v in obj.items() if k != 'facility_id'} for obj in array_of_payload if obj['facility_id'] == int(facility_id)]

                    for courts in filtered_array_of_payload:
                        court_id = courts['court_id']
                        state = courts['state']
                        logging.info(f"court_id: {court_id}, state: {state}")
                        fetch_data_with_light_id(state,court_id)


            else:
                logging.info("State change Manually////////////////////////////////////////////JJ")
                if topic_length == 0:
                    logging.info("Invalid topic length, cannot extract court ID.")
                    return
                court_id = topic_in_msg.split('/')[topic_length-1]
                logging.info(f"Court ID from topic2: {court_id}")
                payload = msg.payload.decode('utf-8')   
                logging.info(f"Payload before parsing2: {payload}")
                parsed_payload = json.loads(payload)
                logging.info(f"Parsed Payload2: {parsed_payload}")

                # Handle both string payload ("on"/"off") and dict payload ({"state": "on", "brightness_pct": 100})
                if isinstance(parsed_payload, str):
                    state_value = parsed_payload
                    brightness_value = 100 if parsed_payload == 'on' else 0
                else:
                    state_value = parsed_payload['state']
                    brightness_value = parsed_payload['brightness_pct']
                logging.info(f"Court ID: {court_id}, New State: {state_value} , Brightness: {brightness_value}")
                fetch_data_with_light_id(state_value, court_id, brightness_value)
                logging.info("State change Manually////////////////////////////////////////////")

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        # parent_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        logging.info('MQTT CETIFI LOC===================================')
        
        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem', 
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt', 
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )
        logging.info('MQTT CETIFI LOC===================================')
        
        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(mqtt_broker, mqtt_port, 60)
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening lights mqtt message: {e}")

#---------------------------------------------------------------------------------------------------------
def fetch_data_with_light_id(state,court_id,brightness_pct= None):

      # Define the API endpoint and parameters  
    try:

        api_url = home_assistant_url+"/api/states/binary_sensor.{}"
        access_token = home_assistant_access_key
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        
        if brightness_pct is None:
            brightness_pct = 100 if normalize_ha_light_state(state) == "on" else 0

        data_from_mqtt = get_stable_light_entity_id(court_id)
        api_url_sensor = api_url.format(data_from_mqtt)

        respose_get_entity = requests.get(api_url_sensor, headers=headers)

        if respose_get_entity.status_code == 200:
            logging.info(respose_get_entity.json())

            sensor_data = {
                "entity_id": data_from_mqtt,
                "state": normalize_ha_light_state(state, brightness_pct),
                "attributes": {
                    "friendly_name": respose_get_entity.json()['attributes']['friendly_name'],
                    "device_class": "light",
                    "brightness": normalize_ha_light_brightness(state, brightness_pct),
                    "meta_state": state 
                },
            }
            
            response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

            if response4.status_code == 200:
                logging.info(f"Light entity {data_from_mqtt} updated successfully!")    
            elif response4.status_code == 201:
                logging.info(f"Light entity {data_from_mqtt} created successfully!") 
            else:
                logging.info(f"Error creating light entity {data_from_mqtt}: {response4.status_code} - {response4.text}")

        # publish_light_state(court_id, state, brightness_pct)

        logging.info(f"Updated light state for court_id: {court_id}, state: {state}, brightness_pct: {brightness_pct}")

    except Exception as e:
          logging.info(f"An error occurr while updating light states: {e}")

#---------------------------------------------------------------------------------------------------------

def listen_mqtt_light_mode_topics(court_ids, c_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
           
            # for slytek intergrated
            if integrated_club:
                
                if integrated_club_type == 'syltek':
                    for court_id in c_ids:
                        topic = f"ok_cloud/light/automatic/{club_uuid}/0/{court_id}"
                        logging.info(f"Lights Topics: {topic}")

                        client.subscribe(topic)
                else:
                    for c_id in c_ids:
                        topic = f"ok_cloud/light/automatic/{club_id}/0/{c_id}"
                        logging.info(f"Lights Topics: {topic}")

                        client.subscribe(topic)

            # For local courts
            else:
                for court_id in court_ids:
                    topic = f"ok_cloud/light/automatic/{club_id}/{facility_id}/{court_id}"
                    logging.info(f"Lights Topics: {topic}")

                    client.subscribe(topic)


        def on_message(client, userdata, msg):
            topic_in_msg = msg.topic
            logging.info(f"Receive data for topic: {topic_in_msg}")
            court_id = topic_in_msg.split('/')[-1]
            mode = msg.payload.decode('utf-8')

            logging.info(f"Court ID: {str(court_id)}, New Mode: {str(mode)}")
            if integrated_club:
                event = f"light/{court_id}"
                data = {'message': mode}
                send_data(event, data)
            else:
                event = f"light/{court_id}"
                data = {'message': mode}
                send_data(event, data)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        
        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem', 
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt', 
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )
        
        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(mqtt_broker, mqtt_port, 60)
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening lights mode mqtt message: {e}")

def listen_mqtt_min_light_level_topics(court_ids, c_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
           
            # for slytek intergrated
            if integrated_club:
                
                if integrated_club_type == 'syltek':
                    for court_id in c_ids:
                        topic = f"ok_cloud/light/min_level/{club_uuid}/0/{court_id}"
                        logging.info(f"Min level Topics: {topic}")

                        client.subscribe(topic)
                else:
                    for c_id in c_ids:
                        topic = f"ok_cloud/light/min_level/{club_id}/0/{c_id}"
                        logging.info(f"Min level Topics: {topic}")

                        client.subscribe(topic)

            # For local courts
            else:
                for court_id in court_ids:
                    topic = f"ok_cloud/light/min_level/{club_id}/{facility_id}/{court_id}"
                    logging.info(f"Min level Topics: {topic}")

                    client.subscribe(topic)


        def on_message(client, userdata, msg):
            topic_in_msg = msg.topic
            logging.info(f"Receive data for topic: {topic_in_msg}")
            court_id = topic_in_msg.split('/')[-1]
            min_level = msg.payload.decode('utf-8')

            logging.info(f"Court ID: {str(court_id)}, New Min level: {str(min_level)}")
            if integrated_club:
                event = f"lights/min_level/{court_id}"
                data = {'message': min_level}
                send_data(event, data)
            else:
                event = f"lights/min_level/{court_id}"
                data = {'message': min_level}
                send_data(event, data)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        
        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem', 
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt', 
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )
        
        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(mqtt_broker, mqtt_port, 60)
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening lights min level mqtt message: {e}")

def listen_mqtt_max_light_level_topics(court_ids, c_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
           
            # for slytek intergrated
            if integrated_club:
                
                if integrated_club_type == 'syltek':
                    for court_id in c_ids:
                        topic = f"ok_cloud/light/max_level/{club_uuid}/0/{court_id}"
                        logging.info(f"Max level Topics: {topic}")

                        client.subscribe(topic)
                else:
                    for c_id in c_ids:
                        topic = f"ok_cloud/light/max_level/{club_id}/0/{c_id}"
                        logging.info(f"Max level Topics: {topic}")

                        client.subscribe(topic)

            # For local courts
            else:
                for court_id in court_ids:
                    topic = f"ok_cloud/light/max_level/{club_id}/{facility_id}/{court_id}"
                    logging.info(f"Max level Topics: {topic}")

                    client.subscribe(topic)


        def on_message(client, userdata, msg):
            topic_in_msg = msg.topic
            logging.info(f"Receive data for topic: {topic_in_msg}")
            court_id = topic_in_msg.split('/')[-1]
            max_level = msg.payload.decode('utf-8')

            logging.info(f"Court ID: {str(court_id)}, New Max level: {str(max_level)}")
            if integrated_club:
                event = f"lights/max_level/{court_id}"
                data = {'message': max_level}
                send_data(event, data)
            else:
                event = f"lights/max_level/{court_id}"
                data = {'message': max_level}
                send_data(event, data)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        
        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem', 
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt', 
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )
        
        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(mqtt_broker, mqtt_port, 60)
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening lights max level mqtt message: {e}")

def listen_mqtt_light_limited_mode_topics(court_ids, c_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
           
            # for slytek intergrated
            if integrated_club:
                
                if integrated_club_type == 'syltek':
                    for court_id in c_ids:
                        topic = f"ok_cloud/light/limited_mode/{club_uuid}/0/{court_id}"
                        logging.info(f"Limited mode Topics: {topic}")

                        client.subscribe(topic)
                else:
                    for c_id in c_ids:
                        topic = f"ok_cloud/light/limited_mode/{club_id}/0/{c_id}"
                        logging.info(f"Limited mode Topics: {topic}")

                        client.subscribe(topic)

            # For local courts
            else:
                for court_id in court_ids:
                    topic = f"ok_cloud/light/limited_mode/{club_id}/{facility_id}/{court_id}"
                    logging.info(f"Limited mode Topics: {topic}")

                    client.subscribe(topic)


        def on_message(client, userdata, msg):
            topic_in_msg = msg.topic
            logging.info(f"Receive data for topic: {topic_in_msg}")
            court_id = topic_in_msg.split('/')[-1]
            limited_mode = msg.payload.decode('utf-8')

            logging.info(f"Court ID: {str(court_id)}, New Limited mode: {str(limited_mode)}")
            if integrated_club:
                event = f"lights/limited_mode/{court_id}"
                data = {'message': limited_mode}
                send_data(event, data)
            else:
                event = f"lights/limited_mode/{court_id}"
                data = {'message': limited_mode}
                send_data(event, data)

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        
        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem', 
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt', 
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )
        
        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(mqtt_broker, mqtt_port, 60)
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening lights limited mode mqtt message: {e}")

#---------------------------------------------------------------------------------------------------------


def fetch_door_ids():
    try:
        # responce = requests.get(f"{back_end_url}api/doorIds?club_id={club_id}")
        logging.info('GETTING DOORS==========================')
        doors = db.getDoors(ok_cloud_access_token,back_end_url,club_id, facility_id)
        logging.info('GETTING DOOR IDs==========================')
        door_ids = [d[1] for d in doors]

        # Build stable mapping for HA door entities while keeping MQTT/backend IDs unchanged.
        # Examples: backend/MQTT 33 -> binary_sensor.puerta_1, 48 -> binary_sensor.puerta_2
        global DOOR_ENTITY_MAP, DOOR_ENTITY_REVERSE_MAP
        DOOR_ENTITY_MAP = {}
        DOOR_ENTITY_REVERSE_MAP = {}
        for index, door in enumerate(doors, start=1):
            stable_entity_id = f"puerta_{index}"
            DOOR_ENTITY_MAP[str(door[1])] = stable_entity_id
            DOOR_ENTITY_MAP[str(door[0])] = stable_entity_id
            DOOR_ENTITY_REVERSE_MAP[stable_entity_id] = str(door[1])
        

        # create doors in HA
        for index, door in enumerate(doors, start=1):
            logging.info('IN a Loop==========================')
            api_url = home_assistant_url+"/api/states/binary_sensor.{}"
            access_token = home_assistant_access_key
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            stable_door_entity_id = get_stable_door_entity_id(door[1])
            sensor_data = {
                "entity_id": stable_door_entity_id,
                "state": "off",
                "attributes": {
                    "friendly_name": door[3],
                    "device_class": "door",                
                },
            }
            
            data_from_mqtt = sensor_data['entity_id']
            logging.info('entity id form mqtt:'+str(data_from_mqtt))

            api_url_sensor = api_url.format(data_from_mqtt)
            response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

            if response4.status_code == 200:
                logging.info(f"Binary sensor {data_from_mqtt} updated successfully!") 
                
            elif response4.status_code == 201:
                logging.info(f"Binary sensor {data_from_mqtt} created successfully!") 
                
            else:
                logging.info(f"Error creating binary sensor {data_from_mqtt}: {response4.status_code} - {response4.text}")

        # listen_mqtt_doors_topics(door_ids)
        # listen_mqtt_doors_mode_topics(door_ids)


        door_state_thread = threading.Thread(target=listen_mqtt_doors_topics, args=(door_ids,))
        door_mode_thread = threading.Thread(target=listen_mqtt_doors_mode_topics, args=(door_ids,))

        # Start both threads
        door_state_thread.start()
        door_mode_thread.start()

        # Wait for both threads to finish
        door_state_thread.join()
        door_mode_thread.join()


        # if responce.status_code == 200:
            # data = responce.json()
            # door_ids = [d['id'] for d in data]
            # listen_mqtt_doors_topics(door_ids)

        # else:
        #     logging.info(f"Error while fetching resources: {responce.status_code} - {responce.text}")

    except Exception as e:
          logging.info(f"An error occurr while fetching door ids: {e}")

#---------------------------------------------------------------------------------------------------------

def listen_mqtt_doors_topics(door_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
            logging.info("Connected with result code ")
            
            for door_id in door_ids:

                    topic = f"ok_cloud/door/{club_id}/{facility_id}/{door_id}"
                    logging.info(f"Door topic: {topic}")

                    client.subscribe(topic)
                    # fetch_data_with_door_id('close',door_id)

            # # for sltek club
            # if integrated_club:
            #     for door_id in door_ids:

            #         topic = f"ok_cloud/door/{club_id}/0/{door_id}"
            #         logging.info(f"Door topic: {topic}")

            #         client.subscribe(topic)
            #         # fetch_data_with_door_id('close',door_id)
            
            # # for localclub
            # else:
            #     for door_id in door_ids:

            #         topic = f"ok_cloud/door/{club_id}/{facility_id}/{door_id}"
            #         logging.info(f"Door topic: {topic}")

            #         client.subscribe(topic)
            #         # fetch_data_with_door_id('close',door_id)

        def on_message(client, userdata, msg):
            topic_in_msg = msg.topic
            door_id = topic_in_msg.split('/')[-1]

            state = msg.payload.decode('utf-8')
            
            logging.info(f"Door:{door_id} State: {state}")
            fetch_data_with_door_id(state,door_id)
            

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem', 
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt', 
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )

        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        # logging.info('---------------------------------------------')
        # logging.info(client.username)
        # logging.info(client.password)
        # logging.info('---------------------------------------------')

        try:
            logging.info(f"mqtt_broker: {mqtt_broker}")
            logging.info(f"mqtt_port: {type(mqtt_port)}")
            client.connect(mqtt_broker, mqtt_port, 60)
        except Exception as err:
            logging.info(f"An error occurred while listening doors mqtt connect: {err}")
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening doors mqtt message: {e}")

#---------------------------------------------------------------------------------------------------------

def listen_mqtt_doors_mode_topics(door_ids):
    
    try:
        def on_connect(client, userdata, flags, rc, properties):
            logging.info("Connected with result code ")
            
            for door_id in door_ids:

                    topic = f"ok_cloud/door/automatic/{club_id}/{facility_id}/{door_id}"
                    logging.info(f"Door topic: {topic}")

                    client.subscribe(topic)           

        def on_message(client, userdata, msg):
            topic_in_msg = msg.topic
            door_id = topic_in_msg.split('/')[-1]

            mode = msg.payload.decode('utf-8')
            
            logging.info(f"Door:{door_id} Mode: {mode}")
            event = f"door/{door_id}"

            data = {'message': mode}
            send_data(event, data)
            

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        client.tls_set(
            ca_certs=f'/cert/AmazonRootCA1.pem',
            certfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-certificate.pem.crt',
            keyfile=f'/cert/e85bd3ae03a42f7c060129714775af0c8a2e9d3aa57f42a3e3ece6738b4be4e9-private.pem.key'
        )

        # client.username_pw_set(username=mqtt_user_name, password=mqtt_user_password)
        # client.tls_set(tls_version=mqtt.ssl.PROTOCOL_TLS)
        
        client.on_connect = on_connect
        client.on_message = on_message
        logging.info('---------------------------------------------')
        # logging.info(client.username)
        # logging.info(client.password)
        # logging.info('---------------------------------------------')

        try:
            logging.info(f"mqtt_broker: {mqtt_broker}")
            logging.info(f"mqtt_port: {type(mqtt_port)}")
            client.connect(mqtt_broker, mqtt_port, 60)
        except Exception as err:
            logging.info(f"An error occurred while listening doors mqtt connect: {err}")
        client.loop_forever()

    except Exception as e:
        logging.info(f"An error occurred while listening doors mqtt message: {e}")

#---------------------------------------------------------------------------------------------------------

def fetch_data_with_door_id(state,door_id):
      # Define the API endpoint and parameters  
    try:

        api_url = home_assistant_url+"/api/states/binary_sensor.{}"
        access_token = home_assistant_access_key
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        data_from_mqtt = get_stable_door_entity_id(door_id)
        logging.info('entity id form mqtt:'+str(data_from_mqtt))

        api_url_sensor = api_url.format(data_from_mqtt)

        respose_get_entity = requests.get(api_url_sensor, headers=headers)
        if respose_get_entity.status_code == 200:
            logging.info(respose_get_entity.json())
            sensor_data = {
                "entity_id": data_from_mqtt,
                "state": "off" if state == 'close' else "on",
                "attributes": {
                    "friendly_name": respose_get_entity.json()['attributes']['friendly_name'],
                    "device_class": "door",                
                },
            }
            
            
            response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

            if response4.status_code == 200:
                logging.info(f"Binary sensor {data_from_mqtt} updated successfully!") 
                
            elif response4.status_code == 201:
                logging.info(f"Binary sensor {data_from_mqtt} created successfully!") 
                
            else:
                logging.info(f"Error creating binary sensor {data_from_mqtt}: {response4.status_code} - {response4.text}")
            
    except Exception as e:
          logging.info(f"An error occurr while updating door states: {e}")

#----------------------------------------------------------------------------------------------------------------------------------------
# def updateEntityState():
#     logging.info(sys.argv[2])
#     try:
#         api_url = home_assistant_url+"/api/states/{}"
#         access_token = sys.argv[2]

#         headers = {
#                   "Authorization": f"Bearer {access_token}",
#                   "Content-Type": "application/json",
#         }
#         logging.info(access_token)

#         body = request.get_json(force=True)
#         entity_id = body.get('entity_id')
#         doorState = body.get('state')
#         name = body.get('attributes')['friendly_name']
#         device_class = body.get('attributes')['device_class']

#         logging.info('*******************************************************')
#         logging.info(entity_id)
#         logging.info(doorState)
#         logging.info(name)
#         logging.info(device_class)


#         api_url_sensor = api_url.format(entity_id)
#         response = requests.post(api_url_sensor, json=body, headers=headers)

      
#         # Check the response for each sensor
#         if response.status_code == 200:
#             if device_class == "door":
#                 logging.info(f"Binary sensor door {entity_id} updated successfully!")
#                 if doorState == "on":
#                     # time.sleep(30)

#                     try:
#                         key = 'door_open_time'
#                         door_open_time = db.getConfigurationByKey(key)
#                         logging.info(door_open_time)
#                         time.sleep(int(door_open_time))

#                     except:
#                         time.sleep(10)
#                         logging.info("Door open time is defautly 10 sec")    

#                     #turn off the door after 30s
#                     #binary sensor data and make POST requests
#                     sensor_data = {
#                         "state": "off",
#                         "entity_id": entity_id,
#                         "attributes": {
#                             "friendly_name": name,
#                             "device_class": "door",
#                         },
#                     }

#                     # logging.info(sensor_data)
                    
                    
#                     response1 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#                     # Check the response for each sensor
#                     if response1.status_code == 200:
#                         logging.info(f"Binary sensor door {entity_id} closed successfully!")
#                         finalResponse = {"result": "Successfully door updated"}
#                         return finalResponse 
#                     elif response1.status_code == 201:
#                         logging.info(f"Binary sensor door {entity_id} closed successfully!")
#                         finalResponse = {"result": "Successfully door updated"}
#                         return finalResponse     
#                     else:
#                         logging.info(f"Error creating binary sensor door {entity_id}: {response1.status_code} - {response1.text}")

#             elif device_class == "light":
#                 logging.info(f"Binary sensor light {entity_id} updated successfully!")
            
#                 #binary sensor data and make POST requests
#                 sensor_data = {
#                     "state": doorState,
#                     "entity_id": entity_id,
#                     "attributes": {
#                         "friendly_name": name,
#                         "device_class": "light",
#                     },
#                 }

#                 response1 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#                 # Check the response for each sensor
#                 if response1.status_code == 200:
#                     logging.info(f"Binary sensor light {entity_id} closed successfully!")
#                     finalResponse = {"result": "Successfully light updated"}
#                     return finalResponse 
#                 elif response1.status_code == 201:
#                     logging.info(f"Binary sensor light {entity_id} closed successfully!")
#                     finalResponse = {"result": "Successfully light updated"}
#                     return finalResponse     
#                 else:
#                     logging.info(f"Error creating binary sensor light {entity_id}: {response1.status_code} - {response1.text}")   

#         elif response.status_code == 201:
#             # logging.info(f"Binary sensor door {entity_id} created successfully!")
#             if device_class == "door":
#                 logging.info(f"Binary sensor door {entity_id} created successfully!")
#                 if doorState == "on":
#                     # time.sleep(30)

#                     try:
#                         key = 'door_open_time'
#                         door_open_time = db.getConfigurationByKey(key)
#                         logging.info(door_open_time)
#                         time.sleep(int(door_open_time))

#                     except:
#                         time.sleep(10)
#                         logging.info("Door open time is defautly 10 sec")    

#                     #turn off the door after 30s
#                     #binary sensor data and make POST requests
#                     sensor_data = {
#                         "state": "off",
#                         "entity_id": entity_id,
#                         "attributes": {
#                             "friendly_name": name,
#                             "device_class": "door",
#                         },
#                     }

#                     # logging.info(sensor_data)
                    
                    
#                     response1 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#                     # Check the response for each sensor
#                     if response1.status_code == 200:
#                         logging.info(f"Binary sensor door {entity_id} closed successfully!")
#                         finalResponse = {"result": "Successfully door created"}
#                         return finalResponse 
#                     elif response1.status_code == 201:
#                         logging.info(f"Binary sensor door {entity_id} closed successfully!")
#                         finalResponse = {"result": "Successfully door created"}
#                         return finalResponse     
#                     else:
#                         logging.info(f"Error creating binary sensor door {entity_id}: {response1.status_code} - {response1.text}")

#             elif device_class == "light":
#                 logging.info(f"Binary sensor light {entity_id} created successfully!")
            
#                 #binary sensor data and make POST requests
#                 sensor_data = {
#                     "state": doorState,
#                     "entity_id": entity_id,
#                     "attributes": {
#                         "friendly_name": name,
#                         "device_class": "light",
#                     },
#                 }

#                 response1 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#                 # Check the response for each sensor
#                 if response1.status_code == 200:
#                     logging.info(f"Binary sensor light {entity_id} closed successfully!")
#                     finalResponse = {"result": "Successfully light created"}
#                     return finalResponse 
#                 elif response1.status_code == 201:
#                     logging.info(f"Binary sensor light {entity_id} closed successfully!")
#                     finalResponse = {"result": "Successfully light created"}
#                     return finalResponse     
#                 else:
#                     logging.info(f"Error creating binary sensor light {entity_id}: {response1.status_code} - {response1.text}")    
#         else:
#             logging.info(f"Error update binary sensor door {entity_id}: {response.status_code} - {response.text}") 

#         # finalResponse = {"result": "Successfully door updated"}
#         # return finalResponse
#         # if response.status_code == 200:
#         #     logging.info(f"Binary sensor updated successfully!")
#         #     result = {"result": "Successfully light mode updated"}
#         #     return result 
#         # elif response.status_code == 201:
#         #     logging.info(f"Binary sensor updated successfully!")
#         #     result = {"result": "Successfully light mode updated"} 
#         #     return result
#         # else:
#         #     result = {"result": "Unauthoraized"} 
#         #     return result
        
#     except Exception as e:
#         return 501

def updateEntityState(club_id):
    logging.info(sys.argv[2])
    try:
        
        body = request.get_json(force=True)
        entity_id = body.get('entity_id')
        doorState = body.get('state')
        name = body.get('attributes')['friendly_name']
        device_class = body.get('attributes')['device_class']
        logging.info('Update state--------------------------------------')
        logging.info(entity_id)

        if device_class == 'light':
            id = get_original_light_id(entity_id)
            logging.info(id)

            url = f"{back_end_url}api/lights/update-light-status?clubId={club_id}"

            body = {
                "lightId": id,
                "status": doorState
            }
            
            logging.info(body)

            # Add the bearer token to the headers
            headers = {
                "Authorization": f"Bearer {ok_cloud_access_token}",
                "Content-Type": "application/json"
            }

            # Send the POST request with headers
            response = requests.post(url, json=body, headers=headers)
            if response.status_code == 200:
                message = "Success"
                return message
            else:
                message = "Faild"
                return message
            
        if device_class == 'door':
            id = get_original_door_id(entity_id)

            if doorState == 'on':
                status= True

                url = f"{back_end_url}api/doors/update-door-status?clubId={club_id}"

                body = {
                    "doorId": id,
                    "status": status
                }

                # Add the bearer token to the headers
                headers = {
                    "Authorization": f"Bearer {ok_cloud_access_token}",
                    "Content-Type": "application/json"
                }

                # Send the POST request with headers
                response = requests.post(url, json=body, headers=headers)
                if response.status_code == 200:
                    message = "Success"
                    return message
                else:
                    message = "Faild"
                    return message
            else:
                status= False

                url = f"{back_end_url}api/doors/update-door-status?clubId={club_id}"

                body = {
                    "doorId": id,
                    "status": status
                }

                # Add the bearer token to the headers
                headers = {
                    "Authorization": f"Bearer {ok_cloud_access_token}",
                    "Content-Type": "application/json"
                }

                # Send the POST request with headers
                response = requests.post(url, json=body, headers=headers)
                if response.status_code == 200:
                    message = "Success"
                    return message
                else:
                    message = "Faild"
                    return message
        
    except Exception as e:
        return 501

def getEntityState():
      
      body = request.get_json(force=True)
      entity_id = body.get('entity_id')
      logging.info(entity_id)

      try:
            api_url = home_assistant_url + "/api/states/{}"
            access_token = sys.argv[2]
            logging.info(access_token)

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            # entity_id = request.args.get('entity_id')  # Get entity_id from query parameters

            api_url_sensor = api_url.format(entity_id)
            response = requests.get(api_url_sensor, headers=headers)

            logging.info(response)
            result = response.json()
            return result

      except Exception as e:
        return {"Error": str(e)}, 501
      
def getDoorState():
      
      body = request.get_json(force=True)
      entity_id = body.get('entity_id')
      logging.info(entity_id)

      try:
            api_url = home_assistant_url + "/api/states/binary_sensor.{}"
            access_token = sys.argv[2]

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            # entity_id = request.args.get('entity_id')  # Get entity_id from query parameters

            api_url_sensor = api_url.format(entity_id)
            response = requests.get(api_url_sensor, headers=headers)

            if response.status_code == 200:
                logging.info(response)
                result = response.json()
                return result
            
            else:
                logging.info(response)
                result = response.json()
                return result

      except Exception as e:
        return {"Error": str(e)}, 501
      
def getDoorStateByEntityId(entity_id):
      
      logging.info(entity_id)

      try:
            api_url = home_assistant_url + "/api/states/binary_sensor.{}"
            access_token = sys.argv[2]

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            # entity_id = request.args.get('entity_id')  # Get entity_id from query parameters

            api_url_sensor = api_url.format(entity_id)
            response = requests.get(api_url_sensor, headers=headers)

            if response.status_code == 200:
                logging.info(response)
                result = response.json()
                return result
            
            else:
                logging.info(response)
                result = response.json()
                logging.info(response)

                raise

      except Exception as e:
        return {"Error": str(e)}, 501      

#Update light table-----------------------------------------------------------------------------------------------------------------------
def updateLightsTable(entity_id, name):

    light = db.getLightByEntityId(entity_id)
    logging.info(light)
    logging.info(entity_id)
    
    if not light:
        db.addLight(str(uuid.uuid4()), entity_id, name)
        logging.info('INSERT')
    else:
        # if()
        db.updateLightsName(entity_id,name)
        logging.info('UPDATE')


#Syltek Integration-----------------------------------------------------------------------------------------------------------------------
# def fetch_data_with_light_id(Tenant, apikey, resources_id, data, resources_genaration_url, sessionID):
#       # Define the API endpoint and parameters
#       params = {'IgnoreSunTime': checkIgnoreSunLight(), 'UseExtrasPeriods': checkUseExtraPeriods(), 'apiKey': apikey, 'IdResources':resources_id}
#       logging.info('In fetch_data_with_light_id() function')
#       try:
#           # Replace with the actual API endpoint URL
#           light_state_url = 'https://'+Tenant+'.syltek.com/hermes/api/v1/Lights/activeGrouped?'

#           # Make a GET request to the API with the specified parameters
#           response5 = requests.get(light_state_url, params=params)

#           # Check if the request was successful (status code 200)
#           if response5.status_code == 200:  
#               light_state = response5.json()
#               logging.info(light_state)

#               # Home Assistant API endpoint for creating or updating a state
#               api_url = home_assistant_url+"/api/states/binary_sensor.{}"

#               # Replace with your Home Assistant access token
#               access_token = home_assistant_access_key

#               # Headers for the request
#               headers = {
#                   "Authorization": f"Bearer {access_token}",
#                   "Content-Type": "application/json",
#               }
#               filtered_list = [item for item in data if item['idResourceType'] in [56, 57]]             

#               # Iterate through binary sensors data and make POST requests
#               for item in filtered_list:
#                   sensor_data = {
#                       "entity_id": item['id'],
#                       "state": "off" if light_state[str(item['id'])] == False else "on",
#                       "attributes": {
#                           "friendly_name": item['name'],
#                           "device_class": "light",                
#                       },
#                   }
                  
#                   data_from_slytek = sensor_data['entity_id']
#                   logging.info('entity id form Slytek:'+str(data_from_slytek))

#                   if(db.getLightByEntityId(data_from_slytek) == None):
                      
                      
#                       logging.info('Not in Our DB')
#                      #   Add to HA
                      
#                       api_url_sensor = api_url.format(data_from_slytek)
#                       response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#                       if response4.status_code == 200:
#                             logging.info(f"Binary sensor {data_from_slytek} updated successfully!")    
#                       elif response4.status_code == 201:
#                             logging.info(f"Binary sensor {data_from_slytek} created successfully!") 
#                       else:
#                             logging.info(f"Error creating binary sensor {data_from_slytek}: {response4.status_code} - {response4.text}")

#                      #   Add to DB
#                       updateLightsTable(data_from_slytek,item['name'])
                      

#                   else:
#                         logging.info('In Our DB')
#                         light = db.getLightByEntityId(data_from_slytek)
#                         light_mode = light[2]
#                         logging.info(light_mode)

#                         if light_mode == (1):
#                             logging.info(data_from_slytek)
#                             # Update DB
                            
#                             updateLightsTable(data_from_slytek,item['name'])

#                             # Update HA
#                             api_url_sensor = api_url.format(data_from_slytek)
#                             response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#                             if response4.status_code == 200:
#                                 logging.info(f"Binary sensor {data_from_slytek} updated successfully!")    
#                             elif response4.status_code == 201:
#                                 logging.info(f"Binary sensor {data_from_slytek} created successfully!") 
#                             else:
#                                 logging.info(f"Error creating binary sensor {data_from_slytek}: {response4.status_code} - {response4.text}")
#                         else:
#                             logging.info('Manual: Cant Change the state of the light')

#               time.sleep(60)
#             #   fetch_data_with_resources(Tenant, resources_genaration_url, sessionID, apikey)
#             #   fetch_data_with_light_id(Tenant, apikey, resources_id, data, resources_genaration_url, sessionID)   

#           else:
#               # logging.info an error message if the request was not successful
#               logging.info(f"Error5: {response5.status_code} - {response5.text}")
#       except Exception as e:
#           logging.info(f"An error occurr while updating light states: {e}")

# def update_door_state(idTerminal, doorState):
#       # Home Assistant API endpoint for creating or updating a state
#       door_entity = 'door'+idTerminal
#       api_url = home_assistant_url+"/api/states/binary_sensor."+door_entity
      
#       # Replace with your Home Assistant access token
#       access_token = home_assistant_access_key

#       # Headers for the request
#       headers = {
#           "Authorization": f"Bearer {access_token}",
#           "Content-Type": "application/json",
#       }

#       #binary sensor data and make POST requests
      
#       #Name Doors
#     #   door_name = args.get('door'+str(idTerminal)+'_name')
#     #   if not door_name:
#       doors_in_db = db.getDoorByEntityId(door_entity)

    
#       logging.info('+++++++++++++++++++++++++++++++++++')
#       logging.info(doors_in_db)
#       door_name = doors_in_db[3]
    

#       sensor_data = {
#           "entity_id": door_entity,
#           "state": "on" if doorState == 1 else "off",
#           "unique_id": idTerminal,
#           "attributes": {
#               "friendly_name": door_name,
#               "device_class": "door",
#               "unique_id": idTerminal,
          
#           },
#       }

#       logging.info(sensor_data)
#       entity_id = sensor_data["entity_id"]
#       api_url_sensor = api_url
#       response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#       # Check the response for each sensor
#       if response4.status_code == 200:
#           logging.info(f"Binary sensor door {entity_id} updated successfully!")
#           if doorState == 1:
#             # time.sleep(30)
#             try:
#                 key = 'door_open_time'
#                 door_open_time = db.getConfigurationByKey(key)
#                 logging.info("Door open time: {}".format(door_open_time))
#                 time.sleep(int(door_open_time))

#             except:
#                 time.sleep(10)
#                 logging.info("Door open time is defautly 10 sec")

#             #turn off the door after 30s
#             #binary sensor data and make POST requests
#             sensor_data = {
#                 "state": "off",
#                 "entity_id": door_entity,
#                 "unique_id": idTerminal,
#                 "attributes": {
#                     "friendly_name": door_name,
#                     "device_class": "door",
#                     "unique_id": idTerminal,
#                 },
#             }

#             # logging.info(sensor_data)
#             entity_id = door_entity
#             api_url_sensor = api_url
#             response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#             # Check the response for each sensor
#             if response4.status_code == 200:
#                 logging.info(f"Binary sensor door {entity_id} updated successfully!")
#             elif response4.status_code == 201:
#                 logging.info(f"Binary sensor door {entity_id} created successfully!")    
#             else:
#                 logging.info(f"Error creating binary sensor door {entity_id}: {response4.status_code} - {response4.text}")

#       elif response4.status_code == 201:
#           logging.info(f"Binary sensor door {entity_id} created successfully!")
#           if doorState == 1:
#             # time.sleep(30)
#             try:
#                 key = 'door_open_time'
#                 door_open_time = db.getConfigurationByKey(key)
#                 logging.info(door_open_time)
#                 time.sleep(int(door_open_time))

#             except:
#                 time.sleep(10)
#                 logging.info("Door open time is defautly 10 sec")

#             #turn off the door after 30s
#             #binary sensor data and make POST requests
#             sensor_data = {
#                 "state": "off",
#                 "entity_id": door_entity,
#                 "unique_id": idTerminal,
#                 "attributes": {
#                     "friendly_name": door_name,
#                     "device_class": "door",
#                     "unique_id": idTerminal,
#                 },
#             }

#             # logging.info(sensor_data)
#             entity_id = door_entity
#             api_url_sensor = api_url
#             response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

#             # Check the response for each sensor
#             if response4.status_code == 200:
#                 logging.info(f"Binary sensor door {entity_id} updated successfully!")
#             elif response4.status_code == 201:
#                 logging.info(f"Binary sensor door {entity_id} created successfully!")    
#             else:
#                 logging.info(f"Error creating binary sensor door {entity_id}: {response4.status_code} - {response4.text}")    
#       else:
#           logging.info(f"Error creating binary sensor door {entity_id}: {response4.status_code} - {response4.text}") 

# def create_doors_in_ha_from_db():
#     doors_in_db = getDoorsForDB()
 
#     for tup in doors_in_db:
#         door_entity_id_in_db = tup[2]
#         door_name_in_db = tup[3]

#         logging.info(door_entity_id_in_db)
#         logging.info(door_name_in_db)

#         # Home Assistant API endpoint for creating or updating a state
#         door_entity = door_entity_id_in_db
#         logging.info(door_entity)
#         api_url = home_assistant_url+"/api/states/binary_sensor."+ door_entity
        
#         # Replace with your Home Assistant access token
#         access_token = home_assistant_access_key

#         # Headers for the request
#         headers = {
#             "Authorization": f"Bearer {access_token}",
#             "Content-Type": "application/json",
#         }

#         #binary sensor data and make POST requests
#         door_name = door_name_in_db

#         sensor_data = {
#             "entity_id": door_entity,
#             "state": "off" ,
#             "unique_id": door_entity_id_in_db,
#             "attributes": {
#                 "friendly_name": door_name,
#                 "device_class": "door",
#                 "unique_id": door_entity_id_in_db,
            
#             },
#         }
#         api_url_sensor = api_url
#         response = requests.post(api_url_sensor, json=sensor_data, headers=headers)
        
#         logging.info(response)
        
#         # Check the response for each sensor
#         if response.status_code == 200:
#             logging.info(f"Binary sensor door {door_entity_id_in_db} updated successfully!")
#         elif response.status_code == 201:
#           logging.info(f"Binary sensor door {door_entity_id_in_db} created successfully!")
#         else:
#           logging.info(f"Error creating binary sensor door {door_entity_id_in_db}: {response.status_code} - {response.text}") 

# def addDoorToHa(entity_id,state,name):
#     door_entity = entity_id
#     logging.info(door_entity)
#     api_url = home_assistant_url+"/api/states/binary_sensor."+ door_entity
    
#     # Replace with your Home Assistant access token
#     access_token = sys.argv[2]

#     # access_token = home_assistant_access_key

#     # Headers for the request
#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json",
#     }

#     #binary sensor data and make POST requests
    

#     sensor_data = {
#         "entity_id": door_entity,
#         "state": state ,
#         "unique_id": entity_id,
#         "attributes": { 
#             "friendly_name": name,
#             "device_class": "door",
#         },
#     }
#     api_url_sensor = api_url
#     response = requests.post(api_url_sensor, json=sensor_data, headers=headers)
#     logging.info(response)
#     # Check the response for each sensor
#     if response.status_code == 200:
#         logging.info(f"Binary sensor door {entity_id} updated successfully!")
#     elif response.status_code == 201:
#         logging.info(f"Binary sensor door {entity_id} created successfully!")
#     else:
#         logging.info(f"Error creating binary sensor door {entity_id}: {response.status_code} - {response.text}") 

def deleteDoorFromHa(entity_id):
    door_entity = entity_id
    logging.info(door_entity)
    api_url = home_assistant_url+"/api/states/binary_sensor."+ door_entity
    
   
    # Replace with your Home Assistant access token
    access_token = sys.argv[2]

    # Headers for the request
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    api_url_sensor = api_url
    response = requests.delete(api_url_sensor, headers=headers)
    
    if response.status_code == 200: 
        logging.info('Deleted')
        logging.info(response.json())
    else:
        raise
  
# def validate_terminal(cardCode, idTerminal, Tenant):
#       params = {'cardCode': cardCode, 'idTerminal': idTerminal}
#       validate_terminalurl = 'https://'+Tenant+'.syltek.com/api/validateterminal?'
      
#       try:
#           # Make a GET request to the API with the specified parameters
#           responseTerminal = requests.get(validate_terminalurl, params=params)

#           # Check if the request was successful (status code 200)
#           if responseTerminal.status_code == 200:
#             logging.info("Terminale Validate Responce :{}".format(responseTerminal.text))
#             doorState = int(responseTerminal.text.split(';')[0])
#             logging.info("Door State",doorState)
#             logging.info("Running update_door_state")

#             if doorState == 1:
#                 update_door_state(str(idTerminal),doorState)
#             else:
#                 logging.info("Door not exists")

#           else:
#               # logging.info an error message if the request was not successful
#               logging.info(f"Error while validate terminal: {responseTerminal.status_code} - {responseTerminal.text}")
      
#       except Exception as e:
#           logging.info(f"An error occurr while validate terminal: {e}")

# def fetch_data_with_resources(Tenant, resources_genaration_url, sessionID, apikey):
#       # Define the API endpoint and parameters
#       params = {'idsession': sessionID}

#       try:
#           # Make a GET request to the API with the specified parameters
#           response3 = requests.get(resources_genaration_url, params=params)

#           # Check if the request was successful (status code 200)
#           if response3.status_code == 200:
#               # Parse and logging.info the response data (you may want to modify this based on the API response format)
#               data = response3.json()
#               logging.info("API Response 3:")
#               logging.info(data)

#               filtered_list = [item for item in data if item['idResourceType'] in [56, 57]]
#               id_array = [str(item['id']) for item in filtered_list]
#               id_string = ','.join(id_array)
#               resources_id = id_string
             

#               # Call the function to fetch data from the API
#               fetch_data_with_light_id(Tenant, apikey, resources_id, data, resources_genaration_url, sessionID,)

#           else:
#               # logging.info an error message if the request was not successful
#               logging.info(f"Error while fetching resources: {response3.status_code} - {response3.text}")

#       except Exception as e:
#           logging.info(f"An error occurr while fetching resources: {e}")

# def fetch_data_with_sessionid(Tenant, sessionID_genaration_url, apikey):
#       # Define the API endpoint and parameters
#       params = {'apikey': apikey}
      
#       try:
#           # Make a GET request to the API with the specified parameters
#           response2 = requests.get(sessionID_genaration_url, params=params)

#           # Check if the request was successful (status code 200)
#           if response2.status_code == 200:
#               # Parse and logging.info the response data (you may want to modify this based on the API response format)
#               data = response2.json()
#               logging.info("API Response 2:")
#               logging.info(data)

#               # Access the "sessionId" object in the JSON response and assign it to a new variable called "SessionID"
#               SessionID = data.get('sessionId')
#               logging.info("Session ID: {}".format(SessionID))
              

#               # Replace the actual API endpoint URL
#               resources_genaration_url = 'https://'+Tenant+'.syltek.com/api/Resources?'

#               # Replace 'sessionID' with the actual SessionID parameter value
#               sessionID = SessionID

#               # Call the function to fetch data from the API
#               fetch_data_with_resources(Tenant, resources_genaration_url, sessionID, apikey)
#           else:
#               # logging.info an error message if the request was not successful
#               logging.info(f"Error while fetching session id: {response2.status_code} - {response2.text}")
      
#       except Exception as e:
#           logging.info(f"An error occurr while fetching session id: {e}")

# def fetch_data_with_uuid(api_genaration_url, club_uuid):
#       # Define the API endpoint and parameters
#       params = {'UUID': club_uuid}
      
#       try:
#           # Make a GET request to the API with the specified parameters
#           response1 = requests.get(api_genaration_url, params=params)

#           # Check if the request was successful (status code 200)
#           if response1.status_code == 200:
#               # Parse and logging.info the response data (you may want to modify this based on the API response format)
#               data = response1.json()
#               logging.info("API Response 1:")
#               # logging.info(data)

#               # Access the "apiKey" and "tenant" object in the JSON response and assign it to a new variable called "ApiKey" and "Tenant"
#               ApiKey = data.get('apiKey')
#               Tenant = data.get('tenant')
#               global global_tenant 
#               global_tenant = Tenant
#               logging.info("Api Key: {}\nTenant: {}\n".format(ApiKey,Tenant))

#               # Replace 'your_sessionID_genaration_url_here' with the actual API endpoint URL
#               sessionID_genaration_url = 'https://'+Tenant+'.syltek.com/api/newsession?'
            
#               # Replace 'apikey' with the actual ApiKey parameter value
#               apikey = ApiKey
            
#               #Connect to Mqtt Broker
#             #   def on_connect(client, userdata, flags, rc):
#             #       logging.info(f"Connected with result code {mqtt.connack_string(rc)}")

#             #   #Get Payload
#             #   def on_message(client, userdata, msg):
#             #       result = msg.payload.decode('utf-8').replace('"', '').split()
#             #       logging.info(f"Door Result: {result}")
#             #       cardCode = result[1]
#             #       logging.info("code: {}".format(cardCode))
#             #       idTerminal = int(result[3])
#             #       logging.info("door: {}".format(idTerminal))

#             #       configuations = db.getConfiguration()
                  
#             #       managerCode = ""
#             #       eventDayCode = ""
#             #       for config in configuations:
#             #           if config[1] == 'manager_code':
#             #               managerCode = config[2]
#             #           if config[1] == 'event_day_code':
#             #               eventDayCode = config[2]
                          
#             #       logging.info("Manager Code:"+managerCode+", Event Day Code:"+eventDayCode)
#             #       logging.info(db.getDoorByDoorId(idTerminal))
#             #       doorMode = db.getDoorByDoorId(idTerminal)[4]

#             #       if(db.getDoorByDoorId(idTerminal)[1] == None):
#             #           logging.info('No door found')
#             #       else:
#             #           if doorMode == 0:
#             #             logging.info('Door mode is Manual: Cant change the state of the door')
#             #           else:
#             #               if (managerCode==cardCode or eventDayCode==cardCode):
#             #                   logging.info('Manager code or Event Code detected: Door is modified')
#             #                   doorState = 1
#             #                   update_door_state(str(idTerminal),doorState)
#             #               else:
#             #                   logging.info('Send request for validation')
#             #                   validate_terminal(cardCode,idTerminal,Tenant)

#             #     #   validate_terminal(cardCode,idTerminal,Tenant)  

#             #   # Create an MQTT client instance
#             #   client = mqtt.Client(clean_session=True)
              
#             #   # Set the TLS/SSL options
#             #   client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)

#             #   # # Set the callbacks
#             #   client.on_connect = on_connect
#             #   client.on_message = on_message

#             #   # Set the username and password (if required by your broker)
#             #   if (mqtt_user_name and mqtt_user_password):
#             #     client.username_pw_set(mqtt_user_name, mqtt_user_password)

#             #   try:
#             #     # Connect to the broker
#             #     logging.info(f"Connecting mqtt broker: {mqtt_broker}")
#             #     logging.info(f"MQTT Port: {int(mqtt_port)}")
#             #     client.connect(mqtt_broker, port=int(mqtt_port))
#             #   except Exception as ce:
#             #     logging.info(f"An error occurre while mqtt connection: {ce}")

#             #   client.subscribe(global_tenant, qos=2)
#             #    # Start the MQTT loop 
              
#             #   client.loop_start()
              
#               # Call the function to fetch data from the API
#               fetch_data_with_sessionid(Tenant, sessionID_genaration_url, apikey)
#           else:
#               # logging.info an error message if the request was not successful
#               logging.info(f"Error while fetching API: Invalid UUID")
      
#       except Exception as e:
#           logging.info(f"An error occurre while getting api key: {e}")
 
def clear_all_entities():
    logging.info("home_assistant_access_key in clearing function: {}".format(home_assistant_access_key))
    try:
      # Replace with your Home Assistant access token
      access_token = home_assistant_access_key

      # Headers for the request
      headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
      }
      response6 = requests.get(home_assistant_url+'/api/states',headers=headers)      
      data = response6.json()
      filtered_list = [item for item in data if 'binary_sensor' in item['entity_id']]
      
      for item in filtered_list:
        filtered_list_entity_id = item['entity_id']
        logging.info(filtered_list_entity_id)

        response7=requests.delete(home_assistant_url+'/api/states/'+filtered_list_entity_id,headers=headers)
        logging.info(response7.json())

        # delete lights from local DB
        light_entity_id_fro_delete = filtered_list_entity_id.replace("binary_sensor.", "")
        logging.info(light_entity_id_fro_delete)

        # db.deleteLight()
        logging.info(light_entity_id_fro_delete+' light deleted from local DB')

    except Exception as e:
        logging.info(f"An error occurred: {e}")

# def mqtt_process():
#     logging.info('mqtt_process function starts')


#     def on_connect(client, userdata, flags, rc):
#         logging.info(f"Connected with result code {mqtt.connack_string(rc)}")
#         logging.info(client)
#         logging.info(userdata)
#         logging.info(flags)

        
#     params = {'UUID': club_uuid}
      
#     try:
#         # Make a GET request to the API with the specified parameters
#         response1 = requests.get(api_genaration_url, params=params)

#         # Check if the request was successful (status code 200)
#         if response1.status_code == 200:
#             # Parse and logging.info the response data (you may want to modify this based on the API response format)
#             data = response1.json()
#             Tenant = data.get('tenant')
#     except Exception as e:
#           logging.info(f"An error occurre while getting tenant : {e}")

#     logging.info(Tenant)


#     #Get Payload
#     def on_message(client, userdata, msg):
#         result = msg.payload.decode('utf-8').replace('"', '').split()
#         logging.info(f"Door Result: {result}")
#         cardCode = result[1]
#         logging.info("code: {}".format(cardCode))
#         idTerminal = int(result[3])
        
#         logging.info("door: {}".format(idTerminal))

#         configuations = db.getConfiguration()
        
#         managerCode = ""
#         eventDayCode = ""
#         for config in configuations:
#             if config[1] == 'manager_code':
#                 managerCode = config[2]
#             if config[1] == 'event_day_code':
#                 eventDayCode = config[2]
                
#         logging.info("Manager Code:"+managerCode+", Event Day Code:"+eventDayCode)
#         logging.info(db.getDoorByDoorId(idTerminal))

#         try:
#             doorMode = db.getDoorByDoorId(idTerminal)[4]
#         except:
#             logging.info("Door not exists")

#         try:
#             db.getDoorByDoorId(idTerminal)[1] == None
#             if doorMode == 0:
#                 logging.info('Door mode is Manual: Cant change the state of the door')
#             else:
#                 if (managerCode==cardCode or eventDayCode==cardCode):
#                     logging.info('Manager code or Event Code detected: Door is modified')
#                     doorState = 1
#                     # update_door_state(str(idTerminal),doorState)

                    
#                     t4 = threading.Thread(target=update_door_state_thread, args=(idTerminal, doorState, ), name='t4',daemon = True)
#                     t4.start()


#                 else:
#                     logging.info('Send request for validation')
#                     # validate_terminal(cardCode,idTerminal,Tenant)

#                     t3 = threading.Thread(target=terminale_validate_thread, args=(cardCode, idTerminal, Tenant, ), name='t3',daemon = True)
#                     t3.start()
#         except:
#             logging.info('Door not exists')


#     #   validate_terminal(cardCode,idTerminal,Tenant)  


#     # client_name = "ha_{}".format(str(uuid.getnode()))
#     # logging.info(client_name)

#     # Create an MQTT client instance
#     client = mqtt.Client(clean_session=True)
    
#     # Set the TLS/SSL options
#     client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)

#     # # Set the callbacks
#     client.on_connect = on_connect
#     client.on_message = on_message

#     # Set the username and password (if required by your broker)
#     if (mqtt_user_name and mqtt_user_password):
#         client.username_pw_set(mqtt_user_name, mqtt_user_password)

#     try:
#         # Connect to the broker
#         logging.info(f"Connecting mqtt broker: {mqtt_broker}")
#         logging.info(f"MQTT Port: {int(mqtt_port)}")
#         client.connect(mqtt_broker, port=int(mqtt_port))
#     except Exception as ce:
#         logging.info(f"An error occurre while mqtt connection: {ce}")

#     client.subscribe(Tenant, qos=2)
#     # Start the MQTT loop 
    
#     client.loop_start()
    

#Multithreading-----------------------------------------------------------------------------------------------------------------------

# def slytekIntergration():
#     try:
#         while True:
#             logging.info("Task 1 assigned to thread: {}".format(threading.current_thread().name))
            
#             fetch_data_with_uuid(api_genaration_url, club_uuid)
#             time.sleep(1)
#     except KeyboardInterrupt:
#         logging.info("Thread received Ctrl+C, exiting gracefully.")

# def mqtt_process_thread():

#     try:
#         # while True:
#             logging.info('MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM')

#             logging.info("Task 2 assigned to thread: {}".format(threading.current_thread().name))
#             mqtt_process()
#             time.sleep(1)
#     except KeyboardInterrupt:
#         logging.info("Thread received Ctrl+C, exiting gracefully.")

# def terminale_validate_thread(cardCode, idTerminal, Tenant):
#     try:
#         # while True:
#             logging.info('Validate Terminal')

#             logging.info("Task 3 assigned to thread: {}".format(threading.current_thread().name))
#             validate_terminal(cardCode, idTerminal, Tenant)
#             time.sleep(1)
#     except KeyboardInterrupt:
#         logging.info("Thread received Ctrl+C, exiting gracefully.")

# def update_door_state_thread(idTerminal, doorState):
#     try:
#         # while True:
#             logging.info('Update door state')

#             logging.info("Task 4 assigned to thread: {}".format(threading.current_thread().name))
#             update_door_state(str(idTerminal),doorState)
#             time.sleep(1)
#     except KeyboardInterrupt:
#         logging.info("Thread received Ctrl+C, exiting gracefully.")
            
def signal_handler(signal, frame):
    logging.info("Exiting program.")
    sys.exit(0)

#Main--------------------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
     
    logging.info(club_uuid)
    logging.info(home_assistant_access_key)
    # logging.info(mqtt_user_name)
    # logging.info(mqtt_user_password)
    logging.info(mqtt_broker)
    logging.info(mqtt_port)
    if(len(sys.argv)>1): 
        club_uuid = sys.argv[1]
        if(len(sys.argv)>2):
            home_assistant_access_key = sys.argv[2]
            if(len(sys.argv)>3):
                mqtt_broker = sys.argv[3]
                if(len(sys.argv)>4):
                    mqtt_port = int(sys.argv[4])

                    if(len(sys.argv)>5):
                        club_name = sys.argv[5]                   
                    if(len(sys.argv)>6):
                        ok_cloud_access_token = sys.argv[6]

                        if(len(sys.argv)>7):
                            back_end_url = sys.argv[7]
                            if(len(sys.argv)>8):
                                club_id = sys.argv[8]

                                if(len(sys.argv)>9):
                                    facility_id = sys.argv[9]

                                    if(len(sys.argv)>10):
                                        integrated_club = sys.argv[10] == 'true'

                                        if(len(sys.argv)>11):
                                            integrated_club_type = sys.argv[11]
                                            # if(len(sys.argv)>12):
                                            #     mqtt_user_name = sys.argv[12]
                                            # else:
                                            #     logging.info('Exit: MQTT username not found')
                                            # if(len(sys.argv)>13):
                                            #     mqtt_user_password = sys.argv[13]
                                            # else:
                                            #     logging.info('Exit: MQTT password not found')
                                                
                                            logging.info("==============================")
                                            logging.info(integrated_club_type)
                                            logging.info("==============================")


                                            createTables()
                                            clear_all_entities()    
                                            # create_doors_in_ha_from_db()
                                            # t1 = threading.Thread(target=slytekIntergration, name='t1',daemon = True)
                                            # t2 = threading.Thread(target=mqtt_process_thread, name='t2',daemon = True)

                                            websocket_thread = Thread(target=start_websocket_server)
                                            websocket_thread.start()

                                            # socketIO_thread = Thread(target=start_socketio)
                                            # socketIO_thread.start()

                                            t1 = threading.Thread(target=fetch_court_ids)
                                            t1.daemon = True
                                            t2 = threading.Thread(target=fetch_door_ids)
                                            t2.daemon = True

                                            t1.start()
                                            t2.start()
                                            # app.run(debug=True, host="0.0.0.0", use_reloader=False)
                                            socketio.run(app, debug=True, host='0.0.0.0', use_reloader=False, allow_unsafe_werkzeug=True)

                                            t1.join()
                                            t2.join()

                                            # t1.start()
                                            # t2.start()

                                            # t1.join()
                                            # t2.join()
                                        else:
                                            logging.info('Exit: integrated mode not found')

                                    else:
                                        logging.info('Exit: integrated state not found')
                                else:
                                    logging.info('Exit: Facility ID not found')

                            else:
                                logging.info('Exit: Club ID not found')
                        else:
                            logging.info('Exit: Backend URL not found')
                    else:
                        logging.info('Exit: OK Cloud Access Token not found')

                      
                else:
                    logging.info('Exit: MQTT Port not found')
            else:
                logging.info('Exit: MQTT Broker not found')
        else:
            logging.info('Exit: HA Token not found')
    else:
        logging.info('Exit: UUID not found')
    
