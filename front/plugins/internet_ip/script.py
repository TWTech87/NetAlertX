#!/usr/bin/env python

import os
import time
import pathlib
import argparse
import sys
import hashlib
import csv
import subprocess
import re
import base64
import sqlite3
from io import StringIO
from datetime import datetime

# Register NetAlertX directories
INSTALL_PATH="/app"
sys.path.extend([f"{INSTALL_PATH}/front/plugins", f"{INSTALL_PATH}/server"])

from plugin_helper import Plugin_Object, Plugin_Objects, decodeBase64
from logger import mylog, append_line_to_file
from helper import timeNowTZ, check_IP_format, get_setting_value
from const import logPath, applicationPath, fullDbPath


CUR_PATH = str(pathlib.Path(__file__).parent.resolve())
LOG_FILE = os.path.join(CUR_PATH, 'script.log')
RESULT_FILE = os.path.join(CUR_PATH, 'last_result.log')

pluginName = 'INTRNT'

no_internet_ip = '0.0.0.0'

def main():

    mylog('verbose', [f'[{pluginName}] In script'])     
    
    parser = argparse.ArgumentParser(description='Check internet connectivity and IP')
    
    parser.add_argument('prev_ip', action="store", help="Previous IP address to compare against the current IP")
    parser.add_argument('DIG_GET_IP_ARG', action="store", help="Arguments for the 'dig' command to retrieve the IP address") # unused

    values = parser.parse_args()

    PREV_IP         = values.prev_ip.split('=')[1]        
    DIG_GET_IP_ARG  = get_setting_value("INTRNT_DIG_GET_IP_ARG")

    mylog('verbose', [f'[{pluginName}] INTRNT_DIG_GET_IP_ARG: ', DIG_GET_IP_ARG])     

    # perform the new IP lookup N times specified by the INTRNT_TRIES setting
    new_internet_IP = ""
    INTRNT_RETRIES  = get_setting_value("INTRNT_RETRIES")
    retries_needed  = 0

    for i in range(INTRNT_RETRIES + 1):

        new_internet_IP, cmd_output = check_internet_IP( PREV_IP, DIG_GET_IP_ARG)   

        if new_internet_IP == no_internet_ip:
            time.sleep(1*i) # Exponential backoff strategy
        else:
            retries_needed = i
            break

    plugin_objects = Plugin_Objects(RESULT_FILE)    
    
    plugin_objects.add_object(
        primaryId   = 'Internet',       # MAC (Device Name)
        secondaryId = new_internet_IP,  # IP Address 
        watched1    = f'Previous IP: {PREV_IP}',
        watched2    = cmd_output.replace('\n',''),
        watched3    = retries_needed,  
        watched4    = 'Gateway',
        extra       = f'Previous IP: {PREV_IP}', 
        foreignKey  = 'Internet')

    plugin_objects.write_result_file() 

    mylog('verbose', [f'[{pluginName}] Finished '])   
    
    return 0
  
    
#===============================================================================
# INTERNET IP CHANGE
#===============================================================================
def check_internet_IP ( PREV_IP, DIG_GET_IP_ARG ):   
    
    # Get Internet IP
    mylog('verbose', [f'[{pluginName}] - Retrieving Internet IP'])
    internet_IP, cmd_output = get_internet_IP(DIG_GET_IP_ARG)

    mylog('verbose', [f'[{pluginName}]  Current internet_IP : {internet_IP}'])        
    
    # Check previously stored IP    
    previous_IP = no_internet_ip

    if  PREV_IP is not None and len(PREV_IP) > 0 :
        previous_IP = PREV_IP

    mylog('verbose', [f'[{pluginName}]          previous_IP : {previous_IP}']) 

    #  logging
    append_line_to_file (logPath + '/IP_changes.log', '['+str(timeNowTZ()) +']\t'+ internet_IP +'\n')          

    return internet_IP, cmd_output
    

#-------------------------------------------------------------------------------
def get_internet_IP (DIG_GET_IP_ARG):

    cmd_output = ''
    
    # Using 'dig'
    dig_args = ['dig', '+short'] + DIG_GET_IP_ARG.strip().split()
    try:
        cmd_output = subprocess.check_output (dig_args, universal_newlines=True)
        mylog('verbose', [f'[{pluginName}]  DIG result : {cmd_output}'])    
    except subprocess.CalledProcessError as e:
        mylog('verbose', [e.output])
        cmd_output = '' # no internet

    # Check result is an IP
    IP = check_IP_format (cmd_output)

    # Handle invalid response
    if IP == '':
        IP = no_internet_ip

    return IP, cmd_output

#===============================================================================
# BEGIN
#===============================================================================
if __name__ == '__main__':
    main()