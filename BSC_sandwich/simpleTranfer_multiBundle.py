import aiohttp
import asyncio
import ssl

from web3 import Web3
from web3.middleware import geth_poa_middleware


class BundleSubmitter:
    def __init__(self,refund_addr):
        self.refund_address = refund_addr
        self.headers_general = {
            "Content-Type": "application/json"
        }
        self.headers_bloxRoute = {
            "Content-Type": "application/json",
            "Authorization": "... input your key"
        }
        self.headers_blockSmith = {
            "Content-Type": "application/json",
            "Authorization": "... input your key"
        }
        self.headers_blockRazor = {
            "Content-Type": "application/json",
            "Authorization": "... input your key"
        }
        self.endpoint_apikey_nodeReal = '... input your key'

        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    async def submit_bundle_bloxRoute(self, tx_list, block_no):
        data = {
            "id": "1",
            "method": "blxr_submit_bundle",
            "params": {
                "transaction": [tx[2:] for tx in tx_list],
                "blockchain_network": "BSC-Mainnet",
                "block_number": web3.to_hex(block_no),
                "mev_builders": {"all": ""},
                "refund_recipient": self.refund_address
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://api.blxrbdn.com",
                    headers=self.headers_bloxRoute,
                    json=data,
                    ssl = self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json

    async def submit_bundle_blockSmith(self, tx_list, block_no):
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendBundle",
            "params": [
            {
              "txs": tx_list,
              "blockNumber": web3.to_hex(block_no),
              # "minTimestamp": 0,
              # "maxTimestamp": 1615920932
            }
          ]

        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://fastbundle-us.blocksmith.org/",
                    headers=self.headers_blockSmith,
                    json=data,
                    ssl=self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json

    async def submit_bundle_blockRazor(self, tx_list, block_no):
        data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendBundle",
            "params": [
                {
                    "txs": tx_list,
                    "maxBlockNumber": block_no # numerical
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://blockrazor-builder-frankfurt.48.club",
                    headers=self.headers_blockRazor,
                    json=data,
                    ssl=self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json
    async def submit_bundle_nodeReal(self, tx_list, block_no):
        data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_sendBundle",
                "params": [
                    {
                        "txs": tx_list,
                        "maxBlockNumber": block_no, # numerical
                    }
                ]
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    self.endpoint_apikey_nodeReal,
                    headers=self.headers_general,
                    json=data,
                    ssl = self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json

    async def submit_bundle_jetBldr(self, tx_list, block_no):
        data = {
                  "jsonrpc": "2.0",
                  "id": 1,
                  "method": "eth_sendBundle",
                  "params": [
                    {
                      "txs": tx_list,
                      "maxBlockNumber": block_no, # numerical
                    }
                  ]
                }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://rpc.bsc-ap.jetbldr.xyz/",
                    headers=self.headers_general,
                    json=data,
                    ssl = self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json

    async def submit_bundle_puissant(self, tx_list, block_no):
        data = {
                  "jsonrpc": "2.0",
                  "id": "1",
                  "method": "eth_sendBundle",
                  "params": [
                    {
                      "txs":tx_list,
                      "maxBlockNumber":block_no,   # numerical
                    }
                  ]
                }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://puissant-builder.48.club/",
                    headers=self.headers_general,
                    json=data,
                    ssl = self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json

    async def submit_bundle_darwinbuilder(self, tx_list, block_no):
        data = {
                  "jsonrpc": "2.0",
                  "id": "1",
                  "method": "eth_sendBundle",
                  "params": [
                    {
                      "txs":tx_list,
                      "blockNumber":web3.to_hex(block_no),
                    }
                  ]
                }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://bsc-builder-eu.darwinbuilder.xyz",
                    headers=self.headers_general,
                    json=data,
                    ssl = self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json

    async def submit_bundle_blockBus(self, tx_list, block_no):
        data = {
                  "jsonrpc": "2.0",
                  "id": "1",
                  "method": "eth_sendBundle",
                  "params": [
                    {
                      "txs":tx_list,
                      "maxBlockNumber":block_no,   # numerical
                    }
                  ]
                }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    "https://bsc-virginia.blockbus.xyz",
                    headers=self.headers_general,
                    json=data,
                    ssl = self.ssl_context
            ) as response:
                if response.status == 200:
                    print(f'success with {response}')
                    return await response.json()
                else:
                    response_json = {
                        "status_code": response.status,
                        "content": await response.text()
                    }
                    print(f'error happened {response_json}')
                    return response_json


def create_raw_tx( to_address,value, gas_price, nonce, private_key):

    gas = 21000

    chain_id = 56

    transaction = {
            "to": to_address,
            "value": value,
            "gas": gas,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": chain_id
        }
    signed_tx = web3.eth.account.sign_transaction(transaction, private_key)
    # raw_tx = signed_tx.rawTransaction.hex()
    return signed_tx


infura_url = '... input your rpc url for node'
web3 = Web3(Web3.HTTPProvider(infura_url))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


test_account = web3.to_checksum_address("... input your wallet adress")
private_key = "... input your private key"
test_account_2 = web3.to_checksum_address('0x05099F60453A0E3d73cd1d8B93D0eA8aC7a7DFd5') # test account 2

bribeEOA_bloxRoute = web3.to_checksum_address('0x74c5F8C6ffe41AD4789602BDB9a48E6Cad623520')
bribeEOA_blockSmith = web3.to_checksum_address('0x0000000000007592b04bB3BB8985402cC37Ca224')
bribeEOA_blockRazor = web3.to_checksum_address('0x1266C6bE60392A8Ff346E8d5ECCd3E69dD9c5F20')
bribeEOA_jetBldr = web3.to_checksum_address('0xe89c42BC188c993273Ab34231e12ae60c73042E4')
bribeEOA_puissant = web3.to_checksum_address('0x4848489f0b2BEdd788c696e2D79b6b69D7484848')
bribeEOA_blockBus = web3.to_checksum_address('0x1319Be8b8Ec4AA81f501924BdCF365fBcAa8d753')

# account info
nonce = web3.eth.get_transaction_count(test_account)
balance = web3.eth.get_balance(test_account)
result = web3.from_wei(balance,'ether')
print(f'Balance of the account {result}')
bribe_amount = int(balance*0.01)
transfer_amount = int(balance*0.01)
gas_price = web3.to_wei('1', 'gwei')

# create bribe tx
bribeTx_bloxRoute = create_raw_tx(bribeEOA_bloxRoute,bribe_amount,gas_price,nonce, private_key)
bribeTx_blockSmith = create_raw_tx(bribeEOA_blockSmith,bribe_amount,gas_price,nonce, private_key)
bribeTx_blockRazor = create_raw_tx(bribeEOA_blockRazor,bribe_amount,gas_price,nonce, private_key)
bribeTx_jetBldr = create_raw_tx(bribeEOA_jetBldr,bribe_amount,gas_price,nonce, private_key)
bribeTx_puissant = create_raw_tx(bribeEOA_puissant,bribe_amount,gas_price,nonce, private_key)
bribeTx_blockBus = create_raw_tx(bribeEOA_blockBus,bribe_amount,gas_price,nonce, private_key)

# create a simple transfer
ETH_transfer_afterBribe = create_raw_tx(test_account,0,gas_price,nonce+1, private_key)
ETH_transfer_noBribe = create_raw_tx(test_account,0,gas_price,nonce, private_key)

# bundle info
block_number = int(web3.eth.block_number+2)

bundle_info = [
    ([bribeTx_bloxRoute.rawTransaction.hex(),ETH_transfer_afterBribe.rawTransaction.hex()],block_number), # for bloxRoute submit tx hash without 0x prefix
    ([bribeTx_blockSmith.rawTransaction.hex(),ETH_transfer_afterBribe.rawTransaction.hex()], block_number),    # blocksmith
    ([bribeTx_blockRazor.rawTransaction.hex(),ETH_transfer_afterBribe.rawTransaction.hex()],block_number),         # blocrazor
    ([ETH_transfer_noBribe.rawTransaction.hex()],block_number),                                                    # nodeReal
    ([bribeTx_jetBldr.rawTransaction.hex(),ETH_transfer_afterBribe.rawTransaction.hex()],block_number),            # jetBldr
    ([bribeTx_puissant.rawTransaction.hex(),ETH_transfer_afterBribe.rawTransaction.hex()],block_number),            # puissant
    ([ETH_transfer_noBribe.rawTransaction.hex()],block_number),                                                    # darwinbuilder
    ([bribeTx_blockBus.rawTransaction.hex(),ETH_transfer_afterBribe.rawTransaction.hex()],block_number)            # darwinbuilder
]

async def main(bundle_info, refund_address):
    submitter = BundleSubmitter(refund_address)

    await asyncio.gather(
        submitter.submit_bundle_bloxRoute(bundle_info[0][0], bundle_info[0][1]),
        submitter.submit_bundle_blockSmith(bundle_info[1][0], bundle_info[1][1]),
        submitter.submit_bundle_blockRazor(bundle_info[2][0], bundle_info[2][1]),
        submitter.submit_bundle_nodeReal(bundle_info[3][0], bundle_info[3][1]),
        submitter.submit_bundle_jetBldr(bundle_info[4][0], bundle_info[4][1]),
        submitter.submit_bundle_puissant(bundle_info[5][0], bundle_info[5][1]),
        # submitter.submit_bundle_darwinbuilder(bundle_info[6][0], bundle_info[6][1]),  # currently does not work
        submitter.submit_bundle_blockBus(bundle_info[7][0], bundle_info[7][1])
    )

print('start to submit')
asyncio.run(main(bundle_info,test_account))

