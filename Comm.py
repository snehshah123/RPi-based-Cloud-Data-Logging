from pymodbus.client import ModbusSerialClient as ModbusClient
import time

def read_modbus_data():

    client = ModbusClient(method="rtu", port="/dev/ttyUSB0", baudrate=9600, timeout=2, parity='N', stopbits=1, bytesize=8)
    client.connect()
   
    result = client.read_holding_registers(address = 0 , count = 8 , slave = 1)
    sensor_data = result.registers
    client.close() 
   
    return sensor_data

rr = read_modbus_data()
print(rr)