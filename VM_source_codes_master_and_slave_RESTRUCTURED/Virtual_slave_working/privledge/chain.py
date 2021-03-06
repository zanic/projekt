from __future__ import unicode_literals

import misc
import config

class Chain:
    def __init__(self):
        self.tail = None
        self.root = None
        self._list = []

    @property
    def list(self):
        return self._list

    @property
    def id(self):
        if self.root is not None:
            return self.root.message_hash
        else:
            return None

    def slice_chain(self, block_hash = None):
        # Return the whole list if no specific block hash is given
        if block_hash is None:
            return self._list
        else:
            # Step through the entire chain in reverse order
            for i, block in misc.reverse_enumerate(self._list):
                # If we have a match, return the sublist
                if block.hash == block_hash:
                    return self._list[i+1:]

            # The requested block isn't in our chain! Return None
            return None

    def search(self, query, match_block=True):
        """Search through the chain

        Arguments:
        query: search string
        match_block (default True): Match on block hash when True, otherwise match on message
        """

        # Walk backward through the list
        end = len(self._list) - 1

        # Prepare return lists
        idx = []
        blocks = []

        if match_block:
            while end >= 0:
                if self.list[end].hash == query:
                    idx.append(end)
                    blocks.append(self._list[end])

                end -= 1
        else:
            while end >= 0:
                if self.list[end].message_hash == query:
                    idx.append(end)
                    blocks.append(self._list[end])

                end -= 1

        return idx, blocks

    def append(self, block):
        from block import BlockType

        # Adding root (must be self-signed and key)
        if block.predecessor is None and self.root is None:

            # Check the block has the right type and is self-signed
            if block.blocktype is not BlockType.key or not block.validate(block.message):
                raise ValueError('Cannot add root block unless it is self-signed and of blocktype \'key\'',
                                 block.blocktype)

            self.root = block
            self.tail = block
            self._list.append(block)

        # Do some checks to make sure block is valid
        else:

            # Is this block's predecessor the last block in our chain?
            if not block.predecessor == self.tail.hash:
                raise ValueError('Predecessor hash does not match the last accepted block', block.predecessor,
                                 self.tail.hash)

            # Check that block signer (signatory_hash) is present on our chain and valid
            if not self.validate_block(block):
                raise ValueError('The block is not signed by an accepted key', block.signature)

            # Hash is correct, Signatory Exists, Signature is Valid: Add to chain!
            self._list.append(block)
            self.tail = block

    # Ensure that the provided hash is valid and has not been revoked
    def validate_block(self, block):
        from block import BlockType

        # Search through the chain for blocks with a message hash that matches the signatory hash
        idx, signatory = self.search(block.signatory_hash, match_block=False)

        # Check that the most recent block was of type key (not revoke)
        if signatory is not None and \
                len(signatory) > 0 and \
                signatory[0].blocktype is BlockType.key:
            return block.validate(signatory[0].message)
        else:
            return False

    def __len__(self):
        return len(self._list)
