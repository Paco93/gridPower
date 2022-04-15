Collect statistics about solar production and home energy consumption collected through a Shelly EM device
SW has been tested on a raspberry pi but should run an any computher with Python 3 (version >=3.7) installed.
The python environment requires some library to worke.g.  pip3 install pytz, isodate, influxdb, suntime 

It is required to configure an influxdB databases for storing measurements
Grafana can be used to plot statistics (some Grafana dashboard json files are provided as examples)


Run as python3 getGridPower.py


Solcast files are cloned from https://github.com/basking-in-the-sun2000/solar-logger/tree/master/solcast
If you want to turn the SW into a linux service copy Shelly.service to /lib/systemd/system/Shelly.service 
