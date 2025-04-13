#!/usr/bin/env python3
from scapy.all import IP, ICMP, send
import argparse
import time

def encode_message_in_ipid(message):
    """
    Convert the message into a list of ASCII integer codes.
    """
    return [ord(c) for c in message]

def send_covert_data(destination, message, interval):
    """
    For each character, craft an IP packet with the IP ID set to the character's ASCII code and
    include a marker in the payload.
    
    Each packet's payload is set to "CovertChannel:<character>".
    """
    data_bytes = encode_message_in_ipid(message)
    for val in data_bytes:
        # Create a marker payload including the specific character.
        marker_payload = f"CovertChannel:{chr(val)}"
        # Construct the packet with the DF flag to help preserve the IP ID.
        pkt = IP(dst=destination, id=val, flags="DF") / ICMP() / marker_payload
        send(pkt, verbose=0)
        print(f"Sent packet with IP ID: {val} (character: {chr(val)}) | Payload: {marker_payload}")
        time.sleep(interval)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Covert Channel Sender using IP ID field")
    parser.add_argument("--dest", type=str, required=True, 
                        help="Destination IP address (INSEC container IP)")
    parser.add_argument("--message", type=str, required=True,
                        help="Covert message to send")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Interval in seconds between packets")
    args = parser.parse_args()
    
    print(f"Starting covert transmission to {args.dest}...")
    send_covert_data(args.dest, args.message, args.interval)
