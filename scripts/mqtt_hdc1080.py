import json
import logging
import struct
import time

import paho.mqtt.publish as publish
import serial
from crccheck.crc import Crc8

SERIAL_TIMEOUT = 5
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

SENSOR_VALUES = {'TEMP': 0, 'HUMID': 0}


def serial_req(addr):
    try:
        tx_data = bytearray(
            struct.pack('>LHBBB', PACKET_HEADER[1], PACKET_TYPE[1][0], PACKET_ADDR[1][addr], 0x02, 0x00))
        tx_data[-1] = Crc8.calc(tx_data[:-1])
        rx_data = []

        ser.flushInput()
        ser.write(tx_data)
        timeout = time.time() + SERIAL_TIMEOUT
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
                                SENSOR_VALUES['TEMP'] = round((data_elems[PACKET_VALUE] * 165.0) / 65536.0 - 40.0, 3)
                            elif data_elems[PACKET_ADDR[0]] == PACKET_ADDR[1][1]:
                                SENSOR_VALUES['HUMID'] = round((data_elems[PACKET_VALUE] * 100.0) / 65536.0, 3)
                    ser.flushInput()
                    break
    except Exception:
        logging.exception('EXCEPTION')


def mqtt_publish(topic, payload, retain):
    publish.single(hostname=PRIVATE_CONFIG['MQTT']['HOSTNAME'], port=1883, client_id='hdc1080',
                   auth={'username': PRIVATE_CONFIG['MQTT']['USERNAME'],
                         'password': PRIVATE_CONFIG['MQTT']['PASSWORD']},
                   topic=topic, payload=json.dumps(payload), retain=retain)


if __name__ == '__main__':
    ser = serial.Serial()
    try:
        f = open('private_config.json')
        PRIVATE_CONFIG = json.load(f)
        f.close()
        if bool(PRIVATE_CONFIG['MQTT']) and bool(PRIVATE_CONFIG['HDC1080']):
            pass
        ser = serial.Serial(PRIVATE_CONFIG['HDC1080']['SERIAL_PORT'], 115200, timeout=SERIAL_TIMEOUT)
        mqtt_publish('homeassistant/sensor/HDC1080_T/config',
                     {"name": 'HDC1080_T',
                      "state_topic": 'homeassistant/sensor/HDC1080/state',
                      "value_template": '{{ value_json.TEMP }}',
                      "device_class": 'temperature', "unit_of_measurement": '°C'},
                     True)
        mqtt_publish('homeassistant/sensor/HDC1080_H/config',
                     {"name": 'HDC1080_H',
                      "state_topic": 'homeassistant/sensor/HDC1080/state',
                      "value_template": '{{ value_json.HUMID }}',
                      "device_class": 'humidity', "unit_of_measurement": '%'},
                     True)
        while ser.is_open:
            start_time = time.time()
            serial_req(ADDR_TEMP)
            serial_req(ADDR_HUMID)
            mqtt_publish('homeassistant/sensor/HDC1080/state', SENSOR_VALUES, False)
            time.sleep(PRIVATE_CONFIG['HDC1080']['SAMPLE_INTERVAL'] - (time.time() - start_time))
    except Exception:
        logging.exception('EXCEPTION')
    try:
        ser.close()
    except Exception:
        pass
