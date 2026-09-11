import appdaemon.plugins.hass.hassapi as hass
import requests
import time
import paho.mqtt.client as mqtt
import ssl

#
# Syltek Integration App
#
# Args:
#
# DEPRECATED 2026-09-11 -- not imported or instantiated anywhere in this
# repository (verified: `grep -rn "SyltekIntegration(" .` only matches the
# class definition itself). Left in place only in case an external
# AppDaemon apps.yaml still references it by class name. Its own
# clear_all_entities() below was even more dangerous than the one removed
# from __main__.py -- it deleted EVERY entity in Home Assistant, not just
# binary_sensor.* ones -- so it has been neutralized into a no-op.
# Do not re-enable it without first switching to an explicit, LoboBrain-
# owned entity list, the same way __main__.py's version should be if it's
# ever needed again.


class SyltekIntegration(hass.Hass):

  home_assistant_access_key = ""
  home_assistant_url = ""
  mqtt_broker = ""
  mqtt_port = ""
  mqtt_user_name = ""
  mqtt_user_password = ""
  api_genaration_url = 'https://pro.syltek.com/hermes/api/v1/Lights/plcnext/register?'

  def initialize(self):
    self.log("Hello from AppDaemon")
    self.log("You are now ready to run Apps!")
    self.log("Syltek Integration App is running with imports.")
    self.home_assistant_access_key = self.args['home_assistant_access_token']
    self.home_assistant_url = self.args['home_assistant_url']
    self.mqtt_broker = self.args['mqtt_broker']
    self.mqtt_port = self.args['mqtt_port']
    self.mqtt_user_name = self.args['mqtt_user_name']
    self.mqtt_user_password = self.args['mqtt_user_password']
    self.uuid = self.args["club_uuid"]

    self.log("Club UUID: {}".format(self.uuid))

    # Neutralized 2026-09-11: this used to unconditionally call
    # clear_all_entities(), which deleted EVERY entity in Home Assistant
    # (see deprecation notice at top of file). clear_all_entities() itself
    # is now a no-op below, kept only so this call doesn't raise if the
    # class is still loaded by an external config.
    self.clear_all_entities()

    # Call the function to fetch data from the API
    self.fetch_data_with_uuid(self.api_genaration_url, self.uuid)
  
  #Clear all entities in the Home Assistant
  def clear_all_entities(self):
    # Neutralized 2026-09-11: this used to delete EVERY entity in the
    # whole Home Assistant instance (no filtering at all, worse than the
    # binary_sensor-only version that was in __main__.py). See the
    # deprecation notice at the top of this file.
    self.log(
        "clear_all_entities() was called but is disabled -- it used to "
        "delete every entity in Home Assistant unconditionally. No action "
        "taken."
    )
    return

  #Get apiKey and tenant with UUID
  def fetch_data_with_uuid(self, api_genaration_url, uuid):
      # Define the API endpoint and parameters
      params = {'UUID': uuid}
      
      try:
          # Make a GET request to the API with the specified parameters
          response1 = requests.get(api_genaration_url, params=params)

          # Check if the request was successful (status code 200)
          if response1.status_code == 200:
              # Parse and self.log the response data (you may want to modify this based on the API response format)
              data = response1.json()
              self.log("API Response 1:")
              # self.log(data)

          # Access the "apiKey" and "tenant" object in the JSON response and assign it to a new variable called "ApiKey" and "Tenant"
              ApiKey = data.get('apiKey')
              Tenant = data.get('tenant')
              global global_tenant 
              global_tenant = Tenant
              self.log("Api Key: {}\nTenant: {}\n".format(ApiKey,Tenant))

              # Replace 'your_sessionID_genaration_url_here' with the actual API endpoint URL
              sessionID_genaration_url = 'https://'+Tenant+'.syltek.com/api/newsession?'
            
              # Replace 'apikey' with the actual ApiKey parameter value
              apikey = ApiKey

              #Connect to Mqtt Broker
              def on_connect(client, userdata, flags, rc):
                  self.log(f"Connected with result code {rc}")

              #Get Payload
              def on_message(client, userdata, msg):
                  result = msg.payload.decode('utf-8').replace('"', '').split()
                  self.log(f"Door Result: {result}")
                  cardCode = result[1]
                  self.log("code: {}".format(cardCode))
                  idTerminal = int(result[3])
                  self.log("door: {}".format(idTerminal))
                  self.validate_terminal(cardCode,idTerminal,Tenant)  

              # Create an MQTT client instance
              client = mqtt.Client()

              # Set the TLS/SSL options
              client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)

              # # Set the callbacks
              client.on_connect = on_connect
              client.on_message = on_message

              # Set the username and password (if required by your broker)
              client.username_pw_set(self.mqtt_user_name, self.mqtt_user_password)

              # Connect to the broker
              client.connect(self.mqtt_broker, port=self.mqtt_port)
              client.subscribe(global_tenant, qos=2)
              # Start the MQTT loop
              client.loop_start()

              # Call the function to fetch data from the API
              self.fetch_data_with_sessionid(Tenant, sessionID_genaration_url, apikey)
          else:
              # self.log an error message if the request was not successful
              self.log(f"Error while fetching API: Invalid UUID")
      
      except Exception as e:
          self.log(f"An error occurre while getting api key: {e}")

  #Validate Terminal
  def validate_terminal(self, cardCode, idTerminal, Tenant):
      params = {'cardCode': cardCode, 'idTerminal': idTerminal}
      validate_terminalurl = 'https://'+Tenant+'.syltek.com/api/validateterminal?'
      
      try:
          # Make a GET request to the API with the specified parameters
          responseTerminal = requests.get(validate_terminalurl, params=params)

          # Check if the request was successful (status code 200)
          if responseTerminal.status_code == 200:
            self.log("Terminale Validate Responce :{}".format(responseTerminal.text))
            doorState = int(responseTerminal.text.split(';')[0])
            self.log("Door State",doorState)
            self.update_door_state(str(idTerminal),doorState)
          else:
              # self.log an error message if the request was not successful
              self.log(f"Error while validate terminal: {responseTerminal.status_code} - {responseTerminal.text}")
      
      except Exception as e:
          self.log(f"An error occurr while validate terminal: {e}")

  #Update the door state in Home Assistant
  def update_door_state(self, idTerminal, doorState):
      # Home Assistant API endpoint for creating or updating a state
      door_entity = 'door'+idTerminal
      api_url = self.home_assistant_url+"/api/states/binary_sensor."+door_entity
      
      # Replace with your Home Assistant access token
      access_token = self.home_assistant_access_key

      # Headers for the request
      headers = {
          "Authorization": f"Bearer {access_token}",
          "Content-Type": "application/json",
      }

      #binary sensor data and make POST requests
      
      #Name Doors
      door_name = self.args.get('door'+str(idTerminal)+'_name')
      if not door_name:
          door_name = 'Door '+str(idTerminal)

      sensor_data = {
          "entity_id": door_entity,
          "state": "on" if doorState == 1 else "off",
          "unique_id": idTerminal,
          "attributes": {
              "friendly_name": door_name,
              "device_class": "door",
              "unique_id": idTerminal,
          
          },
      }

      self.log(sensor_data)
      entity_id = sensor_data["entity_id"]
      api_url_sensor = api_url
      response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

      # Check the response for each sensor
      if response4.status_code == 200:
          self.log(f"Binary sensor door {entity_id} updated successfully!")
      elif response4.status_code == 201:
          self.log(f"Binary sensor door {entity_id} created successfully!")    
      else:
          self.log(f"Error creating binary sensor door {entity_id}: {response4.status_code} - {response4.text}")

      if doorState == 1:
          time.sleep(30)

          #turn off the door after 30s
          #binary sensor data and make POST requests
          sensor_data = {
              "state": "off",
              "entity_id": door_entity,
              "unique_id": idTerminal,
              "attributes": {
                  "friendly_name": door_name,
                  "device_class": "door",
                  "unique_id": idTerminal,
              },
          }

          # self.log(sensor_data)
          entity_id = door_entity
          api_url_sensor = api_url
          response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

          # Check the response for each sensor
          if response4.status_code == 200:
              self.log(f"Binary sensor door {entity_id} updated successfully!")
          elif response4.status_code == 201:
              self.log(f"Binary sensor door {entity_id} created successfully!")    
          else:
              self.log(f"Error creating binary sensor door {entity_id}: {response4.status_code} - {response4.text}")
        
  #Generate Session ID
  def fetch_data_with_sessionid(self, Tenant, sessionID_genaration_url, apikey):
      # Define the API endpoint and parameters
      params = {'apikey': apikey}
      
      try:
          # Make a GET request to the API with the specified parameters
          response2 = requests.get(sessionID_genaration_url, params=params)

          # Check if the request was successful (status code 200)
          if response2.status_code == 200:
              # Parse and self.log the response data (you may want to modify this based on the API response format)
              data = response2.json()
              self.log("API Response 2:")
              self.log(data)

              # Access the "sessionId" object in the JSON response and assign it to a new variable called "SessionID"
              SessionID = data.get('sessionId')
              self.log("Session ID: {}".format(SessionID))
              

              # Replace the actual API endpoint URL
              resources_genaration_url = 'https://'+Tenant+'.syltek.com/api/Resources?'

              # Replace 'sessionID' with the actual SessionID parameter value
              sessionID = SessionID

              # Call the function to fetch data from the API
              self.fetch_data_with_resources(Tenant, resources_genaration_url, sessionID, apikey)
          else:
              # self.log an error message if the request was not successful
              self.log(f"Error while fetching session id: {response2.status_code} - {response2.text}")
      
      except Exception as e:
          self.log(f"An error occurr while fetching session id: {e}")

  #Get Resources
  def fetch_data_with_resources(self, Tenant, resources_genaration_url, sessionID, apikey):
      # Define the API endpoint and parameters
      params = {'idsession': sessionID}

      try:
          # Make a GET request to the API with the specified parameters
          response3 = requests.get(resources_genaration_url, params=params)

          # Check if the request was successful (status code 200)
          if response3.status_code == 200:
              # Parse and self.log the response data (you may want to modify this based on the API response format)
              data = response3.json()
              self.log("API Response 3:")
              self.log(data)

              id_array = [str(item['id']) for item in data]
              id_string = ','.join(id_array)
              self.log(id_string)  
              
            
              resources_id = id_string

              # Call the function to fetch data from the API
              self.fetch_data_with_light_id(Tenant, apikey, resources_id, data, resources_genaration_url, sessionID)

          else:
              # self.log an error message if the request was not successful
              self.log(f"Error while fetching resources: {response3.status_code} - {response3.text}")

      except Exception as e:
          self.log(f"An error occurr while fetching resources: {e}")

  #Get states and update it in the Home Assistant
  def fetch_data_with_light_id(self, Tenant, apikey, resources_id, data, resources_genaration_url, sessionID):
      # Define the API endpoint and parameters
      params = {'IgnoreSunTime': self.args['ignore_sun_time'], 'UseExtrasPeriods': self.args['use_extras_periods'], 'apiKey': apikey, 'IdResources':resources_id}
      
      try:
          # Replace with the actual API endpoint URL
          light_state_url = 'https://'+Tenant+'.syltek.com/hermes/api/v1/Lights/activeGrouped?'

          # Make a GET request to the API with the specified parameters
          response5 = requests.get(light_state_url, params=params)

          # Check if the request was successful (status code 200)
          if response5.status_code == 200:  
              light_state = response5.json()
              self.log(light_state)

              # Home Assistant API endpoint for creating or updating a state
              api_url = self.home_assistant_url+"/api/states/binary_sensor.{}"

              # Replace with your Home Assistant access token
              access_token = self.home_assistant_access_key

              # Headers for the request
              headers = {
                  "Authorization": f"Bearer {access_token}",
                  "Content-Type": "application/json",
              }

              # Iterate through binary sensors data and make POST requests
              for item in data:
                  sensor_data = {
                      "entity_id": item['id'],
                      "state": "off" if light_state[str(item['id'])] == False else "on",
                      "unique_id": item['id'],
                      "icon": "mdi:lightbulb",
                      "attributes": {
                          "friendly_name": item['name'],
                          "device_class": "light",
                          "unique_id": item['id'],
                      
                      },
                  }
                  self.log(sensor_data)
                  entity_id = sensor_data["entity_id"]
                  api_url_sensor = api_url.format(entity_id)
                  response4 = requests.post(api_url_sensor, json=sensor_data, headers=headers)

                  # Check the response for each sensor
                  if response4.status_code == 200:
                      self.log(f"Binary sensor {entity_id} updated successfully!")
                  elif response4.status_code == 201:
                      self.log(f"Binary sensor {entity_id} created successfully!")    
                  else:
                      self.log(f"Error creating binary sensor {entity_id}: {response4.status_code} - {response4.text}")

              time.sleep(60)
              self.fetch_data_with_resources(Tenant, resources_genaration_url, sessionID, apikey)   

          else:
              # self.log an error message if the request was not successful
              self.log(f"Error5: {response5.status_code} - {response5.text}")
      except Exception as e:
          self.log(f"An error occurr while updating light states: {e}")