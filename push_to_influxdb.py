import os
import sys
import pytz
import asyncio
import aiohttp
import suntimes
import datetime
import pvs_simple
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

# Location of device for day/night checking
lat =  41.12255231172327
lon = -72.33433855074045

bucket = "PVS"
token = os.environ.get("INFLUXDB_TOKEN")
org = "Hoime"
url = "http://192.168.5.8:8086"

client = influxdb_client.InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

def is_daytime_and_time_to_sunrise(lat, lon):
    """
    Checks if it is daytime and returns the time until the next sunrise.

    Args:
        lat (float): Latitude of the location.
        lon (float): Longitude of the location.

    Returns:
        tuple: A tuple containing:
            - bool: True if it is daytime, False otherwise.
            - float: Time in seconds until the next sunrise.
    """
    now = datetime.datetime.now(pytz.utc)
    sun = suntimes.SunTimes(lon, lat)
    today_sunrise = sun.riselocal(now)
    today_sunset = sun.setlocal(now)

    now_local = datetime.datetime.now(today_sunrise.tzinfo)
    is_day = today_sunrise < now_local < today_sunset

    # Calculate time to next sunrise
    if now_local <= today_sunrise:
        next_sunrise = today_sunrise
    else:
        tomorrow = now_local + datetime.timedelta(days=1)
        next_sunrise = sun.riselocal(tomorrow)

    time_to_sunrise_seconds = (next_sunrise - now_local).total_seconds()

    return is_day, time_to_sunrise_seconds

def record_device(timestamp, device, energy, power, temp):
    p = influxdb_client.Point("PVS6").tag("device", device).time(timestamp).field("kWh", energy).field("kW", power).field("C",temp)
    write_api.write(bucket=bucket, org=org, record=p)

async def push_to_influxdb(interval=300):
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
            sys.stdout.flush()
            system_power = power

            inverters = pvs_simple.Inverters(data)
            for inverter in range(inverters.num_devices()):
                device = f"inverter-{inverter:02d}"
                energy, power, temp = inverters.get_data(inverter)
                record_device(timestamp, device, energy, power, temp)

            is_day, time_to_sunrise = is_daytime_and_time_to_sunrise(lat, lon)
            sleep_interval = interval
            if not is_day:
                sleep_interval = time_to_sunrise
                pvs.log(f"push_to_influx: sleeping till dawn {time_to_sunrise}s")
            await asyncio.sleep(sleep_interval)

if __name__ == "__main__":
    # The live data seems to be updated in real time but the inverter data only updates every 5 minutes.
    # Polling too frequently will increase wear on eMMC on the PVS device.
    asyncio.run(push_to_influxdb())
