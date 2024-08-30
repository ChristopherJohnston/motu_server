"""
Tests for the datastore module
"""
import unittest
import datetime
import pytest
from motu_server.datastore import ETag, Datastore

class ETagTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        self.etag = ETag()

    @pytest.mark.asyncio
    async def test_increment(self):
        self.assertEqual(await self.etag.value, 0)
        await self.etag.increment(client_id=1001)
        self.assertEqual(await self.etag.value, 1)
        self.assertEqual(await self.etag.updated_by, 1001)
    

class DatastoreTests(unittest.IsolatedAsyncioTestCase):
    """
    Tests the datastore class
    """
    def setUp(self):
        super().setUp()
        initState = {
            "mix": {
                "aux": {
                    "0": {
                        "matrix": {
                            "mute": 0.0,
                            "fader": 1.0,
                            "pan": 0.0
                        }
                    }            
                },
                "chan": {
                    "0": {
                        "matrix": {
                            "aux": {
                                "0": {
                                    "send": 1.0,
                                    "pan": 0.0
                                }
                            }
                        }
                    },
                    "1": {
                        "matrix": {
                            "aux": {
                                "0": {
                                    "send": 1.0,
                                    "pan": 0.0
                                }
                            }
                        }
                    },
                },
                "group": {
                    "0": {
                        "matrix": {
                            "aux": {
                                "0": {
                                    "send": 1.0,
                                    "pan": 0.0
                                }
                            }
                        }            
                    }
                },
                "reverb": {
                    "0": {
                        "matrix": {
                            "aux": {
                                "0": {
                                    "send": 1.0,
                                    "pan": 0.0
                                }
                            }                    
                        }
                    }
                }
            },             
        }
        self.ds = Datastore(initState)

    def test__flatten_tree(self):
        res = self.ds._flatten_tree({
            "mix": {
                "chan": {
                    "0": {
                        "name": "Channel 0"
                    }
                },
                "group": {
                    "0": {
                        "matrix": {
                            "aux": {
                                "0": {
                                    "send": 1.0
                                }
                            }
                        }
                    }
                }
            }
        })
        self.assertEqual(res, {
            "mix/chan/0/name": "Channel 0",
            "mix/group/0/matrix/aux/0/send": 1.0
        })

    def test_parse_value(self):
        self.assertEqual(self.ds.parse_value("1"), 1)
        self.assertEqual(self.ds.parse_value("1.0"), 1.0)
        self.assertEqual(self.ds.parse_value("Channel1"), "Channel1")

    def test__expand_tree(self):
        inputs = {
            "0/name": "ibank0",
            "0/ch/0/name": "ibank0ch0",
            "0/ch/0/defaultName": "ibank0ch0Default",

            "1/name": "ibank1",
            "1/ch/0/name": "ibank1ch0",
            "1/ch/0/defaultName": "ibank1ch0Default",

            "2/name": "ibank2",
            "2/ch/0/name": "ibank2ch0",
            "2/ch/0/defaultName": "ibank2ch0Default",
        }
        res = self.ds._expand_tree(inputs, "ext/ibank")
        print(res)
        self.assertEqual(res, {
            "ext": {
                "ibank": {
                    "0": {
                        "name": "ibank0",
                        "ch": {
                            "0": {
                                "name": "ibank0ch0",
                                "defaultName": "ibank0ch0Default"
                            }
                        }
                    },
                    "1": {
                        "name": "ibank1",
                        "ch": {
                            "0": {
                                "name": "ibank1ch0",
                                "defaultName": "ibank1ch0Default"
                            }
                        }
                    },
                    "2": {
                        "name": "ibank2",
                        "ch": {
                            "0": {
                                "name": "ibank2ch0",
                                "defaultName": "ibank2ch0Default"
                            }
                        }
                    }
                }
            }
        })

    def test__update_nested(self):
        o = {
            "mix": {
                "chan": {
                    "0": {
                        "name": "oldName",
                        "defaultName": "defaultName"
                    }
                }
            }
        }

        u = {
            "mix": {
                "chan": {
                    "0": {
                        "name": "newName",
                    }
                }
            }
        }

        self.ds._update_nested(o, u)

        self.assertEqual(o, {
            "mix": {
                "chan": {
                    "0": {
                        "name": "newName",
                        "defaultName": "defaultName"
                    }
                }
            }
        })

    def test_read(self):
        # single value
        self.assertEqual(self.ds.read("mix/aux/0/matrix/fader"), { "value": 1.0 })

        # multi-values
        self.assertEqual(self.ds.read("mix/aux/0/matrix"), {
            "fader": 1.0,
            "pan": 0.0,
            "mute": 0.0
        })

    async def test_wait_for_updates(self):
        res = await self.ds.wait_for_updates(datetime.timedelta(milliseconds=1))
        self.assertFalse(res)

    async def test_write(self):
        self.assertEqual(await self.ds.etag.value, 0)

        await self.ds.write("mix/aux/0/matrix", {
            "fader": 0.0,
            "pan": -1.0,
            "mute": 1
        })
        self.assertEqual(await self.ds.etag.value, 1)

        self.assertEqual(self.ds.read("mix/aux/0/matrix"), {
            "fader": 0.0,
            "pan": -1.0,
            "mute": 1
        })