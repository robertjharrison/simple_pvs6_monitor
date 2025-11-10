import os
import asyncio
import aiohttp
import pvs_simple
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

bucket = "test3"
token = os.environ.get("INFLUXDB_TOKEN")
org = "Hoime"
url = "http://192.168.5.8:8086"
# Store the URL of your InfluxDB instance                                                                                                                                                          

client = influxdb_client.InfluxDBClient(
    url=url,
    token=token,
    org=org
)

write_api = client.write_api(write_options=SYNCHRONOUS)
async def push_to_influxdb(interval=60):
    '''                                                                                                                                                                                                
    Template for data

    timestamp
      for device in system and all inverters
      tag device
        field kWh lifetime energy
        field kW current power
        field C  current temperature
    '''
    
    async with aiohttp.ClientSession() as session:
        pvs = pvs_simple.PVS(session)
        await pvs.initialize()
        while True:
            data = await pvs._post(data="match=/sys")
            inverters = pvs_simple.Inverters(data)
            livedata = pvs_simple.LiveData(data)
            print(livedata.get_data())
            for id in range(inverters.num_devices()):
                print(inverters.get_data(id))

            await asyncio.sleep(interval)
    

if __name__ == "__main__":
    asyncio.run(push_to_influxdb(10))
