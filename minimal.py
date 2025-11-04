import base64
import time
import asyncio
import aiohttp
import logging

'''
Initial version drawing heavily from: https://github.com/SunStrong-Management/pypvs
'''

logging.basicConfig(level=logging.DEBUG)

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

    async def _post(self, data, headers=""):
        '''
        Make a POST request to the PVS device

        TODO: Some of the error handling is incorrect since invalid names are reported below as being invalid login

        TODO: Add retry logic for login if cookie expired
        '''
        logging.debug(f"Post:url={self._url} data={data} headers={headers} cookies={self._cookies}")
        async with self.session.post(self._url, data=data, headers=headers, cookies=self._cookies, ssl=False) as response:
            if response.status != 200:
                logging.error(f"Request failed with status code: {response.status}")
            else:
                response_json = await response.json()

            logging.debug(f"Response: {response_json}")
            if response.status == 200:
                return response_json
            elif response.status in [400, 401, 500]:
                logging.error("Unauthorized access (missing cookie). Retry login!")
                raise RuntimeError("Unauthorized access (missing cookie). Retry login!")
            else:
                raise RuntimeError(f"POST request failed with status code: {response.status}")

    async def _get_serial_number(self):
        ''' Get the serial number of the PVS device and assign the password '''
        serial_response = await self._post(data="name=/sys/info/serialnum")
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

async def test():
    async with aiohttp.ClientSession() as session:
        pvs= PVS(session)
        await pvs.initialize()
        await pvs._post(data="name=/sys/info/uptime")
        await pvs._post(data="match=/sys/livedata")
        await pvs._post(data="match=/sys/devices/meter")
        await pvs._post(data="match=/sys/devices/inverter")
        #await pvs._post(data="name=/sys/devices/meter/0/ctSclFctr")
        await pvs._post(data="name=/sys") # Everything is under /sys and you can indeed get everthing in one go!
        
asyncio.run(test())
