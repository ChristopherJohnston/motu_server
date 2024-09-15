import asyncio
import tornado
import logging
import json
import datetime
from typing import Optional
from motu_server.datastore import Datastore
from motu_server.zeroconf_registration import MotuZeroConfRegistration

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
            ServerObjects.clients[client_id] = {}
            logger.info(f"New Client {client_id}.")
            return client_id
        
        return client_id

    async def get(self, path:str=""):
        """
        Retrieve datastore data at the given path.
        """
        client_id = self._get_client_id()        
        
        last_etag_str: Optional[str] = self.request.headers.get("If-None-Match", None)
        server_etag = await ServerObjects.datastore.etag.value

        if last_etag_str is None or ServerObjects.datastore.parse_value(last_etag_str) != server_etag:
            # Etag was not sent or they don't match, read entire datastore.
            logger.info(f"{client_id}: Returning data as etags dont match. Header: {last_etag_str}, Datastore: {server_etag}")
            self.set_header("Etag", str(await ServerObjects.datastore.etag.value))
            self.write(ServerObjects.datastore.read(path))
            return

        # When there's an "If-None_Match" header containing the last etag, the client is long polling.
        # In this case, if the provided eTag matches the current eTag, wait up to 15 seconds for updates.
        logger.info(f"{client_id}: etag {last_etag_str} matches server - long poll call waiting 15 seconds for updates.")
        
        remainingTime = datetime.timedelta(seconds=15)
        startTime = datetime.datetime.now()

        while remainingTime > datetime.timedelta(seconds=0):
            if not await ServerObjects.datastore.wait_for_updates(timeout=remainingTime):
                # If wait_for_updates returned False, condition.notify_all was not called.
                # Therefore, as no updates were made before the timeout, Return an http/304.
                break

            # There was an update made before timeout.
            # Filter out updates from the same client or any that aren't relevant
            # to the scope of the request (ie not under the same path).
            updated_by = await ServerObjects.datastore.etag.updated_by
            
            if updated_by != client_id:                
                # An update was received after being made by another client.
                # Return only the updates that are relevant to the client.
                logger.info(f"{client_id}: New data received after update by {updated_by}.")                
                updates = ServerObjects.datastore.read_last_update(path)
                
                if updates:
                    self.set_header("Etag", str(await ServerObjects.datastore.etag.value))
                    self.write(updates)
                    return

                logger.info(f"{client_id}: No relevant updates were made so continuing to wait.")
            else:
                logger.info(f"{client_id}: Ignoring update made by the same client.")
                        
            # An update was received but it was made by this client or was not relevant.
            # Ignore and keep waiting for the remaining time of the original 15 seconds.
            # Clamp this to zero just in case we've gone over since the Condition fell through.
            #
            # We will fall out of the loop if remainingTime == 0, in this case this is the same as
            # having no updates before the timeout, so return an http/304
            remainingTime = max(datetime.timedelta(seconds=0), remainingTime - (datetime.datetime.now() - startTime))
            logger.info(f"{client_id}: Remaining time: {remainingTime}.")

        logger.info(f"{client_id}: Timed out waiting for update. Returning with HTTP/304 status.")
        self.set_header("Etag", str(await ServerObjects.datastore.etag.value))
        self.set_status(304)

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


async def run_tornado_server(datastore:Optional[str]=None, port:int=8888) -> None:
    setupDatastore(path=datastore)
    app = make_app()
    app.listen(port)
    logger.info(f"Server listening at http://localhost:{port}")
    logger.info(f"Datastore located at http://localhost:{port}/datastore")
    await asyncio.Event().wait()


async def main(
        register_server:Optional[bool]=True,
        discovery_name:Optional[str]="Motu Test Server",
        datastore:Optional[str]=None, port:int=8888
    ) -> None:
    tornado_task = asyncio.create_task(run_tornado_server(datastore, port))
    zcr = MotuZeroConfRegistration(register_server, discovery_name, port)
    register_task = asyncio.create_task(zcr.register())
    try:
        await asyncio.gather(tornado_task, register_task)
    except asyncio.CancelledError:
        logger.info("Main tasks cancelled. Cleaning up...")
    finally:
        await zcr.unregister()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted. Exiting gracefully...")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")