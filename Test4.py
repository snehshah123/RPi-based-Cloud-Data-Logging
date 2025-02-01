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

def create_directory(today_date):
    directory_path = os.path.join("Scanner_Files", today_date)
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
    return directory_path

def write_to_csv(directory_path, today_date, data):
    csv_file_path = os.path.join(directory_path, f'{today_date}.csv')

    file_exists = os.path.isfile(csv_file_path)
    with open(csv_file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Date', 'Time', 'CH01', 'CH02', 'CH03', 'CH04', 'CH05', 'CH06', 'CH07', 'CH08'])
        writer.writerow(data)
    return csv_file_path

def upload_to_google_drive_as_sheet(drive, file_path, folder_id):
    try:
        # Search for a file with the same name (today's date) in the folder
        file_list = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()
        existing_file = None

        for file in file_list:
            if file['title'] == os.path.basename(file_path).replace('.csv', ''):
                existing_file = file
                break
       
        if existing_file:
            # If file exists, update its content
            print(f"Google Sheet {os.path.basename(file_path)} already exists. Overwriting...")
            file_drive = drive.CreateFile({'id': existing_file['id']})
        else:
            # If file does not exist, create a new one as a Google Sheet
            file_drive = drive.CreateFile({
                'title': os.path.basename(file_path).replace('.csv', ''),
                'parents': [{'id': folder_id}],
                'mimeType': 'text/csv'
                #'mimeType': 'application/vnd.google-apps.spreadsheet'
            })
       
        file_drive.SetContentFile(file_path)
        file_drive.Upload({'convert': True})
        print(f'File {os.path.basename(file_path)} converted to Google Sheets')
        
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
        print("Calibration settings not found.")
        return None
    except ValueError as ve:
        print(f"Error loading calibration settings: {ve}")
        return None

def read_modbus_data():
    client = ModbusClient(method="rtu", port="/dev/ttyUSB0", baudrate=9600, timeout=2, parity='N', stopbits=1, bytesize=8)
    client.connect()

    result = client.read_holding_registers(address=0, count=8, slave=1)
    client.close()

    if result.isError():
        print("Error reading Modbus registers")
        return None
    return result.registers

def start_logging():
    settings = load_calibration_settings()
    if settings is None:
        return

    log_interval = int(settings['log_interval'])
    folder_id = settings['folder_id']
    division_factor = float(settings['division_factor'])

    print("Starting continuous data logging...")
    drive = authenticate_google_drive()
    if not drive:
        print("Google Drive authentication failed. Exiting.")
        return

    # Initialize the date for file creation
    current_date = datetime.date.today().strftime('%d-%m-%y')
    directory_path = create_directory(current_date)

    while True:
        # Check if the date has changed
        new_date = datetime.date.today().strftime('%d-%m-%y')
        if new_date != current_date:
            # Create a new directory and file for the new date
            current_date = new_date
            directory_path = create_directory(current_date)
            print(f"Date changed to {current_date}. New file created.")

        current_time = datetime.datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        date = datetime.datetime.now().strftime('%d-%m-%Y')
        time_now = datetime.datetime.now().strftime('%H:%M:%S')

        sensor_data = read_modbus_data()
        if sensor_data is None:
            print(f"Skipping logging at {current_time} due to sensor read failure.")
            time.sleep(log_interval)
            continue

        # Apply division factor and check for values greater than 4000
        modified_data = [(0 if value > 4000 else value / division_factor) for value in sensor_data]

        data_row = [date, time_now] + modified_data
        csv_file_path = write_to_csv(directory_path, current_date, data_row)
        print(f"Data logged at {current_time}: {modified_data}")

        # Upload the CSV file as a Google Sheet
        upload_to_google_drive_as_sheet(drive, csv_file_path, folder_id)

        time.sleep(log_interval)

if __name__ == '__main__':
    start_logging()