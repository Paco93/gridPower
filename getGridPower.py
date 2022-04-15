import re
import json
import math

import logging
import pdb
import datetime
import time
import signal, os
import pytz
import emails

import asyncio
from suntime import Sun, SunTimeException

import requests 
from influxdb import InfluxDBClient
import swConfig
import socket

if(swConfig.ENABLE_FORECAST):
    import solcast


runLoop=True

logging.basicConfig( level=logging.INFO, filename=swConfig.LOG_FILENAME, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger=logging.getLogger('Grid')

t1=None
t2=None
t3=None

closeTheSocket=False

decimCount=0

def todayAt (hr, min=0, sec=0, micros=0):
   now = datetime.datetime.now(datetime.timezone.utc)
   return now.replace(hour=hr, minute=min, second=sec, microsecond=micros)    


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
    #if len(retentionPolicies) <2:
    if len(list(filter(lambda x: x['name'] == 'Day_Data', retentionPolicies))) == 0:
        influxdb_client.create_retention_policy('Day_Data', 'INF', '1', database=INFLUXDB_DATABASE,   default=False, shard_duration="0s")
    return influxdb_client


def gridPower():
    response = requests.get(swConfig.SHELLY_HTTP_REQ_URL) 
    #a['emeters'] example is
    #[{"power":-699.18,"reactive":238.15,"pf":-0.95,"voltage":235.42,"is_valid":true,"total":1609373.7,"total_returned":3480157.1},/
    # {"power":823.81,"reactive":-73.60,"pf":-1.00,"voltage":235.42,"is_valid":true,"total":3332254.9,"total_returned":564.9}]
    a=response.json()
    ret=a['emeters']
    return ret

def computePowerFactors(gridPow,gridReact, inverterPow, inverterReact ):
    den=math.sqrt(gridReact**2+gridPow**2)
    if(den>0):
        grid_PF=abs(gridPow)/den
        if ((gridReact*gridPow) < 0 ):
            grid_PF=-grid_PF
    else:
        grid_PF=0
    den1=math.sqrt(inverterReact**2+inverterPow**2)
    if(den1>0):
        invert_PF=inverterPow/den1
        if (inverterReact > 0):
            invert_PF=-invert_PF
    else:
        invert_PF=0
    return grid_PF, invert_PF

def getMeasurementAtDayStart(influxdb_client, measurement, field):
    tStart=todayAt(0, min=2 )
    timestamp = int(tStart.timestamp())*1000000000
    tS=str(timestamp)
    value = None
    try:
        s=('SELECT last("%s") FROM "%s"  WHERE time < %s') %(field, measurement, tS)
        results = influxdb_client.query(s)
        #print (results.raw)
        points = results.get_points()
        for point in points:
            value=(point['last'])
    except Exception as e:       
        value = None
    return value

def getLastMeasurement(influxdb_client, measurement, field):
    value = None
    try:
        s=('SELECT last("%s") FROM "%s" ') %(field, measurement)
        results = influxdb_client.query(s)
        #print (results.raw)
        points = results.get_points()
        for point in points:
            value=(point['last'])
    except Exception as e:
        value = None
    return value


async def active_pow(influxdb_client, inverter_dict):
    global runLoop
    invert_PF=0
    grid_PF=0
    sleepTime =30
    k = 0
    isMeasurementValid = True
    while (runLoop):
        try:
            if(k >= 30):
                k=0 
            if(inverter_dict['activeState'] or k==0):
                a=gridPower()
                gridPow       = a[0]['power']
                gridTotalPow  = a[0]['total']
                gridReturnPow = a[0]['total_returned']
                acVolt        = a[1]['voltage']
                inverterPow   = a[1]['power']
                inverterTotPower= a[1]['total'] 
                if(inverterPow >= 0):
                    invP=inverterPow
                else:
                    invP=0
                homePow=gridPow+ invP

                if(swConfig.SHELLY_NEW_FW== False): 
                    gridReact     = a[0]['reactive']
                    inverterReact = a[1]['reactive']
                    grid_PF, invert_PF = computePowerFactors(gridPow,gridReact, inverterPow, inverterReact )
                else:
                    grid_PF   = a[0]['pf']
                    invert_PF = a[1]['pf']
                    isMeasurementValid = a[0]['is_valid'] and a[1]['is_valid']
                if(isMeasurementValid):
                    inverter_dict['inverterDayPower'] = inverterTotPower-inverter_dict['inverterBasePower']
                    inverter_dict['inverterPow']=  inverterPow
                    inverter_dict['acVolt'] =acVolt
                    measurement={
                            'gridPower'    : gridPow,
                            'inverterPower': inverterPow,
                            'homePower'    : homePow,
                            'inverterDayPower' : inverter_dict['inverterDayPower'],
                            'acVolt'       :  acVolt,
                            'grid_PF'      :  grid_PF,
                            'invert_PF'    :  invert_PF
                        }
                    write_influx(influxdb_client, measurement, "gridPower", swConfig.INFLUXDB_DATABASE)
                    '''json_body = [
                        {
                        'measurement': "gridPower",
                        'tags': {
                            'location': swConfig.LOCATION            },
                        'fields': {
                            'gridPower'    : gridPow,
                            'inverterPower': inverterPow,
                            'homePower'    : homePow,
                            'inverterDayPower' : inverter_dict['inverterDayPower'],
                            'acVolt'       :  acVolt,
                            'grid_PF'      :  grid_PF,
                            'invert_PF'    :  invert_PF
                        }
                        }
                    ]           
                    influxdb_client.write_points(json_body)
                    '''
                else:
                    logger.warning("Shelly measures not valid")
                
                if(k==0):
                    gridDayPower=  gridTotalPow - inverter_dict['gridBasePower']   
                    json_body_2 = [
                    {
                    'measurement': "gridTotal",
                    'tags': {
                        'location': swConfig.LOCATION          },
                    'fields': {
                        'gridTotalPower'   : gridTotalPow  ,
                        'gridReturnPower'  : gridReturnPow ,
                        'inverterTotPower' : inverterTotPower,
                        'gridDayPower'     : gridDayPower
                    }
                    }
                    ]           
                    influxdb_client.write_points(json_body_2) #, retention_policy='year_long')     
 
        except Exception as e:
            logger.error("exception! %s occurred", str(e))
        finally:         
            await asyncio.sleep(sleepTime)
            k=k+1
    logger.debug("Exiting coroutine ")


async def  isDay(influxdb_client, inverter_dict):
    global runLoop
    returnBasePower=getMeasurementAtDayStart(influxdb_client, "gridTotal" , "gridReturnPower" )
    sun = Sun(swConfig.latitude, swConfig.longitude)
    while(runLoop):
        try:
            # Get today's sunrise and sunset in UTC
            today_sr = sun.get_sunrise_time()
            today_ss = sun.get_sunset_time()
        except SunTimeException as e:
            logger.error("Error: {0}.".format(e))   

        tStart=todayAt(today_sr.hour, min=today_sr.minute)
        tStop=todayAt(today_ss.hour, min=today_ss.minute)
        midnigth=todayAt(23, min=59)
        timeNow = datetime.datetime.now(datetime.timezone.utc)
        tDelt2Stop= tStop-timeNow
        tDelt2Start= tStart-timeNow
        tDeltMidnigth=midnigth-timeNow
        secs2Stop=tDelt2Stop.total_seconds()
        secs2Start=tDelt2Start.total_seconds()
        secs2MidNigth=tDeltMidnigth.total_seconds()
        logger.info("secs2Start= {},  secs2Stop ={},   secs2MidNigth= {}".format(secs2Start, secs2Stop, secs2MidNigth ))
        if(secs2Stop>0 and secs2Start>0):
            inverter_dict['activeState']=False
            #print("in 1") 
            await asyncio.sleep(secs2Start+60)
            getSolcastForecasts(influxdb_client) 
            logger.info('Today at Guidonia the sun raised at {} and get down at {} UTC'.
                format(today_sr.strftime('%H:%M'), today_ss.strftime('%H:%M')))
        elif(secs2Stop>0 and secs2Start<=0):
            inverter_dict['activeState']=True
            #print("in 2") 
            await asyncio.sleep(secs2Stop+60)
            inverter_dict['activeState']=False
        elif(secs2Stop<=0 and secs2MidNigth>0):
            #print("in 3") 
            inverter_dict['activeState']=False
            invertDailyPow = getLastMeasurement(influxdb_client, "gridPower" , "inverterDayPower" )
            invDayPowStr=f"{invertDailyPow: .1f}"
            timeHome = datetime.datetime.now()
            strDate=timeHome.strftime( "%Y-%m-%d %H:%M:%S %Z%z")
            finStr= strDate + " End of Active Day.<br> " + "   - Inverter daily production was: "+ invDayPowStr +" Wh\n"
            if(swConfig.ENABLE_EMAIL):
                emails.send_mail(finStr)
            await asyncio.sleep(secs2MidNigth+120)
            try:
                inverter_dict['inverterBasePower']= getMeasurementAtDayStart(influxdb_client, "gridTotal" , "inverterTotPower" )
                invertDailyPow = getLastMeasurement(influxdb_client, "gridPower" , "inverterDayPower" )
                dayGridPowerConsumpt = getLastMeasurement(influxdb_client, "gridTotal" , "gridDayPower" )
                newReturnBasePower= getLastMeasurement(influxdb_client, "gridTotal" , "gridReturnPower" )
                inverter_dict['gridBasePower']= getMeasurementAtDayStart(influxdb_client, "gridTotal" , "gridTotalPower" )

                toGridDayPower=newReturnBasePower- returnBasePower
                returnBasePower=newReturnBasePower
                
                dayHomePower = invertDailyPow - toGridDayPower + dayGridPowerConsumpt
                pvDayOutputs(dayGridPowerConsumpt, toGridDayPower, invertDailyPow)

                tstamp=time.time()-4*3600
                json_body_3 = [
                    {
                    'measurement': "daySummary",
                    'time': int(tstamp*1e9),
                    'tags': {
                        'location': swConfig.LOCATION           },
                    'fields': {
                        'dayGridPower'   : dayGridPowerConsumpt  ,
                        'homeDayPower'   : dayHomePower,
                        'invertDayPower' : invertDailyPow,
                        'toGridDayPower' : toGridDayPower
                    }
                    }
                    ]
                influxdb_client.write_points(json_body_3, retention_policy='Day_Data')   
            except Exception as e:
                logger.error("Exception caugth: %s" , str(e))
        else:
            #print("in 4")
            inverter_dict['activeState']=False
            await asyncio.sleep(3600)
    runLoop=False




def write_influx(flux_client, measurement, iden, db, t = 0):  #used by forcast
    if flux_client is not None:
        metrics = {}
        tags = {}
        if t > 100000000000:
            metrics['time'] = t

        metrics['measurement'] = iden
        tags['location'] = swConfig.LOCATION

        metrics['tags'] = tags
        metrics['fields'] = measurement
        metrics =[metrics, ]
        try:
            target=flux_client.write_points(metrics, database=db)
            if not target:
                logger.error("Error writing to influx.")
            return target

        except Exception as e:
            logger.error("write_influx error: %s", str(e))
            if swConfig.debug_print:
                print("error")
                print(metrics)
                print(db)
                print()
            return False

def getSolcastForecasts(influxdb_client):
    if(swConfig.ENABLE_FORECAST):
        logger.debug("Getting Solcast Forecasts")
        try:
            r1 = solcast.get_rooftop_forecasts(swConfig.SOLCAST_SITE_UUID, api_key=swConfig.SOLCAST_KEY)
            forecast_array = {}
            for x in r1.content['forecasts']:
                dt = x['period_end']
                dt = dt.replace(tzinfo=pytz.timezone('UTC'))
                dt = dt.astimezone(pytz.timezone(swConfig.TIME_ZONE))
                dt = time.mktime(dt.timetuple())
                measurement = {'power': float(x['pv_estimate']), 
                    'power10': float(x['pv_estimate10']), 
                    'power90': float(x['pv_estimate90']) }

                forecast_array[int(dt)] =  float(x['pv_estimate'])

                write_influx(influxdb_client, measurement, "forcast", swConfig.INFLUXDB_DATABASE, int(dt) * 1000000000)
            logger.info("done getting forecast")
        except Exception as e:
            logger.error("Error getting Solcast Forecast: %s", str(e))

async def  pvOutputService(inverter_dict): 
    if(not swConfig.ENABLE_PV_OUTPUT): 
        return 
    global runLoop
    url = swConfig.PV_OUTPUT_STATUS_URL
    apiKey = swConfig.PV_OUTPUT_API_KEY
    systemId = swConfig.PV_OUTPUT_SYSTEM_ID
    headers = {"X-Pvoutput-Apikey" : apiKey,
                 "X-Pvoutput-SystemId" : systemId}

    targetSleepTime =5  #minutes
    targetDur=datetime.timedelta(minutes = targetSleepTime)
    oldTime = datetime.datetime.now()
    await asyncio.sleep( (targetSleepTime-(oldTime.minute % targetSleepTime))*60-oldTime.second)  
    oldTime = datetime.datetime.now(datetime.timezone.utc) 
    last_activePower=0
    while(runLoop):
        now = datetime.datetime.now(datetime.timezone.utc)
        tDelt= now-oldTime
        if(tDelt < targetDur ):
            await asyncio.sleep(targetDur.total_seconds()-tDelt.total_seconds())
        oldTime=datetime.datetime.now(datetime.timezone.utc)
        #dt = oldTime.replace(tzinfo=pytz.timezone('UTC'))
        #dt = dt.astimezone(pytz.timezone(swConfig.TIME_ZONE))
        dt = oldTime.astimezone(pytz.timezone(swConfig.TIME_ZONE))
        invPower=inverter_dict['inverterPow']
        if(invPower<0):
            invPower=0
        try:
            if((invPower > 0 or last_activePower > 0) and inverter_dict['activeState']):
                #payload = "?d={}&t={}&v1={}&v2={}&v5={}&v6={}".format(dt.strftime("%Y%m%d"), dt.strftime("%H:%M"), str(inverter_dict['inverterDayPower']), str(inverterPow),str(temperature), str(acVolt))
                payload = "?d={}&t={}&v1={}&v2={}&v6={}".format(dt.strftime("%Y%m%d"), dt.strftime("%H:%M"), str(inverter_dict['inverterDayPower']), str(invPower), inverter_dict['acVolt'])
                response = requests.get(url+payload, headers=headers)
                response.raise_for_status()
                last_activePower= invPower
        except Exception as e:
            logger.error("Fetching '{}' failed! Error: {}".format(url+payload, e))  
    logger.debug("Exiting coroutine pvOutputService")


def pvDayOutputs(fromGridDayPower, energy_exported, invert_dailyPow):
    if(not swConfig.ENABLE_PV_OUTPUT): 
        return
    url = swConfig.PV_OUTPUT_ADD_URL
    apiKey = swConfig.PV_OUTPUT_API_KEY
    systemId = swConfig.PV_OUTPUT_SYSTEM_ID
    headers = {"X-Pvoutput-Apikey" : apiKey,
                 "X-Pvoutput-SystemId" : systemId}

    energy_consumed=int(invert_dailyPow-energy_exported+fromGridDayPower+0.5)
    #now = datetime.datetime.now(datetime.timezone.utc)
    #dt = now.astimezone(pytz.timezone(swConfig.TIME_ZONE))
    now=datetime.date.fromtimestamp(time.time()-10800)
    try:
        invDayP=int(invert_dailyPow+0.5)
        payload = "?d={}&g={}&e={}&c={}".format(now.strftime("%Y%m%d"), str(invDayP), str(int(energy_exported+0.5)),str(energy_consumed))
        #print(payload)
        response = requests.get(url+payload, headers=headers)
        response.raise_for_status()
    except Exception as e:
        logger.error("Fetching '{}' failed! Error: {}".format(url+payload, e))


def logActivePower(influxdb_client, inverter_dict, measures):
    global decimCount
    try:
        if(decimCount >= 30):
                decimCount=0 
        if(inverter_dict['activeState'] or decimCount==0):
                gridPow       = measures[0]['power']
                gridTotalPow  = measures[0]['total']
                gridReturnPow = measures[0]['total_returned']
                acVolt        = measures[1]['voltage']
                inverterPow   = measures[1]['power']
                inverterTotPower= measures[1]['total'] 
                if(inverterPow >= 0):
                    invP=inverterPow
                else:
                    invP=0
                homePow=gridPow+ invP

                grid_PF   = measures[0]['pf']
                invert_PF = measures[1]['pf']
                inverter_dict['inverterDayPower'] = inverterTotPower-inverter_dict['inverterBasePower']
                inverter_dict['inverterPow']=  inverterPow
                inverter_dict['acVolt'] =acVolt
                json_body = [
                        {
                        'measurement': "gridPower",
                        'tags': {
                            'location': swConfig.LOCATION           },
                        'fields': {
                            'gridPower'    : gridPow,
                            'inverterPower': inverterPow,
                            'homePower'    : homePow,
                            'inverterDayPower' : inverter_dict['inverterDayPower'],
                            'acVolt'       :  acVolt,
                            'grid_PF'      :  grid_PF,
                            'invert_PF'    :  invert_PF
                        }
                        }
                    ]           
                influxdb_client.write_points(json_body)
                
                if(decimCount==0):
                    gridDayPower=  gridTotalPow - inverter_dict['gridBasePower']      
                    json_body_2 = [
                    {
                    'measurement': "gridTotal",
                    'tags': {
                        'location': swConfig.LOCATION          },
                    'fields': {
                        'gridTotalPower'   : gridTotalPow  ,
                        'gridReturnPower'  : gridReturnPow ,
                        'inverterTotPower' : inverterTotPower,
                        'gridDayPower'     : gridDayPower
                    }
                    }
                    ]           
                    influxdb_client.write_points(json_body_2) #, retention_policy='year_long')     
 
    except Exception as e:
        logger.error("exception! %s occurred", str(e))
    finally:         
        decimCount=decimCount+1
    

class EchoClientProtocol:
    def __init__(self, influxdb_client, inverterDict, on_con_lost):
        self.influxdb_client = influxdb_client
        self.on_con_lost = on_con_lost
        self.transport = None
        self.Ret=[{},{}]
        self.inverterDict= inverterDict

    def connection_made(self, transport):
        self.transport = transport
        #sock = transport.get_extra_info("socket")
        #print('Send:', self.message)
        #self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        #tt=time.localtime()
        #print(time.strftime("%H:%M:%S",tt))
        try:
            s=str(data)
            a=s.split('xff')
            json_obj = json.loads(a[1][:-1])
            V=json_obj["G"]
        except:
            return
        for meas in V: 
            if(meas[1]== 4105):
                self.Ret[0]['power']=meas[2]
            elif(meas[1]==4205):
                self.Ret[1]['power']=meas[2]
            elif(meas[1]==4108):
                self.Ret[0]['voltage']=meas[2]
            elif(meas[1]==4208):
                self.Ret[1]['voltage']=meas[2]
            elif(meas[1]==4110):
                self.Ret[0]['pf']=meas[2]
            elif(meas[1]==4210):
                self.Ret[1]['pf']=meas[2]
            elif(meas[1]==4106):
                self.Ret[0]['total']=meas[2]
            elif(meas[1]==4107):
                self.Ret[0]['total_returned']=meas[2]
            elif(meas[1]==4206):
                self.Ret[1]['total']=meas[2]
            elif(meas[1]==4207):
                self.Ret[1]['total_returned']=meas[2]
            else:
                pass
        if(closeTheSocket):
            logger.info("Closing the multicast socket")
            self.transport.close()
        logActivePower(self.influxdb_client, self.inverterDict, self.Ret)

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Connection closed")
        self.on_con_lost.set_result(True)


async def multicast_reader(influxdb_client, inverter_dict):
    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()
    on_con_lost = loop.create_future()
    message = "Hello World!"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32) 
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sock.bind((swConfig.MCAST_GRP, swConfig.MCAST_PORT))

    host = socket.gethostbyname(socket.gethostname())
    sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
    sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(swConfig.MCAST_GRP) + socket.inet_aton(host))
    

    transport, protocol = await loop.create_datagram_endpoint(
        lambda: EchoClientProtocol(influxdb_client, inverter_dict, on_con_lost), sock=sock) 

    try:
        await on_con_lost
    finally:
        transport.close()

def main():
    global t1
    global t2
    global t3
   
    inverter_data = {'activeState': True, 'inverterBasePower': None,'gridBasePower':None, 'inverterDayPower':0.0, 'inverterPow':0.0, 'acVolt':230.0}

    logger.info('Grid Measure started')
    influxdb_client=_init_influxdb_database()
    if(influxdb_client==None):
        logger.error("No InfluxDB instance. Program Terminated")
        return

    getSolcastForecasts(influxdb_client)  
    a=gridPower()
    inverter_data['inverterBasePower']= getMeasurementAtDayStart(influxdb_client, "gridTotal" , "inverterTotPower" )
    inverter_data['gridBasePower']= getMeasurementAtDayStart(influxdb_client, "gridTotal" , "gridTotalPower" )
    if(inverter_data['inverterBasePower'] is None):
        inverter_data['inverterBasePower']= a[1]['total'] 
    if(inverter_data['gridBasePower'] is None):
        inverter_data['gridBasePower']= a[0]['total']
    loop = asyncio.get_event_loop()
    if(swConfig.USE_SHELLY_CoIoT):
        t1 = loop.create_task(multicast_reader(influxdb_client, inverter_data))
    else:
       t1 = loop.create_task(active_pow(influxdb_client, inverter_data))
    t2 = loop.create_task(isDay(influxdb_client, inverter_data))
    t3 = loop.create_task(pvOutputService(inverter_data))
    try:
            loop.run_until_complete(asyncio.gather(t1,t2,t3))
    except asyncio.CancelledError:
            logger.info("Tasks cancelled")
    except Exception as e:
            logger.error("Program terminated with error: {}".format(e)) 

                
def signal_handler(signal, frame):
    global runLoop
    global closeTheSocket
    global t1
    global t2
    global t3
  
    print ("Stop received ")
    runLoop=False
    closeTheSocket=True
    if(swConfig.USE_SHELLY_CoIoT== False):
        t1.cancel()
    t2.cancel()
    t3.cancel()
  
if __name__ == '__main__':    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main()

