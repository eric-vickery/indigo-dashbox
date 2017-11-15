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

kChannelId = "channelId"
kChannelName = "channelName"
kPulseUnit = "pulseUnit"
kChannelNumber = "channelNumber"
kChannelType = "channelType"
kDeviceId = "deviceId"
kNetchannelId = "netchannelId"


kPowerMeterDevice = "powerMeterDevice"
kTemperatureDevice = "temperatureSensorDevice"
kPulseSensorDevice = "pulseSensorDevice"
kVoltageDevice = "voltageSensorDevice"

kChannelTypeToDeviceType = {
	0: kPowerMeterDevice,
	1: kTemperatureDevice,
	2: kPulseSensorDevice,
	3: kVoltageDevice
}


class Plugin(indigo.PluginBase):

	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.debug = False

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def startup(self):
		self.debug = self.pluginPrefs.get("showDebugInfo", False)

		self.debugLog(u"Connecting...")

		self.address = self.pluginPrefs["address"]

		result = False

	def shutdown(self):
		self.debugLog(u"Disconnecting...")

	def refreshStatesFromHardware(self, logRefresh):
		indexedPowerData = {}

		host = self.pluginPrefs["address"]
		if host is None or host == "":
			return indexedPowerData

		try:
			result = requests.get("http://" + host + "/index.php/pages/search/all/0", timeout=1.5)
			if result.status_code == requests.codes.ok:
				activeChannels = result.json()["channels"]

				result = requests.get("http://" + host + "/index.php/pages/search/getWattVals", timeout=1.5)
				if result.status_code == requests.codes.ok:
					powerData = result.json()

					index = 0
					for device in powerData:
						for reading in powerData[device]["watts"]:
							indexedPowerData[int(activeChannels[index])] = reading
							index += 1

					if logRefresh:
						indigo.server.log(u"Queried Dashbox successfully")

		except requests.exceptions.RequestException:
			pass

		return indexedPowerData

	def getDailyUsage(self, channelId):
		host = self.pluginPrefs["address"]
		if host is None or host == "":
			return 0.0

		key = None
		totalDailyUsage = 0.0
		result = requests.post("http://" + host + "/index.php/pages/load/loadBarGraph", data={"chans": "%s,-1,-1" % (channelId)})
		if result.status_code == requests.codes.ok:
			usage = result.json()
			for usageRecord in usage:
				if key is None:
					for keyIndex in usageRecord:
						if keyIndex != "date":
							key = keyIndex
				hourlyUsage = 0.0
				try:
					hourlyUsage = usageRecord[key]
				except:
					pass
				totalDailyUsage += hourlyUsage
			return totalDailyUsage
		else:
			return 0.0

	def refreshDeviceFromData(self, dev, powerData, logRefresh):

		keyValueList = []

		if dev.deviceTypeId == kTemperatureDevice:
			if dev.sensorValue is not None:
				exampleTempFloat = float(powerData[dev.pluginProps[kChannelId]])
				exampleTempStr = "%.1f °F" % (exampleTempFloat)

				keyValueList.append({'key': 'sensorValue', 'value': exampleTempFloat, 'uiValue': exampleTempStr})
				dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensor)

		elif dev.deviceTypeId == kVoltageDevice:
			if dev.sensorValue is not None:
				exampleTempFloat = float(powerData[dev.pluginProps[kChannelId]])
				exampleTempStr = "%.1f V" % (exampleTempFloat)

				keyValueList.append({'key': 'sensorValue', 'value': exampleTempFloat, 'uiValue': exampleTempStr})

		elif dev.deviceTypeId == kPulseSensorDevice:
			if dev.sensorValue is not None:
				exampleTemp = int(powerData[dev.pluginProps[kChannelId]])
				exampleTempStr = "%d Pulses" % (exampleTemp)

				keyValueList.append({'key': 'sensorValue', 'value': exampleTemp, 'uiValue': exampleTempStr})

		elif dev.deviceTypeId == kPowerMeterDevice:
			if "curEnergyLevel" in dev.states:
				watts = int(powerData[dev.pluginProps[kChannelId]])
				wattsStr = "%d W" % (watts)
				if logRefresh:
					indigo.server.log(u"received \"%s\" %s to %s" % (dev.name, "power load", wattsStr))
				keyValueList.append({'key': 'curEnergyLevel', 'value': watts, 'uiValue': wattsStr})

			if "accumEnergyTotal" in dev.states:
				dailyKwh = self.getDailyUsage(dev.pluginProps[kChannelId])
				dailyKwhStr = "%.3f kWh" % (dailyKwh)
				if logRefresh:
					indigo.server.log(u"received \"%s\" %s to %s" % (dev.name, "energy total", dailyKwhStr))
				keyValueList.append({'key': 'accumEnergyTotal', 'value': dailyKwh, 'uiValue': dailyKwhStr})

		dev.updateStatesOnServer(keyValueList)

	def runConcurrentThread(self):
		try:
			while True:
				powerData = self.refreshStatesFromHardware(False)
				for dev in indigo.devices.iter("self"):
					if not dev.enabled or not dev.configured:
						indigo.server.log(u"Device not enabled")
						continue

					self.refreshDeviceFromData(dev, powerData, False)

				self.sleep(4)
		except self.StopThread:
			pass  # Optionally catch the StopThread exception and do any needed cleanup.

	def deviceStartComm(self, indigoDevice):
		self.debugLog(u"Device started: \"%s\" %s" % (indigoDevice.name, indigoDevice.id))
		pass

	def deviceStopComm(self, indigoDevice):
		self.debugLog(u"Device stopped: \"%s\" %s" % (indigoDevice.name, indigoDevice.id))
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
		# First remove all the devices we have added
		self.removeAllDevices(valuesDict, deviceIdList)

		# Now go find all the active channels on the Dashbox and add them
		hostName = self.pluginPrefs["address"]
		dbPassword = self.pluginPrefs["password"]
		if hostName is None or hostName == "" or dbPassword is None or dbPassword == "":
			return

		parser = HTMLParser()
		conn = pg8000.connect(user="dbbackup", password=dbPassword, database="brultech_dash", host=hostName)
		cursor = conn.cursor()
		cursor.execute("SELECT channel_id, channel_name, pulse_unit, chnum, ctype, devices.device_id, netchannel_id FROM channel INNER JOIN devices ON channel.device_id = devices.device_id WHERE hide = 0 ORDER BY channel_id ASC")
		results = cursor.fetchall()
		device_dict = {}
		for row in results:
			channel_id, channel_name, pulse_unit, chnum, ctype, device_id, netchannel_id = row
			deviceType = kChannelTypeToDeviceType[ctype]

			newdev = indigo.device.create(indigo.kProtocol.Plugin, deviceTypeId=deviceType)
			newdev.model = "Dashbox Channel"
			newdev.subModel = parser.unescape(channel_name)
			newdev.name = parser.unescape(channel_name)
			newdev.remoteDisplay = True
			newdev.replaceOnServer()

			device_dict["channelId"] = channel_id
			device_dict["channelName"] = parser.unescape(channel_name)
			device_dict["pulseUnit"] = pulse_unit
			device_dict["channelNumber"] = chnum
			device_dict["channelType"] = ctype
			device_dict["deviceId"] = device_id
			device_dict["netchannelId"] = netchannel_id
			if deviceType == kTemperatureDevice or deviceType == kVoltageDevice or deviceType == kPulseSensorDevice:
				device_dict["SupportsOnState"] = False
				device_dict["SupportsSensorValue"] = True
				device_dict["SupportsStatusRequest"] = False
				device_dict["AllowOnStateChange"] = False
				device_dict["AllowSensorValueChange"] = False
			else:
				device_dict["SupportsEnergyMeter"] = True
				device_dict["SupportsEnergyMeterCurPower"] = True
				device_dict["SupportsSensorValue"] = True
				device_dict["SupportsStatusRequest"] = False
				device_dict["AllowSensorValueChange"] = False
			newdev.replacePluginPropsOnServer(device_dict)

		cursor.close()
		conn.close()

		return valuesDict

	def removeAllDevices(self, valuesDict, devIdList):
		for devId in devIdList:
			try:
				indigo.device.delete(devId)
			except:
				pass  # delete doesn't allow (throws) on root elem
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
