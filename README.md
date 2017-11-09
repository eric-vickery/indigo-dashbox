Brultech Dashbox Plugin
=======================
The Brultech Dashbox plugin loads power data from a [Brultech Dashbox](http://www.brultech.com) to [Indigo](http://www.perceptiveautomation.com).

This plugin (and Readme) is a work in progress.

This code is tested with Dashbox 4.2.3 and Indigo 7.1.0.

Please report issues through Github.

### Installation instructions
1. Download the (zip archive of the) plugin [here](https://github.com/eric-vickery/indigo-dashbox/releases)
2. Install [pg8000](https://github.com/mfenniak/pg8000) by typing the command `pip install pg8000` in a terminal.
3. Install [requests](http://docs.python-requests.org/en/master/) by typing the command `pip install requests` in a terminal.
4. Follow the Indigo [plugin installation instructions](http://wiki.indigodomo.com/doku.php?id=indigo_7_documentation:getting_started#installing_plugins_configuring_plugin_settings_permanently_removing_plugins)

When you have Indigo installed the plugin folder will show as a single file (a package).
When you doubleclick on the file you will automatically open Indigo (or bring it to the front) and you will be asked if you want to install and enable it.

### Configuring the Dashbox
You will need to set a password for the batabase backup (if you haven't already). The database backup user is used by the plugin to retreive some of the information about the channels. This is readonly and nothing is ever written to the Dashbox from teh plugin. You set the password by going to Settings->System->Backup Settings

### Connect to the Dashbox
When enabling the plugin you will need to provide the following:
* Hostname or IP address of the Dashbox
* Password for the backup user (configured above)

### Include devices
All the channels that are not hidden on the Dashbox will have devices created for them when you enable the plugin. The names will be the names of the channels as defined on the Dashbox. If you change what channels are enabled on the Dashbox you will need to reload the devices (see below).

### Using triggers, actions etc.
TBD
When you are at this point the device behaves similar to what you are used to in Indigo so I am not going to spend many more words than necessary here. Triggers, actions etc. are defined based on what is available for a sensor in MySensors. So this is pretty standard stuff. When you miss something that is available in MySensors but not in the plugin you can either let me know or fork the master and add it yourself (and commit the changes so that I can review and add them).

### Menu Items
The following menu items are available:

##### Reload Devices
This will delete all the devices created by the plugin.
Three words of advice here:
* Don't do this unless you are asked to when you are unsure.
* If the channel names were changed on the Dashbox this could cause Triggers and actions to quit working correctly.

### FreeBSD License
Copyright (c) 2017, Eric Vickery
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The views and conclusions contained in the software and documentation are those
of the authors and should not be interpreted as representing official policies,
either expressed or implied, of the FreeBSD Project.