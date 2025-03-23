import asyncio
from nats.aio.client import Client as NATS
import os, random
from scapy.all import Ether

# Set the mean delay in milliseconds.
MEAN_DELAY_MS = 200

async def run():
    nc = NATS()
    nats_url = os.getenv("NATS_SURVEYOR_SERVERS", "nats://nats:4222")
    await nc.connect(nats_url)

    async def message_handler(msg):
        subject = msg.subject
        data = msg.data
        packet = Ether(data)
        # Print a summary to keep log output concise
        print(packet.summary())
        

        # Uniform distribution between 0 and MEAN_DELAY_MS.
        delay = random.uniform(0, MEAN_DELAY_MS / 1000.0)
        print("Applying delay...")
        await asyncio.sleep(delay)
        print(f"Delay of {delay:.3f} seconds applied.")

        
        # Forward the frame based on the source topic.
        if subject == "inpktsec":
            await nc.publish("outpktinsec", msg.data)
        else:
            await nc.publish("outpktsec", msg.data)
   
    # Subscribe to both streams.
    await nc.subscribe("inpktsec", cb=message_handler)
    await nc.subscribe("inpktinsec", cb=message_handler)

    print("Subscribed to inpktsec and inpktinsec topics")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Disconnecting...")
        await nc.close()

if __name__ == '__main__':
    asyncio.run(run())
