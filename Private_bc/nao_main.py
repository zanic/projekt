import block
import settings
import utils
import messaging
from ledger import Ledger
import daemon

import json
import socket
import time


if __name__ == "__main__":
    # Initialize any global variables
    settings.init()
    daemon.disc_ledgers = daemon.discover()
    if len(daemon.disc_ledgers) == 0:
        privkey = utils.gen_privkey()
        # If we made it this far we have a valid key
        # Store generated key in our daemon for now
        daemon.create_ledger(privkey)
        hash = daemon.ledger.id

        print("\nPublic Key Hash: {0}".format(hash))
        utils.log_message("Added key ({0}) as a new Root of Trust".format(hash), utils.Level.FORCE)
    else:
        # Pass the daemon the hash and members
        print(list(daemon.disc_ledgers.keys())[0])
        print(list(list(daemon.disc_ledgers.values())[0]))
        daemon.join_ledger(list(daemon.disc_ledgers.keys())[0], list(list(daemon.disc_ledgers.values())[0])[0])
    while True:
        time.sleep(5)
        """
        temp = 'text'
        message = 'Test123'
        try:

            blocktype = block.BlockType[temp]

            new_block = block.Block(blocktype, daemon.ledger.tail.hash, message)
            new_block.sign(daemon.privkey)

            daemon.ledger.append(new_block)
            print("Added new block to ledger:")
            print('\n{}\n'.format(new_block))

        except KeyError as e:
            print("Could not add block: {} is not a valid blocktype".format(e))
        except ValueError as e:
            print("Could not add block: {}".format(e))        
        """