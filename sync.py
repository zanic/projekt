from block import Block
import os, json

def sync():
	node_blocks = []
	chaindata_dir = 'chaindata'
        if not os.path.exists(chaindata_dir):
		os.mkdir(chaindata_dir)

	if os.path.exists(chaindata_dir):
		for filename in os.listdir(chaindata_dir):
                    if filename.endswith('.json'):
			filepath = '%s/%s' % (chaindata_dir, filename)
			with open(filepath, 'r') as block_file:
				block_info = json.load(block_file)
				block_object = Block(block_info)
				node_blocks.append(block_object)
	return node_blocks
