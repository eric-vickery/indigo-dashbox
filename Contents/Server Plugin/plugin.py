#! /usr/bin/env python
# -*- coding: utf-8 -*-

####################
# Brultech Dashbox plugin interface for Indigo 7
#
# Copyright (c)2017 Eric Vickery.
####################
import httplib
import urllib
import sys
import os
import threading
import glob
import time
from HTMLParser import HTMLParser
import pg8000

kOnlineState = "online"
kOfflineState = "offline"

parser = HTMLParser()
conn = pg8000.connect(user="dbbackup", password="universe", database="brultech_dash", host="dashbox.vickeryranch.com")
cursor = conn.cursor()
cursor.execute("SELECT channel_id, channel_name, pulse_unit, chnum, ctype, devices.device_id, netchannel_id FROM channel INNER JOIN devices ON channel.device_id = devices.device_id WHERE hide = 0 ORDER BY channel_id ASC")
results = cursor.fetchall()
for row in results:
    channel_id, channel_name, pulse_unit, chnum, cttype, device_id, netchannel_id = row
    print("id = %d, name = %s, Type = %d" % (channel_id, parser.unescape(channel_name), row[4]))
# print(results)

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.debug                  = False
        self.inclusionMode          = False

        self.connection             = None
        self.connectionAttempts     = 0

        self.devices                = indigo.Dict()

    def __del__(self):
        indigo.PluginBase.__del__(self)

    def startup(self):
        self.debug = self.pluginPrefs.get("showDebugInfo", False)

        self.debugLog(u"Connecting...")

        self.address = self.pluginPrefs["address"]
        self.unit = self.pluginPrefs.get("unit", "M")

        result = False

        while not result and self.connectionAttempts < 6:
            result = self.openConnection()

            self.sleep(kWorkerSleep)

        if not result:
            self.errorLog(u"permanently failed connecting Gateway at address: %s" % self.address)

        self.loadDevices()

    def shutdown(self):
        self.debugLog(u"Disconnecting...")

        if self.connection:
            self.connection.close()

	def _refreshStatesFromHardware(self, dev, logRefresh):
		# As an example here we update the current power (Watts) to a random
		# value, and we increase the kWh by a smidge.
		keyValueList = []
		if "curEnergyLevel" in dev.states:
			simulateWatts = random.randint(0, 500)
			simulateWattsStr = "%d W" % (simulateWatts)
			if logRefresh:
				indigo.server.log(u"received \"%s\" %s to %s" %
				                  (dev.name, "power load", simulateWattsStr))
			keyValueList.append(
			    {'key': 'curEnergyLevel', 'value': simulateWatts, 'uiValue': simulateWattsStr})

		if "accumEnergyTotal" in dev.states:
			simulateKwh = dev.states.get("accumEnergyTotal", 0) + 0.001
			simulateKwhStr = "%.3f kWh" % (simulateKwh)
			if logRefresh:
				indigo.server.log(u"received \"%s\" %s to %s" %
				                  (dev.name, "energy total", simulateKwhStr))
			keyValueList.append(
			    {'key': 'accumEnergyTotal', 'value': simulateKwh, 'uiValue': simulateKwhStr})

		dev.updateStatesOnServer(keyValueList)

	def runConcurrentThread(self):
		try:
			while True:
				for dev in indigo.devices.iter("self"):
					if not dev.enabled or not dev.configured:
						continue

					# Plugins that need to poll out the status from the meter
					# could do so here, then broadcast back the new values to the
					# Indigo Server.
					self._refreshStatesFromHardware(dev, False)

				self.sleep(4)
		except self.StopThread:
			pass  # Optionally catch the StopThread exception and do any needed cleanup.

    def deviceStartComm(self, indigoDevice):
        self.debugLog(u"Device started: \"%s\" %s" % (indigoDevice.name, indigoDevice.id))
        pass

    def deviceStopComm(self, indigoDevice):
        self.debugLog(u"Device stopped: \"%s\" %s" % (indigoDevice.name, indigoDevice.id))

        try:
            deviceId = indigoDevice.id

            if not deviceId in indigo.devices:
                properties = indigoDevice.pluginProps

                address = self.getAddress(address = properties["address"])

                device = self.devices[address]

                device["id"] = ""

                self.devices[address] = device
        except Exception, (ErrorMessage):
            pass

    ########################################
    # DeviceFactory methods (specified in Devices.xml)
    ########################################
    def getDeviceGroupList(self, filter, valuesDict, deviceIdList):
        device_list = []

        for deviceId in deviceIdList:
            if deviceId in indigo.devices:
                indigoDevice = indigo.devices[deviceId]

                deviceName = indigoDevice.name
            else:
                deviceName = u"- device not found -"

            device_list.append((deviceId, deviceName))

        return device_list

    def addIndigoDevices(self, valuesDict, deviceIdList):
        try:
            nodeId = kNoneNodeId

            try:
                nodeId = int(valuesDict["selecteddevice"])

                self.debugLog(u"add device %s" % nodeId)
            except Exception, (ErrorMessage):
                pass

            if nodeId > kNoneNodeId:
                self.addIndigoChildren(nodeId)
        except Exception, (ErrorMessage):
            pass

        return valuesDict

    def getDeviceFactoryUiValues(self, devIdList):
        valuesDict = indigo.Dict()
        errorMsgDict = indigo.Dict()

        return (valuesDict, errorMsgDict)

    def validateDeviceFactoryUi(self, valuesDict, devIdList):
        errorsDict = indigo.Dict()

        return (True, valuesDict, errorsDict)

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        return (True, valuesDict)

    def closedDeviceFactoryUi(self, valuesDict, userCancelled, devIdList):
        return

    def validatePrefsConfigUi(self, valuesDict):
        return True

    ########################################
    # Sensor Action callback
    ########################################
	def actionControlSensor(self, action, dev):
		###### TURN ON ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		if action.sensorAction == indigo.kSensorAction.TurnOn:
			indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "on"))

		###### TURN OFF ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.TurnOff:
			indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "off"))

		###### TOGGLE ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.Toggle:
			indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "toggle"))


    ########################################
	# General Action callback
    ########################################
	def actionControlUniversal(self, action, dev):
		###### BEEP ######
		if action.deviceAction == indigo.kUniversalAction.Beep:
			indigo.server.log("Beep action not supported")

		###### ENERGY UPDATE ######
		elif action.deviceAction == indigo.kUniversalAction.EnergyUpdate:
			indigo.server.log("Update action not supported")

		###### ENERGY RESET ######
		elif action.deviceAction == indigo.kUniversalAction.EnergyReset:
			indigo.server.log("EnergyReset action not supported")

		###### STATUS REQUEST ######
		elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
			indigo.server.log("RequestStatus action not supported")

    ########################################
    # Incoming messages
    ########################################
    def processIncoming(self):
        arguments = None

        request = None
        nodeId = kMaxNodeId
        childId = kNoneChildId
        messageType = kNoneType
        acqType = kNoneType
        itemType = kNoneType
        payload = ""

        try:
            request = self.connection.readline()

            if request:
                request = request.strip("\n\r")

            if len(request) == 0:
                return

            self.debugLog(u"receive raw %s" % request)

            if request[0].isalpha() or request.find(";") == kNoneType or request.count(";") < 5:
                raise Exception("wrong request formatting: %s" % request)

            arguments = request.split(";")

            nodeId = int(arguments[0])
            childId = int(arguments[1])
            messageType = int(arguments[2])
            acqType = int(arguments[3])
            itemType = int(arguments[4])
            payload = ";".join(arguments[5:])

            if payload.startswith("read:") or payload.startswith("send:"):
                #indigo.server.log(u"READ:WRITE")
                pass
            elif messageType == self.getMessageNumber("PRESENTATION"):
                #indigo.server.log(u"PRESENTATION")
                self.processPresentationCommand(nodeId, childId, acqType, itemType, payload)
            elif messageType == self.getMessageNumber("SET"):
                #indigo.server.log(u"SET")
                self.processSetCommand(nodeId, childId, acqType, itemType, payload)
            elif messageType == self.getMessageNumber("REQUEST"):
                #indigo.server.log(u"REQUEST")
                self.processRequestCommand(nodeId, childId, acqType, itemType, payload)
            elif messageType == self.getMessageNumber("INTERNAL"):
                #indigo.server.log(u"INTERNAL")
                self.processInternalCommand(nodeId, childId, acqType, itemType, payload)
            elif messageType == self.getMessageNumber("STREAM"):
                #indigo.server.log(u"STREAM")
                self.processStreamCommand(nodeId, childId, acqType, itemType, payload)
            else:
                raise Exception("Unrecognized messageType %s" % messageType)
        except Exception, (ErrorMessage):
            self.errorLog(u"process incoming failed: %s" % ErrorMessage)

            if "serial" in ErrorMessage:
                self.connection = None

    def sendCommand(self, nodeId, childId, messageType, ack, itemType, value, uiValue):
        address = self.getAddress(nodeId = nodeId, childId = childId)

        device = self.getDevice(address = address)

        indigoDevice = None

        messageType = self.getMessageNumber(messageType)

        try:
            command = "%s;%s;%s;%s;%s;%s" % (nodeId, childId, messageType, ack, itemType, value)

            self.debugLog(u"command %s" % command)

            if device and device["id"]:
                indigoDevice = indigo.devices[device["id"]]

            if self.connection and self.connection.writable:
                self.connection.write(command + "\n")

                if indigoDevice:
                    indigo.server.log(u"sent '%s' %s " % (indigoDevice.name, uiValue))
                else:
                    indigo.server.log(u"sent '%s:%s' %s " % (nodeId, childId, uiValue))

                return True
            else:
               raise Exception("Can't write to serial port")
        except Exception, (ErrorMessage):
            if indigoDevice:
                self.errorLog(u"send '%s' %s failed: %s" % (indigoDevice.name, uiValue, ErrorMessage))
            else:
                self.errorLog(u"send '%s:%s' %s failed: %s" % (nodeId, childId, uiValue, ErrorMessage))

        return False

    ########################################
    # Device methods
    ########################################
    def getDevice(self, indigoDevice = None, nodeId = None, childId = None, address = None):
        if not address:
            address = self.getAddress(nodeId = nodeId, childId = childId)
        else:
            address = self.getAddress(address = address)

        if nodeId == kNoneNodeId or childId == kNoneChildId or nodeId == kMaxNodeId or childId == kMaxChildId:
            self.debugLog(u"get device %s:%s skipped" % nodeId, childId)

            return None

        self.debugLog(u"get device %s" % address)

        if not address in self.devices:
            if not nodeId:
                identifiers = self.getIdentifiers(address)

                nodeId = identifiers[0]
                childId = identifiers[1]

            device = self.createDevice(nodeId, childId, address)

            self.sendInternalCommand(nodeId, childId, "VERSION", "Get Version")

            if nodeId != kGatewayNodeId:
                self.sendInternalCommand(nodeId, childId, "SKETCH_NAME", "Get Sketch Name")
        else:
            device = self.devices[address]

            if indigoDevice:
                properties = { "id" : indigoDevice.id }

                self.updateDevice(device, address, properties)

        if address in self.devices:
            return self.devices[address]
        else:
            return None

    def createDevice(self, nodeId, childId, address):
        device = indigo.Dict()

        self.debugLog(u"create device %s" % address)

        if nodeId == 0:
            device["type"] = self.getSensorNumber("ARDUINO_NODE")
        else:
            device["type"] = kNoneType

        device["version"] = ""
        device["id"] = ""
        device["model"] = self.getSensorShortName(device["type"])
        device["modelVersion"] = ""

        self.devices[address] = device

        self.pluginPrefs["devices"] = self.devices

        self.updateNodeIds(nodeId, False)

        self.debugLog(u"now available device[%s] %s %s" % (address, device["type"], device["model"]))

    def updateDevice(self, device, address, properties):
        if not device:
            return

        updated = False

        for property in properties:
            if not property in device:
                self.debugLog(u"update device %s created %s = '%s'" % (address, property, properties[property]))

                device[property] = properties[property]

                updated = True
            elif device[property] != properties[property]:
                self.debugLog(u"update device %s updated %s = '%s'" % (address, property, properties[property]))

                device[property] = properties[property]

                updated = True

        if updated:
            self.devices[address] = device

            self.pluginPrefs["devices"] = self.devices

        return updated

    def updateNodeIds(self, nodeId, value):
        if nodeId == kMaxNodeId:
            return

        id = "N%s" % nodeId

        if self.nodeIds[id] != value:
            self.nodeIds[id] = value

            self.pluginPrefs["nodeIds"] = self.nodeIds

    def updateState(self, indigoDevice, itemType, payload):
        if not indigoDevice:
            return

        text = self.getVariableText(itemType)
        field = self.getVariableField(itemType)
        uiValue = None
        uiImage = None

        if itemType == 0:
            # TEMP, field == temperature
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f °C" % value) if self.unit == "M" else (u"%.1f °F" % value)
            uiImage = indigo.kStateImageSel.TemperatureSensor
        elif itemType == 1:
            # HUM, field == humidity
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.0f%%" % value)
            uiImage = indigo.kStateImageSel.HumiditySensor
        elif itemType == 2:
            # LIGHT, field == onOffState
            field = "onOffState"
            value = self.booleanValue(payload)
            uiValue = u"on" if value == True else u"off"
            uiImage = None
        elif itemType == 3:
            # DIMMER, field == dimmer
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 4:
            # PRESSURE, field == pressure
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f Pa" % value)
            uiImage = None
        elif itemType == 5:
            # FORECAST, field == forecast
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 6:
            # RAIN, field == rain
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f mm" % value) if self.unit == "M" else (u"%.1f inch" % value)
            uiImage = None
        elif itemType == 7:
            # RAINRATE, field == rain
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f mm" % value) if self.unit == "M" else (u"%.1f inch" % value)
            uiImage = None
        elif itemType == 8:
            # WIND, field == speed
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f mps" % value) if self.unit == "M" else (u"%.1f fps" % value)
            uiImage = indigo.kStateImageSel.WindSpeedSensor
        elif itemType == 9:
            # GUST, field == gust
            field = "gust"
            value = float(payload)
            uiValue = (u"%.1f mps" % value) if self.unit == "M" else (u"%.1f fps" % value)
            uiImage = None
        elif itemType == 10:
            # DIRECTION, field == direction
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = indigo.kStateImageSel.WindDirectionSensor
        elif itemType == 11:
            # UV, field == uv
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f" % value)
            uiImage = None
        elif itemType == 12:
            # WEIGHT, field == scale
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 13:
            # DISTANCE, field == distance
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.1f cm" % value) if self.unit == "M" else (u"%.1f inch" % value)
            uiImage = None
        elif itemType == 14:
            # IMPEDANCE, field == scale
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 15:
            # ARMED, field == security
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 16:
            # TRIPPED, field == onoroff
            field = "onOffState"
            value = self.booleanValue(payload)
            uiValue = u"on" if value == True else u"off"
            uiImage = None
        elif itemType == 17:
            # WATT, field == watt
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s W" % payload)
            uiImage = None
        elif itemType == 18:
            # KWH, field == kwh
            field = "kwh"
            value = int(payload)
            uiValue = (u"%s kWH" % payload)
            uiImage = None
        elif itemType == 19:
            # SCENE_ON, field == scene
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = indigo.kStateImageSel.PowerOn
        elif itemType == 20:
            # SCENE_OFF, field == scene
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = indigo.kStateImageSel.PowerOff
        elif itemType == 21:
            # HEATER, field == user
            field = "user"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 22:
            # HEATER_SW, field == onoroff
            field = "onOffState"
            value = self.booleanValue(payload)
            uiValue = u"on" if value == True else u"off"
            uiImage = None
        elif itemType == 23:
            # LIGHT_LEVEL, field == lux
            field = "sensorValue"
            value = float(payload)
            uiValue = (u"%.0f lux" % value)
            uiImage = indigo.kStateImageSel.LightSensor
        elif itemType == 24:
            # VAR_1, field == var1
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 25:
            # VAR_2, field == var2
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 26:
            # VAR_3, field == var3
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 27:
            # VAR_4, field == var4
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 28:
            # VAR_5, field == var5
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 29:
            # UP, field == up
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 30:
            # DOWN, field == down
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 31:
            # STOP, field == stop
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 32:
            # IR_SEND, field == send
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 33:
            # IR_RECEIVE, field == receive
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 34:
            # FLOW, field == flow
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 35:
            # VOLUME, field == volume
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 36:
            # LOCK, field == lock
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 37:
            # DUST_LEVEL, field == dust
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        elif itemType == 38:
            # VOLTAGE, field == voltage
            field = "value"
            value = int(payload)
            uiValue = (u"%s V" % payload)
            uiImage = None
        elif itemType == 39:
            # CURRENT, field == current
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s A" % payload)
            uiImage = None
        elif itemType == "batteryLevel":
            # field == batteryLevel
            field = itemType
            value = int(payload)
            uiValue = (u"%s%%" % payload)
            uiImage = None
        elif itemType == "state":
            # field == state
            field = itemType
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None
        else:
            field = "sensorValue"
            value = int(payload)
            uiValue = (u"%s" % payload)
            uiImage = None

        if itemType == "batteryLevel" or itemType == "state":
            indigoDevice.updateStateOnServer(field, value = value, uiValue = uiValue)
        elif (itemType == 2 or itemType == 3) and value != indigoDevice.states[field]:
            indigoDevice.updateStateOnServer(field, value = value)
        elif field == "onOffState" and value != indigoDevice.onState:
            indigoDevice.updateStateOnServer(field, value = value)
        elif field == "sensorValue" and value != indigoDevice.sensorValue:
            indigoDevice.updateStateOnServer(field, value = value, uiValue = uiValue)

        try:
            if uiImage is not None:
                indigoDevice.updateStateImageOnServer(uiImage)

        except Exception, (ErrorMessage):
                self.errorLog(u"setting image failed: %s" % ErrorMessage)

        return u"%s %s" % (text, uiValue)

    def updateProperties(self, indigoDevice, properties):
        if not indigoDevice:
            return

        indigoProperties = indigoDevice.pluginProps

        for property in properties:
            if hasattr(indigoProperties, property) and indigoProperties[property] == properties[property]:
                del properties[property]

        if len(properties) > 0:
            indigoProperties.update(properties)
            indigoDevice.replacePluginPropsOnServer(indigoProperties)

    def loadDevices(self):
        if "devices" in self.pluginPrefs:
            self.devices = self.pluginPrefs["devices"]

        if "nodeIds" in self.pluginPrefs:
            self.nodeIds = self.pluginPrefs["nodeIds"]
        else:
            self.setupNodeIds()

        try:
            for address in self.devices:
                 try:
                    device = self.devices[address]

                    self.debugLog(u"available device\n%s" % device)

                    identifiers = self.getIdentifiers(address)

                    nodeId = identifiers[0]
                    childId = identifiers[1]

                    deviceId = device["id"]

                    if not deviceId in indigo.devices:
                        self.updateDevice(device, address, { "id" : "" })

                    if self.connection and self.connection.isOpen():
                        if nodeId == kGatewayNodeId and childId == kGatewayChildId:
                            self.gatewayVersion = device["version"]

                            self.sendInternalCommand(nodeId, childId, "VERSION", "Get Version")
                        elif device["type"] == kNoneType or childId == kGatewayChildId:
                            self.sendInternalCommand(nodeId, childId, "VERSION", "Get Version")
                            self.sendInternalCommand(nodeId, childId, "SKETCH_NAME", "Get Sketch Name")
                 except Exception, (ErrorMessage):
                    pass

            for deviceId in indigo.devices.iter("self"):
                try:
                    indigoDevice = indigo.devices[deviceId]

                    self.debugLog(u"used device\n%s" % indigoDevice)

                    if indigoDevice.address:
                        address = self.getAddress(address = indigoDevice.address)

                        device = self.getDevice(indigoDevice, address = address)

                    if not (self.connection and self.connection.isOpen()):
                        indigoDevice.setErrorStateOnServer(kOfflineState)
                except Exception, (ErrorMessage):
                    pass
        except Exception, (ErrorMessage):
            self.errorLog(u"load devices failed %s" % ErrorMessage)

        self.debugLog(u"found %s available devices" % len(self.devices))

    ########################################
    # Start connecting
    ########################################
    def openConnection(self):
        if self.address:
            self.connection = self.openSerial("com.it2be.indigo.mysensors", portUrl = self.address, baudrate = kBaudrate, timeout = 0)
        else:
            self.address = "undefined"

        if self.connection:
            self.connectionAttempts = 0

            indigo.server.log(u"connected to Gateway on %s" % self.address)

            return True
        else:
            self.connectionAttempts = self.connectionAttempts + 1

            return False

    ########################################
    # Menu Methods
    ########################################
    def toggleDebugging(self):
        if self.debug:
            indigo.server.log(u"Turning off debug logging")
            self.pluginPrefs["showDebugInfo"] = False
        else:
            indigo.server.log(u"Turning on debug logging")
            self.pluginPrefs["showDebugInfo"] = True

        self.debug = not self.debug
