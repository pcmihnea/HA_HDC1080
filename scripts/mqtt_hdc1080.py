import json
import logging
import os
import struct
import time

import paho.mqtt.publish as publish
import serial
from crccheck.crc import Crc8

MQTT_HOSTNAME = '192.168.0.2'
MQTT_USERNAME = '_USERNAME_'
MQTT_PASSWORD = '_PASSWORD_'
MQTT_CLIENT_ID = 'hdc1080'
SERIAL_PORT_LINUX = '/dev/ttyPMV0'
SERIAL_PORT_WIN = 'COM1'

SAMPLE_INTERVAL = 30
TIMEOUT_SEC = 5

ADDR_TEMP = 0x00
ADDR_HUMID = 0x01
PACKET_HEADER = [0, 0x4c330100]
PACKET_TYPE = [1, [0x340, 0x440]]  # REQ, RESP
PACKET_ADDR = [2, [ADDR_TEMP, ADDR_HUMID]]
PACKET_VALUE = 3
PACKET_CRC1 = 4
PACKET_CRC2 = 5
PACKET_DATA_LEN = 9
PACKET_LEN = 22


def serial_req(addr):
    try:
        tx_data = bytearray(
            struct.pack('>LHBBB', PACKET_HEADER[1], PACKET_TYPE[1][0], PACKET_ADDR[1][addr], 0x02, 0x00))
        tx_data[-1] = Crc8.calc(tx_data[:-1])
        rx_data = []

        ser.flushInput()
        ser.write(tx_data)
        timeout = time.time() + TIMEOUT_SEC
        while ser.is_open and time.time() < timeout:
            time.sleep(0.1)
            if ser.inWaiting() > 0:
                rx_data += ser.read(ser.inWaiting())
                if len(rx_data) >= PACKET_LEN:
                    if len(rx_data) == PACKET_LEN:
                        data_elems = struct.unpack('>LHBHBxxxxxxxxxxxB', bytearray(rx_data))
                        if data_elems[PACKET_HEADER[0]] == PACKET_HEADER[1] and \
                                data_elems[PACKET_TYPE[0]] == PACKET_TYPE[1][1] and \
                                data_elems[PACKET_ADDR[0]] in PACKET_ADDR[1] and \
                                data_elems[PACKET_CRC1] == data_elems[PACKET_CRC2] and \
                                data_elems[PACKET_CRC1] == Crc8.calc(rx_data[0:PACKET_DATA_LEN]):
                            if data_elems[PACKET_ADDR[0]] == PACKET_ADDR[1][0]:
                                SENSOR_VALUES['TEMP'] = round((data_elems[PACKET_VALUE] * 165) / 65536 - 40, 3)
                            elif data_elems[PACKET_ADDR[0]] == PACKET_ADDR[1][1]:
                                SENSOR_VALUES['HUMID'] = round((data_elems[PACKET_VALUE] * 100) / 65536, 3)
                    ser.flushInput()
                    break
    except Exception:
        logging.exception('EXCEPTION')
        raise Exception


if __name__ == '__main__':
    try:
        SENSOR_VALUES = {'TEMP': 0, 'HUMID': 0}

        time.sleep(TIMEOUT_SEC)
        if os.name == 'nt':
            SERIAL_PORT = SERIAL_PORT_WIN
        elif os.name == 'posix':
            SERIAL_PORT = SERIAL_PORT_LINUX
        else:
            raise Exception
        ser = serial.Serial(SERIAL_PORT, 115200, timeout=TIMEOUT_SEC)
        while ser.is_open:
            start_time = time.time()
            serial_req(ADDR_TEMP)
            serial_req(ADDR_HUMID)
            try:
                publish.single(MQTT_CLIENT_ID + '/sensors/values',
                               payload=json.dumps(SENSOR_VALUES),
                               hostname=MQTT_HOSTNAME,
                               port=1883, client_id=MQTT_CLIENT_ID,
                               auth={'username': MQTT_USERNAME, 'password': MQTT_PASSWORD})
            except Exception:
                pass
            time.sleep(SAMPLE_INTERVAL - (time.time() - start_time))
    except Exception:
        logging.exception('EXCEPTION')
    finally:
        try:
            ser.close()
        except Exception:
            pass
