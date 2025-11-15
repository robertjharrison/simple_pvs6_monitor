import os
import asyncio
import aiohttp
import pvs_simple
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

bucket = "PVS"
token = os.environ.get("INFLUXDB_TOKEN")
org = "Hoime"
url = "http://192.168.5.8:8086"

client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

def record_device(timestamp, device, energy, power, temp):
    p = influxdb_client.Point("PVS6").tag("device", device).time(timestamp).field("kWh", energy).field("kW", power).field("C",temp)
    write_api.write(bucket=bucket, org=org, record=p)

async def push_to_influxdb(interval=60):
    '''                                                                                                                                    Template for data

    for device in livedata and all inverters
      tag device
        field kWh lifetime energy
        field kW current power
        field C  current temperature
    '''

    async with aiohttp.ClientSession() as session:
        pvs = pvs_simple.PVS(session)
        await pvs.initialize()
        while True:
            data = await pvs.post(data="match=/sys")

            livedata = pvs_simple.LiveData(data)
            device = "system"
            timestamp, energy, power = livedata.get_data()
            temp = 0.0
            record_device(timestamp, device, energy, power, temp)            
            print(timestamp, f"Recorded system: kWh={energy} kW={power}")
            system_power = power

            inverters = pvs_simple.Inverters(data)
            for inverter in range(inverters.num_devices()):
                device = f"inverter-{inverter:02d}"
                energy, power, temp = inverters.get_data(inverter)
                record_device(timestamp, device, energy, power, temp)

            sleep_interval = interval
            if system_power <= 20:
                sleep_interval = max(interval, 1200) # check less often at night
            await asyncio.sleep(sleep_interval)

if __name__ == "__main__":
    # The live data seems to be updated in real time but the inverter data only updates every 5 minutes.
    asyncio.run(push_to_influxdb(60))
