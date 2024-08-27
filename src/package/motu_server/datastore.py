import json
import logging
import datetime
from tornado.locks import Condition, Lock
from typing import Optional, Union, Any

# Typing of datastore dictionary
# keys are strings, values can be dictionaries, string, float, int
DatastoreDictValues = dict[str, Union[dict, int, str, float]]
DatastoreDict = dict[str, Union[DatastoreDictValues, Any]]

logger: logging.Logger = logging.getLogger(__name__)


class ETag:
    """
    Represents an etag keeping track of updates.

    Uses a tornado.locks.Lock to ensure that updates
    are kept in sync.
    """
    def __init__(self) -> None:
        self._value:int = 0
        self._client_id: Optional[int] = None
        self.tag_lock: Lock = Lock()
        self.tag_condition: Condition = Condition()

    @property
    async def updated_by(self) -> Optional[int]:
        """
        Which client made the last update.
        """
        async with self.tag_lock:
            return self._client_id

    @property
    async def value(self) -> int:
        """
        The current value of the eTag
        """
        async with self.tag_lock:
            return self._value

    async def increment(self, client_id: Optional[int]=None) -> None:
        """
        Increment the eTag, optionally with a client
        identifier to determine which client made the update.
        """
        async with self.tag_lock:
            self._value += 1
            if client_id is not None:
                self._client_id = client_id

        logger.info(f"{client_id}: New eTag value: {self._value}, set by {self._client_id}")
        self.tag_condition.notify_all()


class Datastore:
    """
    Virtual implementation of the MOTU AVB datastore.
    """
    def __init__(self, initial_state: Optional[Union[str, DatastoreDict]]=None) -> None:
        """
        Initialises the Datastore, loading state from
        a json file or dictionary, if provided.
        """
        self.etag = ETag()
        self.datastoreLock = Lock()

        self._datastore: DatastoreDict = {}

        if initial_state:
            if isinstance(initial_state, str):
                with open(initial_state) as f:
                    self._datastore = json.load(f)

                logger.info(f"Loaded datastore state from file {initial_state}")
            elif isinstance(initial_state, dict):
                self._datastore = initial_state
                logger.info("Loaded datastore state from dictionary")
            else:
                logger.info(f"Unable to load datastore state from provided state: {initial_state}")

    def _flatten_tree(self, tree, basePath: str="") -> DatastoreDict:
        """
        Flattens a dictionary into a dictionary of single paths.

        e.g.

        { "mix": { "chan": { "0": { "name": "Channel Name" }}}}

        becomes:

        { "mix/chan/0/name": "Channel Name"}
        """
        res: DatastoreDict = {}

        for k, v in tree.items():
            currentPath = f"{basePath}/{k}" if basePath else k

            if isinstance(v, dict):
                res.update(self._flatten_tree(v, currentPath))
            else:
                res[currentPath] = v    

        return res
    
    def _parse_value(self, value: str) -> Union[str, int, float]:
        """
        Parses a value as integar, float or stirng from the given value.
        """
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    
    def _expand_tree(self, values: dict, base_path:Optional[str]=None) -> DatastoreDict:
        """
        Expands the given dictionary of paths into a dictionary.

        e.g.

        { "mix/chan/0/name": "Channel Name"}

        becomes:

        { "mix": { "chan": { "0": { "name": "Channel Name" }}}}
        """
        def _insert_tree(r, parts, value):
            """
            Recursively insert the values into the tree
            """
            r[parts[0]] = self._parse_value(value) if len(parts) == 1 else _insert_tree(r.get(parts[0], {}), parts[1:], value)
            return r

        res: DatastoreDict = {}

        for k, v in values.items():
            parts = (base_path.split("/") if base_path else []) + (k.split("/") if k != "value" else [])            
            _insert_tree(res, parts, v)

        return res
    
    def _update_nested(
        self, 
        original: DatastoreDict,
        updates: dict[str, Union[dict, str, int, float]]
    ) -> None:
        """
        Makes nested updates to the original dictionary without
        erasing values that aren't in the updates dictionary.
        """
        for k, v in updates.items():
            if isinstance(v, dict) and k in original:
                self._update_nested(original[k], v)
            else:
                original[k] = v

    def read(self, path: Optional[str]=None) -> DatastoreDict:
        """
        Read datastore values at the given path. If none given, read all values.
        """
        if not path:
            return self._flatten_tree(self._datastore)
        
        currentLevel = self._datastore
        for level in path.split("/"):
            currentLevel = currentLevel.get(level, {})

        if isinstance(currentLevel, dict):        
            return self._flatten_tree(currentLevel)
        else:
            return { "value": currentLevel }
        
    async def wait_for_updates(self, timeout:Union[int, datetime.timedelta]=15) -> bool:
        """
        Wait for updates to the eTag.
        """
        if isinstance(timeout, int):
            timeout = datetime.timedelta(seconds=timeout)

        return await self.etag.tag_condition.wait(timeout=timeout)

    async def write(
        self,
        base_path: str,
        values: dict[str, Union[str, float, int]],
        client_id: Optional[int]=None
    ) -> None:
        """
        Write the values under the given base path.
        """
        async with self.datastoreLock:
            self._update_nested(self._datastore, self._expand_tree(values, base_path))

        await self.etag.increment(client_id)        

    