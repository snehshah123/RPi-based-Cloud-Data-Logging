import os
import csv
import datetime
import time
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from pymodbus.client import ModbusSerialClient as ModbusClient

def authenticate_google_drive():
    try:
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("credentials.json")
        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()
        gauth.SaveCredentialsFile("credentials.json")

        drive = GoogleDrive(gauth)
        return drive
    except Exception as e:
        print(f"Error during Google Drive authentication: {e}")
        return None

def create_directory():
    today_date = datetime.date.today().strftime("%d-%m-%y")
    directory_path = os.path.join("Scanner_Files", today_date)
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
    return directory_path

def write_to_csv(directory_path, data, start_date):
    csv_file_path = os.path.join(directory_path, f'{start_date}.csv')
    file_exists = os.path.isfile(csv_file_path)
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Date', 'Time', 'CH01', 'CH02', 'CH03', 'CH04', 'CH05', 'CH06', 'CH07', 'CH08'])
        writer.writerow(data)
    return csv_file_path

def upload_to_google_drive(drive, file_path, folder_id):
    try:
        file_drive = drive.CreateFile({'title': os.path.basename(file_path), 'parents': [{'id': folder_id}]})
        file_drive.SetContentFile(file_path)
        file_drive.Upload()
        print(f'File {os.path.basename(file_path)} uploaded to Google Drive.')
    except Exception as e:
        print(f"Error uploading to Google Drive: {e}")

def save_calibration_settings(settings):
    with open('calibration_settings.txt', 'w') as file:
        for key, value in settings.items():
            file.write(f'{key}:{value}\n')
    print("Calibration settings saved.")

def load_calibration_settings():
    settings = {}
    try:
        with open('calibration_settings.txt', 'r') as file:
            for line in file:
                parts = line.strip().split(':', 1)
                if len(parts) == 2:
                    key, value = parts
                    settings[key] = value
                else:
                    print(f"Skipping malformed line in calibration settings: {line.strip()}")

        return settings
    except FileNotFoundError:
        print("Calibration settings not found. Please run 'calibrate' command first.")
        return None
    except ValueError as ve:
        print(f"Error loading calibration settings: {ve}")
        return None

def read_modbus_data():
    client = ModbusClient(method="rtu", port="/dev/ttyUSB0", baudrate=9600, timeout=2, parity='N', stopbits=1, bytesize=8)
    client.connect()

    result = client.read_holding_registers(address = 0 , count = 8 , slave = 1)
    client.close()

    if result.isError():
        print("Error reading Modbus registers")
        return None
    return result.registers

def start_logging():
    settings = load_calibration_settings()
    if settings is None:
        return

    start_datetime_str = f"{settings['start_date']} {settings['start_time']}"
    stop_datetime_str = f"{settings['stop_date']} {settings['stop_time']}"
    log_interval = int(settings['log_interval'])
    folder_id = settings['folder_id']

    start_datetime = datetime.datetime.strptime(start_datetime_str, '%d-%m-%Y %H:%M:%S')
    stop_datetime = datetime.datetime.strptime(stop_datetime_str, '%d-%m-%Y %H:%M:%S')

    print(f"Current time: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")
    print(f"Logging will start at: {start_datetime_str}")
    while datetime.datetime.now() < start_datetime:
        time.sleep(1)

    print("Starting data logging...")
    drive = authenticate_google_drive()
    if not drive:
        print("Google Drive authentication failed. Exiting.")
        return

    directory_path = create_directory()

    while datetime.datetime.now() <= stop_datetime:
        current_time = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        date = datetime.datetime.now().strftime('%d-%m-%Y')
        time_now = datetime.datetime.now().strftime('%H:%M:%S')

        sensor_data = read_modbus_data()
        if sensor_data is None:
            print(f"Skipping logging at {current_time} due to sensor read failure.")
            time.sleep(log_interval)
            continue

        data_row = [date, time_now] + sensor_data
        write_to_csv(directory_path, data_row, settings['start_date'])
        print(f"Data logged at {current_time}: {sensor_data}")
        time.sleep(log_interval)

    csv_file_path = os.path.join(directory_path, f"{settings['start_date']}.csv")
    upload_to_google_drive(drive, csv_file_path, folder_id)
    print("Data logging completed and file uploaded.")

def calibrate():
    try:
        print("Enter the following recording time settings:")
        start_time = input("Start Time (HH:MM:SS): ")
        start_date = input("Start Date (DD-MM-YYYY): ")
        stop_time = input("Stop Time (HH:MM:SS): ")
        stop_date = input("Stop Date (DD-MM-YYYY): ")
        log_interval = input("Log Interval (in seconds): ")
        folder_id = input("Google Drive Folder ID: ")

        settings = {
            'start_time': start_time,
            'start_date': start_date,
            'stop_time': stop_time,
            'stop_date': stop_date,
            'log_interval': log_interval,
            'folder_id': folder_id
        }
        save_calibration_settings(settings)
    except Exception as e:
        print(f"Error during calibration: {e}")

def main():
    while True:
        try:
            command = input("Enter 'calibrate', 'start' to log data, or 'quit' to exit: ").lower()
            if command == 'calibrate':
                calibrate()
            elif command == 'start':
                start_logging()
            elif command == 'quit':
                break
            else:
                print("Invalid command.")
        except KeyboardInterrupt:
            print("Exiting program.")
            break

if __name__ == '__main__':
    main()