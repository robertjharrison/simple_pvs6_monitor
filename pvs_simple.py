import base64
import time
import asyncio
import aiohttp
import logging
import json
import datetime

'''
Initial version drawing heavily from: https://github.com/SunStrong-Management/pypvs
'''

logging.basicConfig(level=logging.INFO,
                    filename="pvslog.txt",
                    filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

class PVS:
    '''
        Class to interact with PVS device
    '''
    _user = "ssm_owner"
    _host = "192.168.4.101" # Replace with your PVS device IP address

    _url = f"https://{_host}/vars" # Endpoint for variable requests
    _login_url = f"https://{_host}/auth?login" # Endpoint for login requests

    _cookies = ""
    _password = ""
    _serial = ""

    def __init__(self, session):
        ''' Initialize PVS class with aiohttp session '''
        self.session = session

    async def initialize(self):
        ''' Initialize the PVS device by getting serial number and logging in '''
        await self._get_serial_number()
        await self._login()

    def log(self, message):
        logging.info(message)

    async def post(self, data, headers=""):
        '''
        Make a POST request to the PVS device
        '''
        logging.debug(f"Post:url={self._url} data={data} headers={headers} cookies={self._cookies}")
        MAX_ATTEMPTS = 3
        for attempts in range(MAX_ATTEMPTS):
            async with self.session.post(self._url, data=data, headers=headers, cookies=self._cookies, ssl=False) as response:
                if response.status == 200:
                    logging.debug("Request successful")
                    response_json = await response.json()
                    logging.debug(f"Response: {response_json}")
                    return response_json
                else:
                    logging.error("Possible unauthorized access (missing cookie) or possible malformed request or server error. Status code: {response.status}. Retrying login!")
                    await asyncio.sleep(30) 
                    await self._login()
                    continue
        else:
            logging.error("Server error after retrying login. Aborting.")
            raise RuntimeError("Server error after retrying login")

    async def _get_serial_number(self):
        ''' Get the serial number of the PVS device and assign the password '''
        serial_response = await self.post(data="name=/sys/info/serialnum")
        self._serial = serial_response["values"][0]["value"]
        self._password = self._serial[-5:]
        return self._serial

    async def _login(self):
        ''' Login to the PVS device and store the session cookies for future requests'''
        token = base64.b64encode(f"{self._user}:{self._password}".encode("utf-8")).decode()
        headers = {"Authorization": f"basic {token}"}

        async with self.session.get(self._login_url, headers=headers, ssl=False) as response:
            if response.status != 200:
                logging.error(f"Login failed with status code: {response.status} and response: {response.text}")
                raise RuntimeError("Login failed")

        self._cookies = response.cookies            
        logging.info(f"Login successful! with cookies: {self._cookies}")

class Devices(object):
    ''' Class to extract and manage data from devices with multiple instances like meters and inverters '''
    def __init__(self, data, data_info, device_type):
        ''' Initialize with data being response from PVS devices matching /sys/devices/device_type/ '''
        self.device_type = device_type
        self.data_info = data_info
        self.devices = {}
        for item in data['values']:
            name = item['name']
            if f'/sys/devices/{self.device_type}/' in name:
                parts = name.split('/')
                device_id = int(parts[4])
                if device_id not in self.devices:
                    self.devices[device_id] = {}

                try:
                    value = float(item['value'])
                except ValueError:
                    value = item['value']

                prop_name = parts[5]
                self.devices[device_id][prop_name] = value

        logging.info(f"Found {len(self.devices)} {self.device_type}s.")

    def num_devices(self):
        ''' Return number of devices detected '''
        return len(self.devices)

    def print_properties(self):
        for device_id, properties in sorted(self.devices.items()):
            print(f"\n--- {self.device_type} {device_id} ---")
            for prop_name, prop_value in properties.items():
                try:
                    long_name = self.data_info[prop_name][1]
                except KeyError:
                    long_name = "Unknown property"

                print(f"  {long_name:>50}: {prop_value}")

class Inverters(Devices):
    data_info = {
        "freqHz"        : [float,"Frequency in Hz dectected by inverter"],
        "i3phsumA"      : [float,"Sum of phase currents in A"],
        "iMppt1A"       : [float,"Current of MPPT1 in A"],
        "ltea3phsumKwh" : [float,"Lifetime sum of 3-phase energy in kWh"],
        "msmtEps"       : [str,  "Timestamp of the last measurement"],
        "p3phsumKw"     : [float,"Sum of 3-phase power in kW"],
        "pMppt1Kw"      : [float,"Power of MPPT1 in kW"],
        "prodMdlNm"     : [str,  "Product model name"],
        "sn"            : [str,  "Serial number of the inverter"],
        "tHtsnkDegc"    : [int,  "Temperature of the heat sink in °C"],
        "vMppt1V"       : [float,"Voltage of MPPT1 in V"],
        "vln3phavgV"    : [float,"Avg voltage of 3-phase system V"]
    }

    def get_data(self, devicenum):
        ''' Return lifetime energyin kWh, current power in kW, and current temperature in °C '''
        return self.devices[devicenum]["ltea3phsumKwh"], self.devices[devicenum]["p3phsumKw"], self.devices[devicenum]["tHtsnkDegc"]

    def __init__(self, data):
        super().__init__(data, self.data_info, "inverter")
                    
class Meters(Devices):
    data_info = {
        "ctSclFctr"        : [int,"CT scaling factor"],
        "freqHz"           : [float,"Frequency in Hz"],
        "i1A"              : [float,"Current in A for phase 1"],
        "i2A"              : [float,"Current in A for phase 2"],
        "msmtEps"          : [str,"Timestamp of the last measurement"],
        "negLtea3phsumKwh" : [float,"Negative lifetime sum of 3-phase energy in kWh"],
        "netLtea3phsumKwh" : [float,"Net lifetime sum of 3-phase energy in kWh"],
        "p1Kw"             : [float,"Power in kW for phase 1"],
        "p2Kw"             : [float,"Power in kW for phase 2"],
        "p3phsumKw"        : [float,"Sum of 3-phase power in kW"],
        "posLtea3phsumKwh" : [float,"Positive lifetime sum of 3-phase energy in kWh"],
        "prodMdlNm"        : [str,"Product model name"],
        "q3phsumKvar"      : [float,"Sum of 3-phase reactive power in kVar"],
        "s3phsumKva"       : [float,"Sum of 3-phase apparent power in kVA"],
        "sn"               : [str,"Serial number of the meter"],
        "totPfRto"         : [float,"Total power factor ratio"],
        "v12V"             : [float,"Voltage between phase 1 and 2 in V"],
        "v1nV"             : [float,"Voltage between phase 1 and neutral in V"],
        "v2nV"             : [float,"Voltage between phase 2 and neutral in V"]
    }

    def __init__(self, data):
        super().__init__(data, self.data_info, "meter")

class LiveData:
    ''' Class to extract and manage live data from PVS device '''

    data_info = {
        "time" : [int,"Telemetry Websockets timestamp"],
        "pv_p" : [float,"Production Power (kW)"],
        "pv_en" : [float,"Production Energy (kWh)"],
        "net_p" : [float,"Net Consumption Power (kW)"],
        "net_en" : [float,"Net Consumption Energy (kWh)"],
        "site_load_p" : [float,"Site Load Power (kW)"],
        "site_load_en" : [float,"Site Load Energy (kWh)"],
        "ess_en" : [float,"Battery Energy (kWh)"],
        "ess_p" : [float,"Battery Power (kW)"],
        "soc" : [float,"Battery State of Charge (%)"],
        "backupTimeRemaining" : [int,"Battery Backup Time Remaining (minutes)"],
        "midstate" : [int,"MID State"]
        }
    
    def __init__(self, data):
        ''' Initialize with response from PVS device matching /sys/livedata/ '''
        self.live_data = {}
        for item in data['values']:
            name = item['name']
            if '/sys/livedata/' in name:
                parts = name.split('/')
                data_key = parts[3]

                try:
                    value = float(item['value'])
                except ValueError:
                    value = item['value']

                self.live_data[data_key] = value

    def get_data(self):
        ''' Return timestamp in Zulu, lifetime energy in kWh, current power in kW'''
        dt_object_utc = datetime.datetime.fromtimestamp(self.live_data['time'], tz=datetime.timezone.utc)
        zulu_time_str = dt_object_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        return zulu_time_str, self.live_data["pv_en"], self.live_data["pv_p"]

    def print_properties(self):
        for data_key, data_value in sorted(self.live_data.items()):
            try:
                long_name = self.data_info[data_key][1]
            except KeyError:
                long_name = "Unknown property"

            print(f"  {long_name:>50}: {data_value}")

async def test():
    async with aiohttp.ClientSession() as session:
        pvs= PVS(session)
        await pvs.initialize()
        # await pvs.post(data="name=/sys/info/uptime")
        # await pvs.post(data="match=/sys/livedata")
        # await pvs.post(data="match=/sys/devices/meter")
        # await pvs.post(data="match=/sys/devices/inverter")
        #await pvs.post(data="name=/sys/devices/meter/0/ctSclFctr")

        data = await pvs.post(data="match=/sys") # Everything is under /sys and you can indeed get everthing in one go!

        inverters = Inverters(data)
        inverters.print_properties()

        livedata = LiveData(data)
        livedata.print_properties()

        meters = Meters(data)
        meters.print_properties()

if __name__ == "__main__":
    asyncio.run(test())
