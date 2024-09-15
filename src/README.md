# MOTU AVB Development Server

A tornado web server emulating a MOTU AVB interface's datastore API. Enables development of tools to read and manipulate the datastore without requiring an active interface.

For Datastore API, see [MOTU AVB Datastore API Docs](https://cdn-data.motu.com/downloads/audio/AVB/docs/MOTU%20AVB%20Web%20API.pdf)

For a websocket bridge, see [MOTU AVB Websocket Bridge](https://github.com/ChristopherJohnston/motu_websocket_bridge)

For HTTP request examples, see [requests.http](https://github.com/ChristopherJohnston/motu_server/requests.http)

# Usage

```
import asyncio
from motu_server import server

def main():
    asyncio.run(server.main())

if __name__ == '__main__':
    main()
```

Server is available at http://localhost:8888/datastore
