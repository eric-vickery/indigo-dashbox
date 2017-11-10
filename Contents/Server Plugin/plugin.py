#! /usr/bin/env python
# -*- coding: utf-8 -*-

####################
# Brultech Dashbox plugin interface for Indigo 7
#
# Copyright (c)2017 Eric Vickery.
####################
import sys
import os
import threading
import time
from HTMLParser import HTMLParser
import pg8000
import requests

kOnlineState = "online"
kOfflineState = "offline"

device_dict = {}
parser = HTMLParser()
conn = pg8000.connect(user="dbbackup", password="universe", database="brultech_dash", host="dashbox.vickeryranch.com")
cursor = conn.cursor()
cursor.execute("SELECT channel_id, channel_name, pulse_unit, chnum, ctype, devices.device_id, netchannel_id FROM channel INNER JOIN devices ON channel.device_id = devices.device_id WHERE hide = 0 ORDER BY channel_id ASC")
results = cursor.fetchall()
for row in results:
	device_dict[channel_id] = 
	channel_id, channel_name, pulse_unit, chnum, cttype, device_id, netchannel_id = row
	print("id = %d, name = %s, Type = %d" % (channel_id, parser.unescape(channel_name), row[4]))
print(results)
cursor.close()
conn.close()

result = requests.get("http://dashbox.vickeryranch.com/index.php/pages/search/all/0")
print result.json()["channels"]

result = requests.get("http://dashbox.vickeryranch.com/index.php/pages/search/getWattVals")
power_data = result.json()

for device in power_data:
	print device
	for reading in power_data[device]["watts"]:
		print reading


class Plugin(indigo.PluginBase):

	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.debug = False
		self.inclusionMode = False

		self.connection = None
		self.connectionAttempts = 0

		self.devices = indigo.Dict()

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
				indigo.server.log(u"received \"%s\" %s to %s" % (dev.name, "power load", simulateWattsStr))
			keyValueList.append({'key': 'curEnergyLevel', 'value': simulateWatts, 'uiValue': simulateWattsStr})

		if "accumEnergyTotal" in dev.states:
			simulateKwh = dev.states.get("accumEnergyTotal", 0) + 0.001
			simulateKwhStr = "%.3f kWh" % (simulateKwh)
			if logRefresh:
				indigo.server.log(u"received \"%s\" %s to %s" % (dev.name, "energy total", simulateKwhStr))
			keyValueList.append({'key': 'accumEnergyTotal', 'value': simulateKwh, 'uiValue': simulateKwhStr})

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

			if deviceId not in indigo.devices:
				properties = indigoDevice.pluginProps

				address = self.getAddress(address=properties["address"])

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
		# TURN ON ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		if action.sensorAction == indigo.kSensorAction.TurnOn:
			indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "on"))

		# TURN OFF ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.TurnOff:
			indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "off"))

		# TOGGLE ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.Toggle:
			indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name, "toggle"))

	########################################
	# General Action callback
	########################################
	def actionControlUniversal(self, action, dev):
		# BEEP ######
		if action.deviceAction == indigo.kUniversalAction.Beep:
			indigo.server.log("Beep action not supported")

		# ENERGY UPDATE ######
		elif action.deviceAction == indigo.kUniversalAction.EnergyUpdate:
			indigo.server.log("Update action not supported")

		# ENERGY RESET ######
		elif action.deviceAction == indigo.kUniversalAction.EnergyReset:
			indigo.server.log("EnergyReset action not supported")

		# STATUS REQUEST ######
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
				# indigo.server.log(u"READ:WRITE")
				pass
			elif messageType == self.getMessageNumber("PRESENTATION"):
				# indigo.server.log(u"PRESENTATION")
				self.processPresentationCommand(nodeId, childId, acqType, itemType, payload)
			elif messageType == self.getMessageNumber("SET"):
				# indigo.server.log(u"SET")
				self.processSetCommand(nodeId, childId, acqType, itemType, payload)
			elif messageType == self.getMessageNumber("REQUEST"):
				# indigo.server.log(u"REQUEST")
				self.processRequestCommand(nodeId, childId, acqType, itemType, payload)
			elif messageType == self.getMessageNumber("INTERNAL"):
				# indigo.server.log(u"INTERNAL")
				self.processInternalCommand(nodeId, childId, acqType, itemType, payload)
			elif messageType == self.getMessageNumber("STREAM"):
				# indigo.server.log(u"STREAM")
				self.processStreamCommand(nodeId, childId, acqType, itemType, payload)
			else:
				raise Exception("Unrecognized messageType %s" % messageType)
		except Exception, (ErrorMessage):
			self.errorLog(u"process incoming failed: %s" % ErrorMessage)

			if "serial" in ErrorMessage:
				self.connection = None

	def sendCommand(self, nodeId, childId, messageType, ack, itemType, value, uiValue):
		address = self.getAddress(nodeId=nodeId, childId=childId)

		device = self.getDevice(address=address)

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
	def getDevice(self, indigoDevice=None, nodeId=None, childId=None, address=None):
		if not address:
			address = self.getAddress(nodeId=nodeId, childId=childId)
		else:
			address = self.getAddress(address=address)

		if nodeId == kNoneNodeId or childId == kNoneChildId or nodeId == kMaxNodeId or childId == kMaxChildId:
			self.debugLog(u"get device %s:%s skipped" % nodeId, childId)

			return None

		self.debugLog(u"get device %s" % address)

		if address not in self.devices:
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
				properties = {"id": indigoDevice.id}

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
			if property not in device:
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

		return ""

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

	########################################
	# Start connecting
	########################################
	def openConnection(self):
		if self.address:
			self.connection = self.openSerial("com.it2be.indigo.mysensors", portUrl=self.address, baudrate=kBaudrate, timeout=0)
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
