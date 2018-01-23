import block
import config
import misc
import messaging
from chain import Chain
import daemon

import json
import socket
import time


if __name__ == "__main__":
    # Initialize any global variables
    config.init()
    daemon.disc_chains = daemon.discover()
    if len(daemon.disc_chains) == 0:
        privkey = misc.gen_privkey()
        # If we made it this far we have a valid key
        # Store generated key in our daemon for now
        daemon.create_chain(privkey)
        hash = daemon.chain.id

        print("\nPublic Key Hash: {0}".format(hash))
        misc.log_message("Added key ({0}) as a new Root of Trust".format(hash), misc.Level.FORCE)
    else:
        # Pass the daemon the hash and members
        print(list(daemon.disc_chains.keys())[0])
        print(list(list(daemon.disc_chains.values())[0]))
        daemon.join_chain(list(daemon.disc_chains.keys())[0], list(list(daemon.disc_chains.values())[0])[0])
    while True:
        time.sleep(5)
        """
        temp = 'text'
        message = 'Test123'
        try:

            blocktype = block.BlockType[temp]

            new_block = block.Block(blocktype, daemon.chain.tail.hash, message)
            new_block.sign(daemon.privkey)

            daemon.chain.append(new_block)
            print("Added new block to chain:")
            print('\n{}\n'.format(new_block))

        except KeyError as e:
            print("Could not add block: {} is not a valid blocktype".format(e))
        except ValueError as e:
            print("Could not add block: {}".format(e))        
        """