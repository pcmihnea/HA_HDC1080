# What?
HomeAssistant integration of a Texas Instruments HDC1080 Temperature/Humidity Evaluation Module (EVM).  
With a few modifications, may also work on similar devices from their [Sensing Solutions EVM range](https://www.ti.com/lit/zip/snoc028).  
 
# Why?
By design, the evaluation board works with the official software only. 
As such, no documentation regarding third-party integration is readily available - the information contained in this repo is obtained via reverse-engineering efforts.  
Once the minimal communication protocol (for sampling temperature/humidity) is known, the board is easy to connect locally to a HomeAssistant instance, due to its USB port.

# How?

## 1. Determine communication protocol
- Once connected, the device enumerates as a USB CDC, i.e. a virtual COM (serial) port (with parameters 115200, 8N1) - driver installation may be required on Windows (Linux has native support on modern kernels).  
- (Optional) A firmware update may be required, as each compatible sensor requires a specific binary flash image:
	- Login/register onto [TI.com](www.ti.com), then download the **WINDOWS-ONLY** [Sensing Solutions EVM GUI](https://www.ti.com/lit/zip/snoc028) - it may be necessary to rename the downloaded file from `snoc028f` to `snoc028f.zip`  
	- After installation, run the software, and using the `Firmware` tab accesible from top-left menu, update to the appropiate firmware file, i.e. `C:\ti\Sensing Solutions EVM GUI-1.10.0\EVM Firmware\HDC10x0\HDC10x0_EVM_Firmware.txt`
- The board expects commands (i.e. host PC -> board) and responds (board -> PC) on a fixed payload structure - this document displays the raw bytes as hex-coded, little-endian:
	- To read the value of a internal register, a command is formed as `HEADER[4] TYPE[2] ADDR[1] VALUE[2] CRC[1]`, with the response `HEADER[4] TYPE[2] ADDR[1] VALUE[2] CRC1[1] PAD[11] CRC2[1]`, where:
		- [i] = i number of bytes
		- `HEADER` = always `0x4c330100`  
		- `TYPE` = `0x340` for a register read command, `0x440` for a register read response,  
		- `ADDR` = address of the sensor's internal register - for HDC1080 most notable are:  
			- `0x00` holds the current temperature measurement raw value,  
			- `0x01` holds the humidity value  
		- `VALUE` = always `0x02` in a read register command, while in the response it contains the actual value stored in the requested register,  
		- `PAD` = padding, all null bytes (`0x00`) - a command contains no padding, while a response uses 11-bytes,  
		- `CRC`, `CRC1`, `CRC2` = CRC8 checksum of all the payload bytes - `CRC1` is equal to `CRC2`
	- To request the temperature value, send `0x4c3301000340000287` as raw binary, while for humidity send `0x4c3301000340010292`
	- The board will send after each request the actual value, so only each command shall be sent only after a response was received
	- The raw values need to be converted to obtain the physical value:  
		- `temperature_value = round((register_value * 165) / 65536 - 40, 3)`
		- `humidity_value = round((register_value * 100) / 65536, 3)`
	- For example, a response payload of `0x4c33010004400062f8a60000000000000000000000a6` contains the temperature value of 23.788°C, while `0x4c3301000440019b8417000000000000000000000017` shows that humidity is at 60.748%

## 2. Configure the data relay
Since the Python script relies on non-standard libraries, a [Home Assistant Docker installation](https://www.home-assistant.io/installation/linux#install-home-assistant-container) is assumed to be already working.  
Also, a MQTT broker (for example Mosquitto) is also [installed](https://mosquitto.org/download), [configured](https://mosquitto.org/man/mosquitto-conf-5.html) and [accesible in HA](https://www.home-assistant.io/docs/mqtt/broker).  

- Install the required python libraries: `sudo pip install paho_mqtt crccheck pyserial`  
- Since the board is identified as a USB-to-serial port, at device plug-in and system restart, the `COM*` port (Windows) or console name `/dev/tty\*` (Linux) could be randomly (re)assigned - as such a static name should be set:  
	- (Windows) The assigned COM port, if the device is plugged-in into the same USB port, should not be changed automatically by the OS - check `Device Manager` in the `Control Panel`  
	- (Linux) Static assignments of console names is distribution specific, for example in Debian (Raspbian) add the following line in `/etc/udev/rules.d/99-com.rules`:  
		`SUBSYSTEM=='tty', ATTRS{idVendor}=='2047', ATTRS{idProduct}=='08f8', ATTRS{serial}=='0123456789ABCDEF', SYMLINK+='ttyPMV0'`, where:  
			- `0123456789ABCDEF` = the board's unique serial number, that can be obtained by running `lsusb -v` and scrolling to the device with attribute `idProduct`=`FDC2x14/LDC13xx/LDC16xx EVM`, and noting its `iSerial` attribute's value  
			- `ttyPMV0` = the console name to be static assigned - to be entered in the parameter `LINUX_SERIAL_PORT` at the following step  
- Edit the `mqtt_hdc1080.py` file by configuring the user-specific values accordingly to the used MQTT broker (`MQTT_HOSTNAME`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_CLIENT_ID`), serial port (`WIN_SERIAL_PORT` for Windows, `LINUX_SERIAL_PORT` for Linux), and sampling period (`SAMPLE_INTERVAL`)  
- Run the Python script as root: `sudo python3 mqtt_hdc1080.py`  
- (Optional) Configure the script to run at startup, for example by adding it to `/etc/rc.local`  

## 3. Configure the HomeAssistant instance

- Add the following lines in `configuration.yaml` file (present inside the user-defined `homeassistant` configuration folder).  
Take note of the `state_topic` value, where `hdc1080` is a example that shall be subtituted with the exact value of `MQTT_CLIENT_ID` parameter set at step 2.

```
sensor:
  - platform: mqtt
    name: TEMP
    unique_id: "hdc1080_temp"
    state_topic: "hdc1080/sensors/values"
    value_template: "{{ value_json.TEMP }}"
    device_class: temperature
    unit_of_measurement: "°C"
  - platform: mqtt
    name: HUMID
    unique_id: "hdc1080_humid"
    state_topic: "hdc1080/sensors/values"
    value_template: "{{ value_json.HUMID }}"
    device_class: humidity
    unit_of_measurement: "%"
```
- If all is well, after a HA restart the newly created sensors shall be available.


# Who/where/when?
All the reverse-engineering, development, integration, and documentation efforts are based on the latest software and hardware versions available at the time of writing (February 2022), and licensed under the GNU General Public License v3.0.
