import asyncio
import tornado
import logging
import json
import datetime
from typing import Optional
from motu_server.datastore import Datastore

logger = logging.getLogger(__name__)


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("motu_server.log"), logging.StreamHandler()],
)


class ServerObjects:
    """
    Shared objects in the server.

    Datastore: The motu avb datastore containing the device state.
    Clients: Known clients of the server.
    """
    datastore: Datastore = Datastore()
    clients: dict[int, dict] = {}


def setupDatastore(path: Optional[str]="./datastore.json"):
    """
    Sets up an initial datastore for use by the server.
    """
    ServerObjects.datastore = Datastore(path)
    ServerObjects.clients = {}


class ApiVersionHandler(tornado.web.RequestHandler):
    async def get(self):
        self.write("0.0.0")


class DatastoreHandler(tornado.web.RequestHandler):
    """
    Handles GET and PATCH requests for the AVB datastore.
    """
    def set_default_headers(self):
        """
        Set CORS headers for all requests.
        """
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "if-none-match")
        self.set_header('Access-Control-Allow-Methods', 'POST, PATCH, GET, OPTIONS')
        self.set_header('Access-Control-Expose-Headers', "Etag")

    def _get_client_id(self) -> Optional[int]:
        """
        Determines the client identifier from the
        querystring arguments. Adds the client to the 
        clients dictionary if it's not already there.
        """
        client_id: int = int(self.get_argument("client", "-1"))

        if client_id == -1:
            # No client id provided - that's ok
            return None
        
        if client_id not in ServerObjects.clients:
            # New Client
            logger.warn(client_id)
            ServerObjects.clients[client_id] = {}
            logger.info(f"New Client {client_id}.")
            return client_id
        
        return client_id

    async def get(self, path:str=""):
        """
        Retrieve datastore data at the given path.
        """
        client_id = self._get_client_id()
        
        # When there's an "If-None_Match" header containing the last etag, the client is long polling.
        # In this case, if the provided eTag matches the current eTag, wait up to 15 seconds for updates.
        last_etag = int(self.request.headers.get("If-None-Match", -1))
        if last_etag > -1 and last_etag == await ServerObjects.datastore.etag.value:

            logger.info(f"{client_id}: etags match - long poll call waiting for updates")
            
            remainingTime = datetime.timedelta(seconds=15)
            startTime = datetime.datetime.now()

            while remainingTime > datetime.timedelta(seconds=0):
                if not await ServerObjects.datastore.wait_for_updates(timeout=remainingTime):
                    logger.info(f"{client_id}: timed out waiting for update")
                    self.set_header("Etag", str(await ServerObjects.datastore.etag.value))
                    self.set_status(304)
                    return

                # Filter out updates from the same client
                updated_by = await ServerObjects.datastore.etag.updated_by               
            
                if updated_by == client_id:                    
                    remainingTime = remainingTime - (datetime.datetime.now() - startTime)
                    logger.info(f"{client_id}: ignoring update recieved from client {updated_by}. Remaining time: {remainingTime}")                
                else:
                    logger.info(f"{client_id}: New data received after update by {updated_by}.")
                    break
    
        # If there's new data, read from the datastore
        self.set_header("Etag", str(await ServerObjects.datastore.etag.value))
        self.write(ServerObjects.datastore.read(path))

    async def options(self, path:str=""):
        """
        For OPTIONS requests, set defult cors headers (using set_default_headers)
        and return 200/OK.
        """
        self.set_status(200)
        self.finish()

    async def patch(self, path:str=""):
        """
        handle patch request to update the data at the given path.

        requests come in as raw json in the body, with an argument named "json"
        """
        client_id = self._get_client_id()
        logger.info(f"{client_id}: Updating datastore at {path}")
        request_dict = json.loads(self.request.arguments["json"][0])

        await ServerObjects.datastore.write(path, request_dict, client_id=client_id)

        self.set_header("Etag", str(await ServerObjects.datastore.etag.value))


def make_app() -> tornado.web.Application:
    return tornado.web.Application([
        (r"/datastore[/]*(.*)", DatastoreHandler),
        ("/apiversion", ApiVersionHandler)
    ])


async def main(datastore:Optional[str]=None, port:int=8888) -> None:
    setupDatastore(path=datastore)
    app = make_app()
    app.listen(port)
    logger.info(f"Server listening at http://localhost:{port}")
    logger.info(f"Datastore located at http://localhost:{port}/datastore")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())