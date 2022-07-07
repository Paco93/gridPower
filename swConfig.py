INFLUXDB_ADDRESS = 'ipaddress'
INFLUXDB_USER = 'username'
INFLUXDB_PASSWORD = 'password'
INFLUXDB_DATABASE = 'databaseName'
LOCATION='name'

LOG_FILENAME='/home/pi/sw/gridPower/grid.log'

SHELLY_HTTP_REQ_URL = 'http://ip_address/status/emeter/0'
SHELLY_NEW_FW= True
inverter_channel=1 #this is the Shelly EM channel number of the CT measuring the inverter production 
grid_channel=0     #this is the Shelly EM channel number of the CT measuring power to/from the grid 

USE_SHELLY_CoIoT = True # if True then CoIoT is used for acquiring Shelly measurements. Otherwise HTTP requests are used 
MCAST_GRP='224.0.1.187'
MCAST_PORT= 5683

ENABLE_FORECAST= True # Set to False if you don't have a Solcast account  
SOLCAST_KEY = "key"
INSTALL_DATE = "2021-01-01"
SOLCAST_SITE_UUID = "uuid"

ENABLE_PV_OUTPUT= True  # Set to False if you don't have a pvoutput account 
PV_OUTPUT_STATUS_URL = "https://pvoutput.org/service/r2/addstatus.jsp"
PV_OUTPUT_ADD_URL    = "https://pvoutput.org/service/r2/addoutput.jsp"
PV_OUTPUT_API_KEY = 'pv_key'
PV_OUTPUT_SYSTEM_ID = 'pv-systemID'

TIME_ZONE = 'Europe/Paris'

#email
ENABLE_EMAIL= True
EMAIL_FROM = "xxx"
EMAIL_TO = "xxx"
EMAIL_PASS = "xxxx"
EMAIL_SERVER = "xxxx"
EMAIL_PORT = 465 #587

debug_print=False


latitude = 0
longitude = 0

