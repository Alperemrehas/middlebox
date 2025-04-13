#!/usr/bin/env python3
from scapy.all import sniff, IP, ICMP
import argparse

received_chars = []

def process_packet(pkt):
    """
    Check if the ICMP payload contains the marker "CovertChannel" and, if so,
    extract and decode the IP ID field as the covert character.
    """
    if IP in pkt and ICMP in pkt:
        # Extract the raw payload bytes from the ICMP layer.
        payload_bytes = bytes(pkt[ICMP].payload)
        # Check if our unique marker is present.
        if b"CovertChannel" in payload_bytes:
            ip_id = pkt[IP].id
            try:
                # Check if the value is in a reasonable ASCII range.
                if 32 <= ip_id < 127:
                    ch = chr(ip_id)
                    received_chars.append(ch)
                    print(f"Received packet with IP ID: {ip_id} (character: {ch})")
                else:
                    print(f"Received packet with modified IP ID (out of ASCII range): {ip_id}")
            except Exception as e:
                print("Error decoding character:", e)
        else:
            # Ignore packets that do not contain the marker.
            pass

def main(interface, packet_count):
    print(f"Sniffing for covert channel packets on interface {interface}...")
    sniff(iface=interface, filter="icmp", prn=process_packet, count=packet_count)
    covert_message = "".join(received_chars)
    print("\n=== Covert Message Received ===")
    print(covert_message)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Covert Channel Receiver using IP ID field")
    parser.add_argument("--iface", type=str, default="eth0", help="Interface to sniff on")
    parser.add_argument("--count", type=int, default=10, help="Number of packets to capture")
    args = parser.parse_args()
    
    main(args.iface, args.count)
