# simple_pvs6_monitor

A deliberately simple Python program to extract info from a SunPower PVS6 solar monitor drawing heavily upon [Sun Strong's more powerful implementation](https://github.com/SunStrong-Management/pypvs).
* Don't poll too often to avoid eMMC write exhaustion.

Also included are a basic script for pushing data to `influxdb` and a `grafana` dashboard.

Requirements:
* For core functionality --- `pip install aiohttp`
* For pushing to influx --- `pip install influxdb_client suntimes pytz`

![grafana dashboard](grafana-dashboard-snapshot.png)






