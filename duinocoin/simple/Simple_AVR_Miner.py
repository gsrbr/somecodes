#!/usr/bin/env python3
##########################################
# Duino-Coin Python AVR Miner (v2.6.1)
# https://github.com/revoxhere/duino-coin
# Distributed under MIT license
# © Duino-Coin Community 2019-2021
##########################################
# Import libraries
import sys
from configparser import ConfigParser
from datetime import datetime
from json import load as jsonload
from locale import LC_ALL, getdefaultlocale, getlocale, setlocale
from os import _exit, execl, mkdir
from os import name as osname
from os import path
from os import system as ossystem
from platform import machine as osprocessor
from pathlib import Path
from platform import system
from re import sub
from signal import SIGINT, signal
from socket import socket
from subprocess import DEVNULL, Popen, check_call, call
from threading import Thread as thrThread
from threading import Lock
from time import ctime, sleep, strptime, time
from statistics import mean
from random import choice
import select
import pip


def install(package):
    try:
        pip.main(["install",  package])
    except AttributeError:
        check_call([sys.executable, '-m', 'pip', 'install', package])

    call([sys.executable, __file__])


def now():
    # Return datetime object
    return datetime.now()


try:
    # Check if pyserial is installed
    from serial import Serial
    import serial.tools.list_ports
except ModuleNotFoundError:
    print(
        now().strftime('%H:%M:%S ')
        + 'Pyserial is not installed. '
        + 'Miner will try to install it. '
        + 'If it fails, please manually install "pyserial" python3 package.'
        + '\nIf you can\'t install it, use the Minimal-PC_Miner.')
    install('pyserial')

try:
    # Check if requests is installed
    import requests
except ModuleNotFoundError:
    print(
        now().strftime('%H:%M:%S ')
        + 'Requests is not installed. '
        + 'Miner will try to install it. '
        + 'If it fails, please manually install "requests" python3 package.'
        + '\nIf you can\'t install it, use the Minimal-PC_Miner.')
    install('requests')

try:
    # Check if pypresence is installed
    from pypresence import Presence
except ModuleNotFoundError:
    print(
        now().strftime('%H:%M:%S ')
        + 'Pypresence is not installed. '
        + 'Miner will try to install it. '
        + 'If it fails, please manually install "pypresence" python3 package.'
        + '\nIf you can\'t install it, use the Minimal-PC_Miner.')
    install('pypresence')

# Global variables
MINER_VER = '2.61'  # Version number
SOC_TIMEOUT = 45
PERIODIC_REPORT_TIME = 60
AVR_TIMEOUT = 3.1  # diff 6 * 100 / 196 h/s = 3.06
BAUDRATE = 115200
RESOURCES_DIR = 'AVRMiner_' + str(MINER_VER) + '_resources'
shares = [0, 0]
hashrate_mean = []
ping_mean = []
diff = 0
shuffle_ports = "y"
donator_running = False
job = ''
debug = 'n'
discord_presence = 'y'
rig_identifier = 'None'
donation_level = 0
hashrate = 0
config = ConfigParser()
thread_lock = Lock()
mining_start_time = time()

# Create resources folder if it doesn't exist
if not path.exists(RESOURCES_DIR):
    mkdir(RESOURCES_DIR)


# OS X invalid locale hack
if system() == 'Darwin':
    if getlocale()[0] is None:
        setlocale(LC_ALL, 'en_US.UTF-8')

# Check if miner is configured, if it isn't, autodetect language
lang = 'english'


def get_prefix(diff: int):
    if int(diff) >= 1000000000:
        diff = str(round(diff / 1000000000)) + "G"
    elif int(diff) >= 1000000:
        diff = str(round(diff / 1000000)) + "M"
    elif int(diff) >= 1000:
        diff = str(round(diff / 1000)) + "k"
    return str(diff)


def debug_output(text: str):
    # Debug output
    if debug == 'y':
        print(
            + now().strftime('%H:%M:%S.%f ')
            + 'DEBUG: '
            + str(text))


def title(title: str):
    # Window title
    if osname == 'nt':
        # Windows systems
        ossystem('title ' + title)
    else:
        # Most standard terminals
        print('\33]0;' + title + '\a', end='')
        sys.stdout.flush()


def handler(signal_received, frame):
    # SIGINT handler
    pretty_print(
        'sys0',
        " SIGINT detected - Exiting gracefully."
        + " See you soon!",
        'warning')
    try:
        # Close previous socket connection (if any)
        socket.close()
    except Exception:
        pass
    _exit(0)


# Enable signal handler
signal(SIGINT, handler)


def load_config():
    # Config loading section
    global username
    global donation_level
    global avrport
    global debug
    global rig_identifier
    global discord_presence
    global shuffle_ports
    global SOC_TIMEOUT
    global AVR_TIMEOUT
    global PERIODIC_REPORT_TIME

    # Initial configuration section
    if not Path(str(RESOURCES_DIR) + '/Miner_config.cfg').is_file():
        print(
            "\nDuino-Coin basic configuration tool\nEdit "
            + RESOURCES_DIR
            + "/Miner_config.cfg file later if you want to change it.")

        print(
            "Don't have an Duino-Coin account yet? Use "
            + "Wallet"
            + " to register on server.\n")

        username = input(
            "Enter your Duino-Coin username: "
            )

        print("Configuration tool has found the following ports:")
        portlist = serial.tools.list_ports.comports(include_links=True)
        for port in portlist:
            print('  '
                  + str(port))
        print("If you can't see your board here, make sure the it is properly connected and the program has access to it (admin/sudo rights).")

        port_names = []
        for port in portlist:
            port_names.append(port.device)

        avrport = ''
        while True:
            current_port = input(
                "Enter your board serial port (e.g. COM1 (Windows) or /dev/ttyUSB1 (Unix)): "
                )

            if current_port in port_names:
                avrport += current_port
                confirmation = input(
                    "Do you want to add another board? (y/N): "
                    )

                if confirmation == 'y' or confirmation == 'Y':
                    avrport += ','
                else:
                    break
            else:
                print('Please enter a valid COM port from the list above')

        rig_identifier = input("Do you want to add an identifier (name) to this rig? (y/N) ")
        if rig_identifier == 'y' or rig_identifier == 'Y':
            rig_identifier = input(
                "Enter desired rig name: "
                )
        else:
            rig_identifier = 'None'

        donation_level = '0'
        #if osname == 'nt' or osname == 'posix':
        #    donation_level = input(
        #        Style.RESET_ALL
        #        + Fore.YELLOW
        #        + get_string('ask_donation_level')
        #        + Fore.RESET
        #        + Style.BRIGHT)

        # Check wheter donation_level is correct
        donation_level = sub(r'\D', '', donation_level)
        if donation_level == '':
            donation_level = 1
        if float(donation_level) > int(5):
            donation_level = 5
        if float(donation_level) < int(0):
            donation_level = 0

        # Format data
        config['Duino-Coin-AVR-Miner'] = {
            'username':         username,
            'avrport':          avrport,
            'donate':           donation_level,
            'language':         lang,
            'identifier':       rig_identifier,
            'debug':            'n',
            "soc_timeout":      45,
            "avr_timeout":      3.1,
            "discord_presence": "y",
            "periodic_report":  60,
            "shuffle_ports":    "y"
        }

        # Write data to file
        with open(str(RESOURCES_DIR)
                  + '/Miner_config.cfg', 'w') as configfile:
            config.write(configfile)

        avrport = avrport.split(',')
        print("Config saved! Launching the miner")

    else:  # If config already exists, load from it
        config.read(str(RESOURCES_DIR) + '/Miner_config.cfg')
        username = config['Duino-Coin-AVR-Miner']['username']
        avrport = config['Duino-Coin-AVR-Miner']['avrport']
        avrport = avrport.replace(" ", "").split(',')
        donation_level = config['Duino-Coin-AVR-Miner']['donate']
        debug = config['Duino-Coin-AVR-Miner']['debug']
        rig_identifier = config['Duino-Coin-AVR-Miner']['identifier']
        SOC_TIMEOUT = int(config["Duino-Coin-AVR-Miner"]["soc_timeout"])
        AVR_TIMEOUT = float(config["Duino-Coin-AVR-Miner"]["avr_timeout"])
        discord_presence = config["Duino-Coin-AVR-Miner"]["discord_presence"]
        shuffle_ports = config["Duino-Coin-AVR-Miner"]["shuffle_ports"]
        PERIODIC_REPORT_TIME = int(
            config["Duino-Coin-AVR-Miner"]["periodic_report"])


def greeting():
    # greeting message depending on time
    global greeting

    current_hour = strptime(ctime(time())).tm_hour

    if current_hour < 12:
        greeting = "Have a wonderful morning"
    elif current_hour == 12:
        greeting = "Have a tasty noon"
    elif current_hour > 12 and current_hour < 18:
        greeting = "Have a peaceful afternoon"
    elif current_hour >= 18:
        greeting = "Have a cozy evening"
    else:
        greeting = "Welcome back"

    # Startup message
    print(' | '
        + "Simple_AVR_miner by gsrbr based on Official Duino-Coin AVR Miner"
        + ' (v'
        + str(MINER_VER)
        + ') '
        + '2019-2021')

    print(
        ' | '
        + 'https://github.com/revoxhere/duino-coin')


    print(
        ' | '
        + "AVR board(s) on port(s): "
        + ' '.join(avrport))

    #if osname == 'nt' or osname == 'posix':
    #    print(
    #        Style.DIM
    #        + Fore.MAGENTA
    #        + ' | '
    #        + Style.NORMAL
    #        + Fore.RESET
    #        + get_string('donation_level')
    #        + Style.BRIGHT
    #        + Fore.YELLOW
    #        + str(donation_level))
    print(' | '
        + "Algorithm: "
        + 'DUCO-S1A  AVR diff')

    if rig_identifier != "None":
        print(' | '
            + "Rig identifier: "
            + rig_identifier)

    print(
        ' | '
        + str(greeting)
        + ', '
        + str(username)
        + '!\n')


def init_rich_presence():
    # Initialize Discord rich presence
    global RPC
    try:
        RPC = Presence(808056068113563701)
        RPC.connect()
        debug_output('Discord rich presence initialized')
    except Exception:
        # Discord not launched
        pass


def update_rich_presence():
    # Update rich presence status
    startTime = int(time())
    while True:
        try:
            RPC.update(
                details='Hashrate: ' + str(round(hashrate)) + ' H/s',
                start=startTime,
                state='Acc. shares: '
                + str(shares[0])
                + '/'
                + str(shares[0] + shares[1]),
                large_image='ducol',
                large_text='Duino-Coin, '
                + 'a coin that can be mined with almost everything, '
                + 'including AVR boards',
                buttons=[
                    {'label': 'Learn more',
                     'url': 'https://duinocoin.com'},
                    {'label': 'Discord Server',
                     'url': 'https://discord.gg/k48Ht5y'}])
        except Exception:
            # Discord not launched
            pass
        # 15 seconds to respect Discord's rate limit
        sleep(15)


def pretty_print(message_type, message, state):
    # Print output messages in the DUCO 'standard'
    # Usb/net/sys background
    if message_type.startswith('net'):
        background = 'net'
    elif message_type.startswith('usb'):
        background = 'usb'
    else:
        background = ''

    # Text color
    if state == 'success':
        color = 'success'
    elif state == 'warning':
        color = 'warning'
    else:
        color = ''

    with thread_lock:
        print(now().strftime('%H:%M:%S ')
              + background
              + ' '
              + message_type
              + ' '
              + color
              + message)


def mine_avr(com, threadid):
    global hashrate

    start_time = time()
    report_shares = 0
    while True:
        try:
            while True:
                try:
                    # Default AVR mining port
                    debug_output('Connecting to ' +
                                 str(NODE_ADDRESS + ":" + str(NODE_PORT)))
                    soc = socket()
                    soc.connect((str(NODE_ADDRESS), int(NODE_PORT)))
                    soc.settimeout(SOC_TIMEOUT)
                    server_version = soc.recv(100).decode()

                    if threadid == 0:
                        if float(server_version) <= float(MINER_VER):
                            pretty_print(
                                'net0',
                                " Connected"
                                + " to master Duino-Coin server (v"
                                + str(server_version)
                                + ")",
                                'success')
                        else:
                            pretty_print(
                                'sys0',
                                ' Miner is outdated (v'
                                + MINER_VER
                                + ') -'
                                + " server is on v"
                                + server_version
                                + ", please download latest version from https://github.com/revoxhere/duino-coin/releases/",
                                'warning')
                            sleep(10)

                        soc.send(bytes("MOTD", encoding="ascii"))
                        motd = soc.recv(1024).decode().rstrip("\n")

                        if "\n" in motd:
                            motd = motd.replace("\n", "\n\t\t")

                        try:
                            pretty_print("net" + str(threadid),
                                        " MOTD: "
                                        + str(motd),
                                        "success")
                        except:
                            pretty_print("net" + str(threadid),
                                    " MOTD: "
                                    + "Ops... I cant figure the MOTD",
                                    "success")
                    break
                except Exception as e:
                    pretty_print(
                        'net0',
                        " Error connecting to the server. Retrying in 10s"
                        + ' ('
                        + str(e)
                        + ')',
                        'error')
                    debug_output('Connection error: ' + str(e))
                    sleep(10)

            pretty_print(
                'sys'
                + str(''.join(filter(str.isdigit, com))),
                " AVR mining thread is starting"
                + " using DUCO-S1A algorithm ("
                + str(com)
                + ')',
                'success')

            while True:
                # Send job request
                debug_output(com + ': requested job from the server')
                soc.sendall(
                    bytes(
                        'JOB,'
                        + str(username)
                        + ',AVR',
                        encoding='ascii'))

                # Retrieve work
                job = soc.recv(128).decode().rstrip("\n")
                job = job.split(",")
                debug_output("Received: " + str(job))

                try:
                    diff = int(job[2])
                    debug_output(str(''.join(filter(str.isdigit, com)))
                                 + "Correct job received")
                except:
                    pretty_print("usb"
                                 + str(''.join(filter(str.isdigit, com))),
                                 " Node message: "
                                 + job[1],
                                 "warning")
                    sleep(3)

                while True:
                    while True:
                        try:
                            ser.close()
                        except:
                            pass

                        try:
                            ser = Serial(com,
                                         baudrate=int(BAUDRATE),
                                         timeout=float(AVR_TIMEOUT))
                            break
                        except Exception as e:
                            pretty_print(
                                'usb'
                                + str(''.join(filter(str.isdigit, com))),
                                " AVR connection error on port "
                                + str(com)
                                + ", please check whether it's plugged in or not"
                                + ' (port connection err: '
                                + str(e)
                                + ')',
                                'error')
                            sleep(10)

                    while True:
                        retry_counter = 0
                        while True:
                            if retry_counter >= 3:
                                break

                            try:
                                debug_output(com + ': sending job to AVR')
                                ser.write(
                                    bytes(
                                        str(
                                            job[0]
                                            + ',' + job[1]
                                            + ',' + job[2]
                                            + ','), encoding='ascii'))

                                debug_output(com + ': reading result from AVR')
                                result = ser.read_until(b'\n').decode().strip()
                                ser.flush()

                                if "\x00" in result or not result:
                                    raise Exception("Empty data received")

                                debug_output(com + ': retrieved result: '
                                             + str(result)
                                             + ' len: '
                                             + str(len(result)))
                                result = result.split(',')

                                try:
                                    if result[0] and result[1]:
                                        break
                                except Exception as e:
                                    debug_output(
                                        com
                                        + ': retrying reading data: '
                                        + str(e))
                                    retry_counter += 1
                            except Exception as e:
                                debug_output(
                                    com
                                    + ': retrying sending data: '
                                    + str(e))
                                retry_counter += 1

                        try:
                            debug_output(
                                com
                                + ': received result ('
                                + str(result[0])
                                + ')')
                            debug_output(
                                com
                                + ': received time ('
                                + str(result[1])
                                + ')')
                            # Convert AVR time to seconds
                            computetime = round(int(result[1]) / 1000000, 3)
                            if computetime < 1:
                                computetime = str(
                                    int(computetime * 1000)) + "ms"
                            else:
                                computetime = str(round(computetime, 2)) + "s"
                            # Calculate hashrate
                            hashrate_t = round(
                                int(result[0]) * 1000000 / int(result[1]), 2)
                            hashrate_mean.append(hashrate_t)
                            # Get average from the last hashrate measurements
                            hashrate = mean(hashrate_mean[-5:])
                            debug_output(
                                com +
                                ': calculated hashrate (' +
                                str(hashrate_t) + ')'
                                + ' (avg:' + str(hashrate) + ')')

                            try:
                                chipID = result[2]
                                debug_output(
                                    com + ': chip ID: ' + str(result[2]))
                                """ Check if chipID got received, this is 
                                    of course just a fraction of what's 
                                    happening on the server with it """
                                if not chipID.startswith('DUCOID'):
                                    raise Exception('Wrong chipID string')
                            except Exception:
                                pretty_print(
                                    'usb'
                                    + str(''.join(filter(str.isdigit, com))),
                                    ' Possible incorrect chip ID!'
                                    + ' This can cause problems with the'
                                    + ' Kolka system',
                                    'warning')
                                chipID = 'None'
                            break
                        except Exception as e:
                            pretty_print(
                                'usb'
                                + str(''.join(filter(str.isdigit, com))),
                                " Error connecting to the AVR! Retrying in 10s"
                                + ' (error reading result from the board: '
                                + str(e)
                                + ', please check connection '
                                + 'and port setting)',
                                'warning')
                            debug_output(
                                com + ': error splitting data: ' + str(e))
                            sleep(1)

                    try:
                        # Send result to the server
                        soc.sendall(
                            bytes(
                                str(result[0])
                                + ','
                                + str(hashrate_t)
                                + ',Simple AVR Miner v'
                                + str(MINER_VER)
                                + ','
                                + str(rig_identifier)
                                + ','
                                + str(chipID),
                                encoding='ascii'))
                    except Exception as e:
                        pretty_print(
                            'net'
                            + str(''.join(filter(str.isdigit, com))),
                            " Error connecting to the server. Retrying in 10s"
                            + ' ('
                            + str(e)
                            + ')',
                            'error')
                        debug_output(com + ': connection error: ' + str(e))
                        sleep(5)
                        break

                    while True:
                        try:
                            responsetimetart = now()
                            feedback = soc.recv(64).decode().rstrip('\n')
                            responsetimestop = now()

                            time_delta = (responsetimestop -
                                          responsetimetart).microseconds
                            ping_mean.append(round(time_delta / 1000))
                            ping = mean(ping_mean[-10:])
                            debug_output(com + ': feedback: '
                                         + str(feedback)
                                         + ' with ping: '
                                         + str(ping))
                            break
                        except Exception as e:
                            pretty_print(
                                'net'
                                + str(''.join(filter(str.isdigit, com))),
                                " Error connecting to the server. Retrying in 10s"
                                + ' (err parsing response: '
                                + str(e)
                                + ')',
                                'error')
                            debug_output(com + ': error parsing response: '
                                         + str(e))
                            sleep(5)
                            break

                    diff = get_prefix(diff)
                    if feedback == 'GOOD':
                        # If result was correct
                        shares[0] += 1
                        title(
                            "Duino-Coin AVR Miner (v"
                            + str(MINER_VER)
                            + ') - '
                            + str(shares[0])
                            + '/'
                            + str(shares[0] + shares[1])
                            + " accepted shares")
                        with thread_lock:
                            print(
                                now().strftime('%H:%M:%S ')
                                + ' usb'
                                + str(''.join(filter(str.isdigit, com)))
                                + ' '
                                + ' '
                                + " accepted shares"
                                + str(int(shares[0]))
                                + '/'
                                + str(int(shares[0] + shares[1]))
                                + ' ('
                                + str(int((shares[0]
                                           / (shares[0] + shares[1]) * 100)))
                                + '%)'
                                + ' . '
                                + str(round(hashrate))
                                + ' H/s'
                                + ' ('
                                + computetime
                                + ')'
                                + '  diff '
                                + str(diff)
                                + ' . '
                                + 'ping '
                                + str('%02.0f' % int(ping))
                                + 'ms')

                    elif feedback == 'BLOCK':
                        # If block was found
                        shares[0] += 1
                        title(
                            "Duino-Coin AVR Miner (v"
                            + str(MINER_VER)
                            + ') - '
                            + str(shares[0])
                            + '/'
                            + str(shares[0] + shares[1])
                            + " accepted shares")
                        with thread_lock:
                            print(
                                now().strftime('%H:%M:%S ')
                                + ' usb'
                                + str(''.join(filter(str.isdigit, com)))
                                + ' '
                                + ' '
                                + " Block found "
                                + str(int(shares[0]))
                                + '/'
                                + str(int(shares[0] + shares[1]))
                                + ' ('
                                + str(int((shares[0]
                                           / (shares[0] + shares[1]) * 100)))
                                + '%)'
                                + ' . '
                                + str(round(hashrate))
                                + ' H/s'
                                + ' ('
                                + computetime
                                + ')'
                                + '  diff '
                                + str(diff)
                                + ' . '
                                + 'ping '
                                + str('%02.0f' % int(ping))
                                + 'ms')

                    else:
                        # If result was incorrect
                        shares[1] += 1
                        title(
                            "Duino-Coin AVR Miner (v"
                            + str(MINER_VER)
                            + ') - '
                            + str(shares[0])
                            + '/'
                            + str(shares[0] + shares[1])
                            + " accepted shares")
                        with thread_lock:
                            print(
                                now().strftime('%H:%M:%S ')
                                + ' usb'
                                + str(''.join(filter(str.isdigit, com)))
                                + ' '
                                + '  X '
                                + " Rejected "
                                + str(int(shares[0]))
                                + '/'
                                + str(int(shares[0] + shares[1]))
                                + ' ('
                                + str(int((shares[0]
                                           / (shares[0] + shares[1]) * 100)))
                                + '%)'
                                + ' . '
                                + str(round(hashrate))
                                + ' H/s'
                                + ' ('
                                + computetime
                                + ')'
                                + '  diff '
                                + str(diff)
                                + ' . '
                                + 'ping '
                                + str('%02.0f' % int(ping))
                                + 'ms')

                    end_time = time()
                    elapsed_time = end_time - start_time
                    if (threadid == 0
                            and elapsed_time >= PERIODIC_REPORT_TIME):
                        report_shares = shares[0] - report_shares
                        uptime = calculate_uptime(mining_start_time)

                        periodic_report(start_time,
                                        end_time,
                                        report_shares,
                                        hashrate,
                                        uptime)
                        start_time = time()
                    break

        except Exception as e:
            pretty_print(
                'net0',
                " Error connecting to the server. Retrying in 10s"
                + ' (main loop err: '
                + str(e)
                + ')',
                'error')
            debug_output('Main loop error: ' + str(e))


def periodic_report(start_time,
                    end_time,
                    shares,
                    hashrate,
                    uptime):
    seconds = round(end_time - start_time)
    pretty_print("sys0",
                 " " 
                 + "Periodic mining report (BETA): "
                 + "\n\t\t| During the last "
                 + str(seconds)
                 + " seconds"
                 + "\n\t\t| You've mined "
                 + str(shares)
                 + " shares ("
                 + str(round(shares/seconds, 1))
                 + " shares/s)"
                 + "\n\t\t| With the hashrate of "
                 + str(int(hashrate)) + " H/s"
                 + "\n\t\t| In this time period, you've solved "
                 + str(int(hashrate*seconds))
                 + " hashes"
                 + "\n\t\t| Total miner uptime: "
                 + str(uptime), "success")


def calculate_uptime(start_time):
    uptime = time() - start_time
    if uptime <= 59:
        return str(round(uptime)) + " seconds"
    elif uptime == 60:
        return str(round(uptime // 60)) + " minute"
    elif uptime >= 60:
        return str(round(uptime // 60)) + " minutes"
    elif uptime == 3600:
        return str(round(uptime // 3600)) + " hour"
    elif uptime >= 3600:
        return str(round(uptime // 3600)) + " hours"


def fetch_pools():
    while True:
        pretty_print("net0",
                     " "
                     + "Searching for the fastest node to connect to"
                     + "...",
                     "warning")

        try:
            response = requests.get(
                "https://server.duinocoin.com/getPool"
            ).json()

            NODE_ADDRESS = response["ip"]
            NODE_PORT = response["port"]

            return NODE_ADDRESS, NODE_PORT
        except Exception as e:
            pretty_print("net0",
                         " Error retrieving mining node: "
                         + str(e)
                         + ", retrying in 15s",
                         "error")
            sleep(15)


if __name__ == '__main__':
    if osname == "nt":
        # Unicode fix for windows
        ossystem("chcp 65001")

    # Window title
    title("Simple_AVR_miner by gsrbr based on Official Duino-Coin AVR Miner (v" + str(MINER_VER) + ')')

    print("Hello, welcome to the Simple AVR miner, this it's an adapted version of the Official AVR miner, without any colorama dependence or special characters.\nWarning\nAs it is an adapted version, only for users of old systems, this miner may not receive constant updates or even not receive updates\nthanks for understanding \n-gsrbr - https://github.com/gsrbr")
    sleep(3)

    try:
        # Load config file or create new one
        load_config()
        debug_output('Config file loaded')
    except Exception as e:
        pretty_print(
            'sys0',
            " Error loading the configfile ("
            + RESOURCES_DIR
            + "/Miner_config.cfg). Try removing it and re-running configuration. Exiting in 10s"
            + ' ('
            + str(e)
            + ')',
            'error')
        debug_output('Error reading configfile: ' + str(e))
        sleep(10)
        _exit(1)

    try:
        # Display greeting message
        greeting()
        debug_output('greeting displayed')
    except Exception as e:
        debug_output('Error displaying greeting message: ' + str(e))

    try:
        NODE_ADDRESS, NODE_PORT = fetch_pools()
    except Exception as e:
        print(e)
        NODE_ADDRESS = "server.duinocoin.com"
        NODE_PORT = 2813
        debug_output("Using default server port and address")

    try:
        # Launch avr duco mining threads
        threadid = 0
        for port in avrport:
            thrThread(
                target=mine_avr,
                args=(port, threadid)).start()
            threadid += 1
    except Exception as e:
        debug_output('Error launching AVR thread(s): ' + str(e))

    if discord_presence == "y":
        try:
            # Discord rich presence threads
            init_rich_presence()
            thrThread(
                target=update_rich_presence).start()
        except Exception as e:
            debug_output('Error launching Discord RPC thread: ' + str(e))
