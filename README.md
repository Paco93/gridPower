# Description #

Collect statistics about solar production and home energy consumption through a Shelly EM device.
The SW has been tested on a raspberry pi but should run an any computer with Python 3 (version >=3.7) installed.
The SW may optionally download solar production forecasst from the Solcast (solcast.com) forecast service.
Also the SW may optionally upload solar production info to pvoutput.org web site.


# Basic Instructions #
It is required to configure an influxdB databases for storing measurements before using the provided SW.
The swConfig.py file shall be edited to setup required info about the InfluxdB database (ip address, username, password and database name).
From the swConfig.py file it is possible to enable the solcast.com forecasts as well as the solar power measurement logging to pvoutput.org. In case these options are enabled, the required parameters to use such services shall also be provided.

Grafana can be used to plot statistics (some Grafana dashboard json files are provided as examples).
The python environment requires some library to work e.g.  pip3 install pytz, isodate, influxdb, suntime. 

# Usage #
Run as python3 getGridPower.py
If you want to turn the SW into a linux service copy Shelly.service to /lib/systemd/system/Shelly.service and use systemctl to start and stop the service.

# Acknowledgment #
Files in the solcast folder were cloned from https://github.com/basking-in-the-sun2000/solar-logger/tree/master/solcast
