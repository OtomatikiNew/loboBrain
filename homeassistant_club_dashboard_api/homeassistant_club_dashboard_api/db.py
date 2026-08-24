import logging
import sqlite3
import requests
import json

# db_path = "/dashboard.db"
db_path = "/config/dashboard.db"


def createTables():
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()

        query1 = "CREATE TABLE IF NOT EXISTS lights (id INTEGER, entity_id TEXT, automatic_mode INTEGER, name TEXT)"
        result1 = cursor.execute(query1)

        query2 = "CREATE TABLE IF NOT EXISTS doors (id INTEGER, door_id INTEGER, entity_id TEXT, friendly_name TEXT, automatic_mode INTEGER)"
        result2 = cursor.execute(query2)

        query3 = "CREATE TABLE IF NOT EXISTS configuration (id INTEGER, key TEXT, value TEXT)"
        result3 = cursor.execute(query3)
        
        try:
            cursor.execute("ALTER TABLE lights ADD COLUMN min_level INTEGER DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise

        try:
            cursor.execute("ALTER TABLE lights ADD COLUMN max_level INTEGER DEFAULT 100")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        
        try:
            cursor.execute("ALTER TABLE lights ADD COLUMN limited_option INTEGER DEFAULT 0")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                raise
        
        conn.close()
        # return result
    except Exception as e:
        return e

# def getDoors():
#     try:
#         conn = sqlite3.connect(db_path, isolation_level=None)
#         cursor = conn.cursor()
#         query = "SELECT * FROM doors"
#         doors_data = cursor.execute(query).fetchall()
#         conn.close()
#         return doors_data

#     except Exception as e:
#         return e

def getDoors(ok_cloud_access_token,back_end_url,club_id, facility_id):
    logging.info(ok_cloud_access_token)
    try:
        # Assuming ok_cloud_access_token is your bearer token
        headers = {
            'Authorization': f'Bearer {ok_cloud_access_token}'
        }
        
        # get doors with club_id, facility_id
        response = requests.get(f"{back_end_url}api/get-doors-with-facility/{club_id}/{facility_id}", headers=headers)
        logging.info('|||||||||||||||||||||||||||||||||')
        logging.info(response.json())
        logging.info('|||||||||||||||||||||||||||||||||')

        doors_data = []
    
        for entry in response.json():
            if entry["terminal_id"]:
                door_id = str(entry["id"])
                terminal_id = entry["terminal_id"]
                door_name = "door" + str(entry["id"])
                friendly_name = entry["friendly_name"]
                automatic_mode = entry["automatic_mode"]
                formatted_entry = [door_id, door_id, door_name, friendly_name, automatic_mode]
                
                # door_id = str(entry["id"])
                # terminal_id = entry["terminal_id"]
                # door_name = "door" + str(entry["terminal_id"])
                # friendly_name = entry["friendly_name"]
                # automatic_mode = entry["automatic_mode"]
                
                # formatted_entry = [terminal_id, door_id, door_name, friendly_name, automatic_mode]
                doors_data.append(formatted_entry)
            else:
                door_id = str(entry["id"])
                terminal_id = entry["id"]
                door_name = "door" + str(entry["id"])
                friendly_name = entry["friendly_name"]
                automatic_mode = entry["automatic_mode"]
                
                formatted_entry = [terminal_id, door_id, door_name, friendly_name, automatic_mode]
                doors_data.append(formatted_entry)

        return doors_data

    except Exception as e:
        logging.info("Error in fetchimg doors from ok cloud")
        return str(e)



# def getLights():
#     try:
#         conn = sqlite3.connect(db_path, isolation_level=None)
#         cursor = conn.cursor()
#         query = "SELECT * FROM lights"
#         lights_data = cursor.execute(query).fetchall()
#         conn.close()
#         return lights_data

#     except Exception as e:
#         return e

def getLights(ok_cloud_access_token,back_end_url,club_uuid, club_id, facility_id,integrated_club, integrated_club_type):
    try:
        headers = {
            'Authorization': f'Bearer {ok_cloud_access_token}'
        }

        # get lights with uuid
        if integrated_club:
            if integrated_club_type  == "syltek":
                response = requests.get(f"{back_end_url}api/get-lights-with-uuid/{club_uuid}",headers=headers)
            elif integrated_club_type  == "playtomic":
                response = requests.get(f"{back_end_url}api/get-lights-with-playtomic-club-id/{club_id}",headers=headers)
            elif integrated_club_type  == "taykus":
                response = requests.get(f"{back_end_url}api/get-lights-with-taykus-club-id/{club_id}",headers=headers)

            # access_token = ok_cloud_access_token

            lights_data = []
            logging.info('GOT LIGHTs from OK ==========================')
            logging.info(response.json())
            logging.info('GOT LIGHTs from OK ==========================')

            for item in response.json():
                if 'entity_id' in item:
                    lights_data.append([
                        str(item['id']),
                        item['entity_id'],
                        item['automatic_mode'],
                        item['name'],
                        item['status'],
                        item.get('min_level', 0),
                        item.get('max_level', 100),
                        item.get('limited_option', False),
                    ])
                else:
                    if integrated_club_type  == "playtomic":
                        lights_data.append([
                            str(item['id']),
                            item['id'],
                            item['automatic_mode'],
                            item['name'],
                            item['status'],
                            item.get('min_level', 0),
                            item.get('max_level', 100),
                            item.get('limited_option', False),
                        ])
                    else:
                        lights_data.append([
                            str(item['id']),
                            item['court_id'],
                            item['automatic_mode'],
                            item['name'],
                            item['status'],
                            item.get('min_level', 0),
                            item.get('max_level', 100),
                            item.get('limited_option', False),
                    ])

            return lights_data
        
        # get local courts with club_id and facility id
        else:
            response = requests.get(f"{back_end_url}api/get-courts-with-facility/{club_id}/{facility_id}",headers=headers)
            # access_token = ok_cloud_access_token

            lights_data = []
            logging.info(response.json())
            logging.info('GOT LIGHTs from OK CLOD==========================')

            for item in response.json():
                if 'entity_id' in item:
                    lights_data.append([
                        str(item['id']),
                        item['entity_id'],
                        item['automatic_mode'],
                        item['name'],
                        item['status'],
                        item.get('min_level', 0),
                        item.get('max_level', 100),
                        item.get('limited_option', False),
                    ])
                else:
                    lights_data.append([
                        str(item['id']),
                        item['id'],
                        item['automatic_mode'],
                        item['name'],
                        item['status'],
                        item.get('min_level', 0),
                        item.get('max_level', 100),
                        item.get('limited_option', False),
                    ])

            return lights_data

    except Exception as e:
        logging.info(f"Error in getting lights from OK Cloud: {e}")
        return e
        

def getLightByEntityId(entity_id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "SELECT * FROM lights WHERE entity_id = '{}'".format(entity_id)
        lights_data = cursor.execute(query).fetchone()
        conn.close()
        return lights_data

    except Exception as e:
        return e
    
def getDoorByEntityId(entity_id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "SELECT * FROM doors WHERE entity_id = '{}'".format(entity_id)
        doors_data = cursor.execute(query).fetchone()
        conn.close()
        return doors_data

    except Exception as e:
        return e
    
def getDoorByDoorId(door_id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "SELECT * FROM doors WHERE door_id = '{}'".format(door_id)
        door_data = cursor.execute(query).fetchone()
        conn.close()
        return door_data

    except Exception as e:
        return e  

def getDoorById(id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "SELECT * FROM doors WHERE id = '{}'".format(id)
        door_data = cursor.execute(query).fetchone()
        conn.close()
        return door_data

    except Exception as e:
        return e        

def getConfiguration():
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "SELECT * FROM configuration"
        config_data = cursor.execute(query).fetchall()
        conn.close()
        return config_data

    except Exception as e:
        return e
    
def getConfigurationByKey(key):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "SELECT * FROM configuration WHERE key ='{}'".format(key)
        id,key,value = cursor.execute(query).fetchone()
        
        conn.close()
        return value

    except Exception as e:
        return e

def updateConfig(value, key):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()

        query = "SELECT * FROM configuration WHERE key = ?"
        cursor.execute(query, (key,))
        existing_row = cursor.fetchone()


        if existing_row is None:
            query = "INSERT INTO configuration (key, value) VALUES ('{}','{}')".format(key, value)
            cursor.execute(query)
        else:
            query = "UPDATE configuration SET value = '{}' WHERE key = '{}'".format(value, key)
            cursor.execute(query)

        conn.commit()
        conn.close()

    except Exception as e:
        return e

def addDoor(id, door_id, entity_id, friendly_name):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "INSERT INTO doors (id, door_id, entity_id, friendly_name, automatic_mode) VALUES ('{}','{}', '{}','{}', '1')".format(id, door_id, entity_id,friendly_name)
        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e

def addLight(id, entity_id, friendly_name):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "INSERT INTO lights (id, entity_id, name, automatic_mode) VALUES ('{}', '{}','{}', '1')".format(id, entity_id,friendly_name)
        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e

def deleteLight():
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "DELETE FROM lights"
        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e

def updateLightsName(entity_id,name):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "UPDATE lights SET name  = '{}' WHERE entity_id = '{}'".format(name, entity_id)

        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e
    
def deleteDoor(id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "DELETE FROM doors WHERE id = '{}'".format(id)
        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e
        
def updateDoorId(id, door_id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "UPDATE doors SET door_id = '{}', entity_id='door{}' WHERE id = '{}'".format(door_id, door_id,id)
        
        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e

def updateDoorEntityId(id, entity_id):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "UPDATE doors SET entity_id = '{}' WHERE id = '{}'".format(entity_id, id)

        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e

def updateDoorName(id, friendly_name):
    try:
        conn = sqlite3.connect(db_path, isolation_level=None)
        cursor = conn.cursor()
        query = "UPDATE doors SET friendly_name = '{}' WHERE id = '{}'".format(friendly_name, id)

        cursor.execute(query)
        conn.commit()
        conn.close()

    except Exception as e:
        return e
        
# def updateDoorMode(id, automatic_mode):
#     try:
#         conn = sqlite3.connect(db_path, isolation_level=None)
#         cursor = conn.cursor()
#         query = "UPDATE doors SET automatic_mode = '{}' WHERE id = '{}'".format(automatic_mode, id)

#         cursor.execute(query)
#         conn.commit()
#         conn.close()

#     except Exception as e:
#         return e
    
def updateDoorMode(id, automatic_mode, ok_cloud_access_token,back_end_url, club_id):
    try:
        url = f"{back_end_url}api/doors/update-door-mode?clubId={club_id}"

        body = {
            "id": id,
            "automatic_mode": automatic_mode
        }

        # Add the bearer token to the headers
        headers = {
            "Authorization": f"Bearer {ok_cloud_access_token}",
            "Content-Type": "application/json"
        }

        # Send the POST request with headers
        response = requests.put(url, json=body, headers=headers)

        # Return the response
        return response

    except Exception as e:
        return e

# def updateLightMode(id, automatic_mode):
#     try:
#         conn = sqlite3.connect(db_path, isolation_level=None)
#         cursor = conn.cursor()
#         query = "UPDATE lights SET automatic_mode = '{}' WHERE id = '{}'".format(automatic_mode, id)

#         cursor.execute(query)
#         conn.commit()
#         conn.close()

#     except Exception as e:
#         return e

def updateLightMode(id, automatic_mode, ok_cloud_access_token,back_end_url, club_id):
    try:
        url = f"{back_end_url}api/lights/update-light-mode?clubId={club_id}"

        body = {
            "id": id,
            "automatic_mode": automatic_mode
        }

        # Add the bearer token to the headers
        headers = {
            "Authorization": f"Bearer {ok_cloud_access_token}",
            "Content-Type": "application/json"
        }

        # Send the POST request with headers
        response = requests.put(url, json=body, headers=headers)

        # Return the response
        return response

    except Exception as e:
        return e
    

def updateLightLimitedOption(id, limited_option, ok_cloud_access_token, back_end_url, club_id):
    try:
        url = f"{back_end_url}api/lights/update-limited-option?clubId={club_id}"

        body = {
            "id": id,
            "limited_option": limited_option
        }

        headers = {
            "Authorization": f"Bearer {ok_cloud_access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=body, headers=headers)

        return response

    except Exception as e:
        return e
    

    
def updateMinLightLevel(id, minLevel, ok_cloud_access_token,back_end_url, club_id):
    try:
        url = f"{back_end_url}api/lights/update-min-light-level?clubId={club_id}"

        body = {
            "id": id,
            "min_level": minLevel
        }

        # Add the bearer token to the headers
        headers = {
            "Authorization": f"Bearer {ok_cloud_access_token}",
            "Content-Type": "application/json"
        }

        # Send the POST request with headers
        response = requests.put(url, json=body, headers=headers)

        # Return the response
        return response

    except Exception as e:
        return e
    
def updateMaxLightLevel(id, maxLevel, ok_cloud_access_token,back_end_url, club_id):
    try:
        url = f"{back_end_url}api/lights/update-max-light-level?clubId={club_id}"

        body = {
            "id": id,
            "max_level": maxLevel
        }

        # Add the bearer token to the headers
        headers = {
            "Authorization": f"Bearer {ok_cloud_access_token}",
            "Content-Type": "application/json"
        }

        # Send the POST request with headers
        response = requests.put(url, json=body, headers=headers)

        # Return the response
        return response

    except Exception as e:
        return e
    
def getClubName(back_end_url, ok_cloud_access_token, club_id):
    try:
        url = f"{back_end_url}api/club-name?clubId={club_id}"

        # Add the bearer token to the headers
        headers = {
            # "Authorization": f"Bearer {ok_cloud_access_token}",
            "Content-Type": "application/json"
        }

        # Send the POST request with headers
        response = requests.get(url, headers=headers)

        # Return the response
        logging.info(response)
        result = {"tenant": response.json()}
        return result, 200

    except Exception as e:
        logging.info(e)
        return e
