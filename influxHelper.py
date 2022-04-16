
import swConfig
from influxdb import InfluxDBClient
import time
import logging

class InfluxDBError(Exception):
  pass

def _init_influxdb_database():
    INFLUXDB_ADDRESS = swConfig.INFLUXDB_ADDRESS
    INFLUXDB_USER = swConfig.INFLUXDB_USER
    INFLUXDB_PASSWORD = swConfig.INFLUXDB_PASSWORD
    INFLUXDB_DATABASE = swConfig.INFLUXDB_DATABASE
    influxdb_client = InfluxDBClient(INFLUXDB_ADDRESS, 8086, INFLUXDB_USER, INFLUXDB_PASSWORD, None)
    notConnected=True
    count=0
    while(notConnected):
        try:
            databases = influxdb_client.get_list_database()
            notConnected=False
        except:
            count +=1
            time.sleep(10)
            if (count > 30):
                return None

    if len(list(filter(lambda x: x['name'] == INFLUXDB_DATABASE, databases))) == 0:
        influxdb_client.create_database(INFLUXDB_DATABASE)
    influxdb_client.switch_database(INFLUXDB_DATABASE)

    retentionPolicies=influxdb_client.get_list_retention_policies(database=INFLUXDB_DATABASE)
    if len(list(filter(lambda x: x['name'] == 'Day_Data', retentionPolicies))) == 0:
        influxdb_client.create_retention_policy('Day_Data', 'INF', '1', database=INFLUXDB_DATABASE,   default=False, shard_duration="0s")

    return influxdb_client


def write_influx(flux_client, measurement, measureName, db, t = 0):  #used by forcast
    if flux_client is not None:
        metrics = {}
        tags = {}
        if t > 100000000000:
            metrics['time'] = t

        metrics['measurement'] = measureName
        tags['location'] = swConfig.LOCATION

        metrics['tags'] = tags
        metrics['fields'] = measurement
        metrics =[metrics, ]
        try:
            target=flux_client.write_points(metrics, database=db)
            if not target:
                if swConfig.debug_print:
                    print("Error writing to influx.")
            return target

        except Exception as e:
            raise InfluxDBError("Error in write_influx function") from e

