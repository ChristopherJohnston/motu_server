# MOTU AVB Development Server

A tornado web server emulating a MOTU AVB interface's datastore API. Enables development of tools to read and manipulate the datastore without requiring an active interface.

For Datastore API, see [MOTU AVB Datastore API Docs](https://cdn-data.motu.com/downloads/audio/AVB/docs/MOTU%20AVB%20Web%20API.pdf)

For a websocket bridge, see [MOTU AVB Websocket Bridge](https://github.com/ChristopherJohnston/motu_websocket_bridge)

# Usage

In the command line, call:

```
./run --datastore ./datastore.json --port 8888
```

alternatively:

```
make run
```

For HTTP request examples, see [requests.http](./requests.http) (Requires [REST Client extension](https://marketplace.visualstudio.com/items?itemName=humao.rest-client))