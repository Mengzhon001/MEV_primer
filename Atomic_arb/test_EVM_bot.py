
import asyncio
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from collections import deque
from typing import List, Tuple

import aiohttp
import brownie
import eth_abi
import eth_account
import flashbots
import web3
import websockets

import degenbot as bot

BROWNIE_NETWORK = "mainnet-local-ws"
BROWNIE_ACCOUNT = "mainnet_bot"
FLASHBOTS_IDENTITY_ACCOUNT = "flashbots_id"

MULTICALL_FLUSH_INTERVAL = 1000

FLASHBOTS_RELAY_URL = "https://relay.flashbots.net"

WEBSOCKET_URI = "ws://localhost:8546"

ETHERSCAN_API_KEY = "[redacted]"

ARB_CONTRACT_ADDRESS = "[redacted]"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
MULTICALL_ADDRESS = "0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696"

MIN_PROFIT_ETH = int(0.000 * 10**18)

FLASHBOTS_MINER_TIP = 0.9  # % of profit to bribe the miner (via relay)

DRY_RUN = True

RELAY_RETRIES = 3

VERBOSE_ACTIVATION = True
VERBOSE_BLOCKS = True
VERBOSE_EVENTS = False
VERBOSE_PROCESSING = True
VERBOSE_RELAY_SIMULATION = True
VERBOSE_TIMING = False
VERBOSE_UPDATES = False
VERBOSE_WATCHDOG = True

ARB_ONCHAIN_ENABLE = True

# require min. number of simulations before evaluating the cutoff threshold
SIMULATION_CUTOFF_MIN_ATTEMPTS = 10
# arbs that fail simulations greater than this percentage will be added to a blacklist
SIMULATION_CUTOFF_FAIL_THRESHOLD = 0.8

AVERAGE_BLOCK_TIME = 12
# how many seconds behind the chain timestamp to consider the block
# "late" and disable processing until it catches up
LATE_BLOCK_THRESHOLD = 3


async def _main_async():

    with ThreadPoolExecutor() as executor:
        asyncio.get_running_loop().set_default_executor(executor)
        tasks = [
            asyncio.create_task(coro)
            for coro in [
                activate_arbs(),
                load_arbs(),
                refresh_pools(),
                remove_failed_arbs(),
                status_watchdog(),
                track_balance(),
                watch_events(),
                watch_new_blocks(),
            ]
        ]
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"main: {e}")
            print(type(e))


async def activate_arbs():

    while True:

        await asyncio.sleep(AVERAGE_BLOCK_TIME)

        if status_paused:
            continue

        # identify all possible arbs (regardless of profit) that have not been
        # simulated for gas
        arbs_to_process = (
            arb_helper
            for arb_helper in degenbot_cycle_arb_helpers.copy().values()
            if not arb_helper.gas_estimate
        )

        while True:

            await asyncio.sleep(0)

            try:
                arb_helper = next(arbs_to_process)
            except StopIteration:
                break
            except Exception as e:
                print(e)
                print(type(e))

            try:
                arb_helper.auto_update(block_number=newest_block)
                arb_helper.calculate_arbitrage()
            except bot.exceptions.ArbitrageError as e:
                # print(e)
                continue
            except Exception as e:
                if VERBOSE_ACTIVATION:
                    print(f"estimate_arbs: {e}")
                    print(type(e))
                continue
            else:
                # the arb will only reach this block if it is up-to-date
                # and calculate_arbitrage has generated a valid payload
                test_onchain_arb_gas(
                    arb_id=arb_helper.id, block_number=newest_block
                )


async def execute_arb_with_relay(
    arb_dict: dict,
    state_block: int,
    target_block: int,
    arb_id=None,
    backrun_mempool_tx=None,
    frontrun_mempool_tx=None,
):

    global arb_simulations

    # yield to event loop and check the target block, abandon if the block has already arrived
    await asyncio.sleep(0)
    if target_block <= newest_block:
        return

    # get a pointer to the arb helper
    # BUGFIX: check for None since the arb may have been blacklisted with executions pending on the event loop
    if not (arb_helper := degenbot_cycle_arb_helpers.get(arb_id)):
        return

    if VERBOSE_TIMING:
        start = time.monotonic()
        print("starting execute_arb_with_relay")

    tx_params = {
        "from": bot_account.address,
        "chainId": brownie.chain.id,
        "gas": arb_gas
        if (arb_gas := int(1.25 * arb_helper.gas_estimate))
        else 2_000_000,
        "nonce": bot_account.nonce,
        "maxFeePerGas": next_base_fee,
        "maxPriorityFeePerGas": 0,
        "value": 0,
    }

    arb_payloads = arb_helper.generate_payloads(
        from_address=arb_contract.address
    )

    transactions_to_bundle = (
        w3.eth.contract(address=arb_contract.address, abi=arb_contract.abi)
        .functions.execute_payloads(arb_payloads)
        .buildTransaction(tx_params),
    )

    # bundle the backrun (with the backrun mempool_tx at first position)
    bundle = []
    if backrun_mempool_tx:
        bundle.append({"signed_transaction": backrun_mempool_tx})
    for transaction in transactions_to_bundle:
        tx = eth_account.Account.from_key(
            bot_account.private_key
        ).sign_transaction(transaction)
        signed_tx = tx.rawTransaction
        bundle.append({"signed_transaction": signed_tx})
    if frontrun_mempool_tx:
        bundle.append({"signed_transaction": frontrun_mempool_tx})

    # simulate the bundle if part of a frontrun/backrun,
    # skip for a single TX
    if frontrun_mempool_tx or backrun_mempool_tx:
        attempts = 0
        while True:
            if attempts == RELAY_RETRIES:
                return

            try:
                attempts += 1
                simulation = w3.flashbots.simulate(
                    bundled_transactions=bundle,
                    state_block_tag=w3.toHex(state_block),
                    block_tag=target_block,
                    block_timestamp=newest_block_timestamp
                    + AVERAGE_BLOCK_TIME,
                )
            except ValueError as e:
                print(f"execute_arb_with_relay (simulate): {e}")
                await asyncio.sleep(0.5)
                continue
            except Exception as e:
                print(f"Relay Error: {e}")
                print(f"Type: {type(e)}")
                print(f"Arb ID: {arb_helper.id}")
                await asyncio.sleep(0.5)
                continue
            else:
                arb_simulations[arb_id]["simulations"] += 1
                for result in simulation.get("results"):
                    if result.get("error"):
                        if VERBOSE_RELAY_SIMULATION:
                            print(result.get("revert"))
                        arb_simulations[arb_id]["failures"] += 1
                        return
                break

        simulated_gas_use = sum(
            [
                tx.get("gasUsed")
                for tx in simulation.get("results")
                if tx.get("fromAddress") == bot_account.address
            ]
        )

        arb_helper.gas_estimate = simulated_gas_use

    gas_fee = arb_helper.gas_estimate * next_base_fee
    arb_net_profit = arb_dict.get("profit_amount") - gas_fee

    if arb_net_profit > MIN_PROFIT_ETH and not DRY_RUN:

        print()
        if backrun_mempool_tx:
            print("*** BACKRUN ARB (RELAY) ***")
        elif frontrun_mempool_tx:
            print("*** FRONTRUN ARB (RELAY) ***")
        else:
            print("*** ONCHAIN ARB (RELAY) ***")
        print(f"Arb    : {arb_helper}")
        print(f"Profit : {arb_dict.get('profit_amount')/(10**18):0.5f} ETH")
        print(f"Gas    : {gas_fee/(10**18):0.5f} ETH")
        print(f"Net    : {arb_net_profit/(10**18):0.5f} ETH")

        # set the miner bribe as a quantity of ETH
        bribe = int(FLASHBOTS_MINER_TIP * arb_net_profit)
        bribe_gas = bribe // arb_helper.gas_estimate

        print(f"BRIBE SET TO {bribe/(10**18):0.5f} ETH")

        tx_params.update(
            {
                "maxFeePerGas": next_base_fee + bribe_gas,
                "maxPriorityFeePerGas": bribe_gas,
            }
        )

        transactions_to_bundle = (
            w3.eth.contract(address=arb_contract.address, abi=arb_contract.abi)
            .functions.execute_payloads(arb_payloads)
            .buildTransaction(tx_params),
        )

        # bundle the arb (with the frontrun/backrun mempool TXs at the start or end)
        bundle = []
        if backrun_mempool_tx:
            bundle.append({"signed_transaction": backrun_mempool_tx})
        for transaction in transactions_to_bundle:
            tx = eth_account.Account.from_key(
                bot_account.private_key
            ).sign_transaction(transaction)
            signed_tx = tx.rawTransaction
            bundle.append({"signed_transaction": signed_tx})
        if frontrun_mempool_tx:
            bundle.append({"signed_transaction": frontrun_mempool_tx})

        print("Bundle built!")
        print("Simulating bundle!")

        # simulate with the final gas values before submitting, retrying up to 5 times
        attempts = 0
        while True:
            if attempts == RELAY_RETRIES:
                return

            try:
                attempts += 1
                simulation = w3.flashbots.simulate(
                    bundled_transactions=bundle,
                    state_block_tag=w3.toHex(state_block),
                    block_tag=target_block,
                    block_timestamp=newest_block_timestamp + 10,
                )
            except ValueError as e:
                print(f"Relay Error (ValueError): {e}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Relay Error (other): {e}")
                print(f"Type: {type(e)}")
                await asyncio.sleep(0.5)
            else:
                for result in simulation.get("results"):
                    if result.get("error"):
                        if VERBOSE_RELAY_SIMULATION:
                            print(result.get("revert"))
                        return
                simulated_gas_use = sum(
                    [
                        tx.get("gasUsed")
                        for tx in simulation.get("results")
                        if tx.get("fromAddress") == bot_account.address
                    ]
                )
                break

        print(f'Simulation: {simulation.get("results")}')
        print(f"Gas       : {simulated_gas_use}")
        print(f"bundleHash: {simulation.get('bundleHash')}")

        if backrun_mempool_tx or frontrun_mempool_tx:
            bundle_valid_blocks = 5
        else:
            bundle_valid_blocks = 1

        # submit the bundle to the relay, retrying up to RELAY_RETRIES times per valid block
        attempts = 0
        # BUGFIX: track the submitted blocks separately, some bundles were not being recorded accurately
        submitted_blocks = []
        for i in range(bundle_valid_blocks):

            while True:

                if attempts == RELAY_RETRIES:
                    return

                await asyncio.sleep(0)

                try:
                    attempts += 1
                    print(
                        f"Sending bundle targeting block {target_block +  i}"
                    )
                    w3.flashbots.send_bundle(
                        bundle,
                        target_block_number=target_block + i,
                    )
                except Exception as e:
                    print(e)
                    await asyncio.sleep(0.25)
                else:
                    submitted_blocks.append(target_block + i)
                    attempts = 0  # reset counter for next block
                    break

        print("Bundle sent!")
        # record the bundle hash, signed TX, and all successfully submitted blocks
        record_bundle(
            bundle_hash=simulation.get("bundleHash"),
            blocks=submitted_blocks,
            tx=[tx.get("signed_transaction").hex() for tx in bundle],
            arb_id=arb_id,
        )
        print("Bundle recorded!")

        # zero out the mempool dict after submitting
        # NOTE: leaves the `best` dict in place in case this arb is valid next block
        if backrun_mempool_tx or frontrun_mempool_tx:
            arb_helper.clear_best_future()

    if VERBOSE_TIMING:
        print(
            f"send_arb_via_relay completed in {time.monotonic() - start:0.4f}s"
        )


async def load_arbs():

    print("Starting arb loading function")

    global degenbot_lp_helpers
    global degenbot_cycle_arb_helpers
    global arb_simulations

    # liquidity_pool_and_token_addresses will filter out any blacklisted addresses, so helpers should draw from this as the "official" source of truth
    liquidity_pool_data = {}
    for filename in [
        "ethereum_sushiswap_lps.json",
        "ethereum_uniswapv2_lps.json",
        "ethereum_uniswapv3_lps.json",
    ]:
        with open(filename) as file:
            for pool in json.load(file):
                pool_address = pool.get("pool_address")
                token0_address = pool.get("token0")
                token1_address = pool.get("token1")
                if (
                    token0_address in BLACKLISTED_TOKENS
                    or token1_address in BLACKLISTED_TOKENS
                ):
                    continue
                else:
                    liquidity_pool_data[pool_address] = pool
    print(f"Found {len(liquidity_pool_data)} pools")

    arb_paths = []
    for filename in [
        "ethereum_arbs_2pool_withv3.json",
        # "ethereum_arbs_triangle.json",
    ]:
        with open(filename) as file:
            for arb_id, arb in json.load(file).items():
                passed_checks = True
                if arb_id in BLACKLISTED_ARBS:
                    passed_checks = False
                for pool_address in arb.get("path"):
                    if not liquidity_pool_data.get(pool_address):
                        passed_checks = False
                if passed_checks:
                    arb_paths.append(arb)
    print(f"Found {len(arb_paths)} arb paths")

    # Identify all unique pool addresses in arb paths
    unique_pool_addresses = {
        pool_address
        for arb in arb_paths
        for pool_address in arb.get("path")
        if liquidity_pool_data.get(pool_address)
    }
    print(f"Found {len(unique_pool_addresses)} unique pools")

    # Identify all unique token addresses, checking if the pool is present in pools_and_tokens (pre-checked against the blacklist)
    # note: | is the operator for a set 'union' method
    unique_tokens = (
        # all token0 addresses
        {
            token_address
            for arb in arb_paths
            for pool_address in arb.get("path")
            for pool_dict in arb.get("pools").values()
            if (token_address := pool_dict.get("token0"))
            if liquidity_pool_data.get(pool_address)
        }
        |
        # all token1 addresses
        {
            token_address
            for arb in arb_paths
            for pool_address in arb.get("path")
            for pool_dict in arb.get("pools").values()
            if (token_address := pool_dict.get("token1"))
            if liquidity_pool_data.get(pool_address)
        }
    )
    print(f"Found {len(unique_tokens)} unique tokens")

    # build a dict of Erc20Token helper objects, keyed by address
    degenbot_token_helpers = {}

    event_loop = asyncio.get_running_loop()

    start = time.time()

    for token_address in unique_tokens:
        await asyncio.sleep(0)
        try:
            token_helper = await event_loop.run_in_executor(
                None,
                partial(
                    bot.Erc20Token,
                    address=token_address,
                    silent=True,
                    unload_brownie_contract_after_init=True,
                ),
            )
        except ValueError:
            BLACKLISTED_TOKENS.append(token_address)
        except Exception as e:
            print(e)
            print(type(e))
        else:
            if VERBOSE_PROCESSING:
                print(f"Created token helper: {token_helper}")
            # add the helper to the dict of token objects, keyed by address
            degenbot_token_helpers[token_helper.address] = token_helper

    print(
        f"Built {len(degenbot_token_helpers)} tokens in {time.time() - start :.2f}s"
    )

    with open("ethereum_blacklisted_tokens.json", "w") as file:
        json.dump(BLACKLISTED_TOKENS, file, indent=2)

    start = time.time()

    event_loop = asyncio.get_running_loop()

    lens = (
        bot.uniswap.v3.TickLens()
    )  # create a lens object, used by all V3 pools

    for pool_address in unique_pool_addresses:

        # skip pools holding tokens that could not be loaded
        if not (
            token0_obj := degenbot_token_helpers.get(
                liquidity_pool_data.get(pool_address).get("token0")
            )
        ) or not (
            token1_obj := degenbot_token_helpers.get(
                liquidity_pool_data.get(pool_address).get("token1")
            )
        ):
            continue

        pool_type = liquidity_pool_data[pool_address]["type"]

        try:
            if pool_type == "UniswapV2":
                pool_helper = await event_loop.run_in_executor(
                    None,
                    partial(
                        bot.LiquidityPool,
                        address=pool_address,
                        tokens=[token0_obj, token1_obj],
                        update_method="external",
                        silent=True,
                        abi=bot.uniswap.v2.abi.UNISWAPV2_LP,
                    ),
                )

            elif pool_type == "UniswapV3":
                pool_helper = await event_loop.run_in_executor(
                    None,
                    partial(
                        bot.V3LiquidityPool,
                        address=pool_address,
                        tokens=[token0_obj, token1_obj],
                        abi=bot.uniswap.v3.abi.UNISWAP_V3_POOL_ABI,
                        # populate_ticks=False,
                        lens=lens,
                        update_method="external",
                    ),
                )
            else:
                raise Exception("Could not identify pool type!")
        except Exception as e:
            print(e)
            print(type(e))
        else:
            if VERBOSE_PROCESSING:
                print(f"Created pool helper: {pool_helper}")
            # add the helper to the dictionary of LP objects, keyed by address
            degenbot_lp_helpers[pool_helper.address] = pool_helper

    print(
        f"Built {len(degenbot_lp_helpers)} liquidity pool helpers in {time.time() - start:.2f}s"
    )

    _weth_balance = weth.balanceOf(arb_contract.address)

    # build a dict of arb helpers, keyed by arb ID
    degenbot_cycle_arb_helpers = {
        arb_id: bot.arbitrage.UniswapLpCycle(
            input_token=degenbot_token_helpers.get(WETH_ADDRESS),
            swap_pools=swap_pools,
            max_input=_weth_balance,
            id=arb_id,
        )
        for arb in arb_paths
        # ignore arbs on the blacklist and arbs where pool helpers are not available for ALL hops in the path
        if (arb_id := arb.get("id")) not in BLACKLISTED_ARBS
        if len(
            swap_pools := [
                pool_obj
                for pool_address in arb.get("path")
                if (pool_obj := degenbot_lp_helpers.get(pool_address))
            ]
        )
        == len(arb.get("path"))
    }
    print(f"Built {len(degenbot_cycle_arb_helpers)} cycle arb helpers")

    arb_simulations = {
        id: {
            "simulations": 0,
            "failures": 0,
        }
        for id in degenbot_cycle_arb_helpers.keys()
    }


async def process_onchain_arbs(arbs: deque):

    arbs_submitted_this_block = []
    arbs_processed = 0

    while True:

        await asyncio.sleep(0)

        try:
            arb_helper = arbs.popleft()
        except IndexError:
            # queue is empty, break the loop
            break

        try:
            if arb_helper.auto_update(
                silent=True,
                block_number=newest_block
            ):
                arb_helper.calculate_arbitrage()
        except bot.exceptions.ArbitrageError as e:
            continue
        except Exception as e:
            print(f"process_onchain_arbs: {e}")
            print(type(e))
            continue
        else:
            arbs_processed += 1

    if VERBOSE_PROCESSING and arbs_processed:
        print(
            f"(process_onchain_arbs) processed {arbs_processed} updated arbs"
        )

    # generator to identify all profitable arbs (ignoring gas fees)
    profitable_arbs = (
        arb_helper
        for arb_helper in degenbot_cycle_arb_helpers.copy().values()
        if arb_helper.gas_estimate
        if (_profit := arb_helper.best.get("profit_amount"))
        if _profit > 0
    )

    best_arb_profit = 0
    best_arb = None

    while True:
        try:
            arb_helper = next(profitable_arbs)
        except StopIteration:
            break
        else:
            # ignore this arb if it comes up again
            if arb_helper in arbs_submitted_this_block:
                continue
            if (profit := arb_helper.best["profit_amount"]) > best_arb_profit:
                best_arb_profit = profit
                best_arb = arb_helper

    if best_arb:
        arbs_submitted_this_block.append(best_arb)
        await execute_arb_with_relay(
            arb_dict=best_arb.best,
            state_block=newest_block,
            target_block=newest_block + 1,
            arb_id=best_arb.id,
        )


def record_bundle(
    bundle_hash: str,
    blocks: List[int],
    tx: List[str],
    arb_id: str,
):

    SUBMITTED_BUNDLES[bundle_hash] = {
        "blocks": blocks,
        "transactions": tx,
        "arb_id": arb_id,
        "time": time.time(),
    }

    with open("submitted_bundles.json", "w") as file:
        json.dump(SUBMITTED_BUNDLES, file, indent=2)


async def refresh_pools():

    global status_pool_sync_in_progress

    while True:

        # run once per block
        await asyncio.sleep(AVERAGE_BLOCK_TIME)

        if first_new_block and first_event_block:
            this_block = newest_block
        else:
            continue

        # Generators for finding all pools with the most recent update marked before
        # the block where event-based updates began
        # e.g. a pool created at block 1 would be considered "stale" and refreshed
        # if the event updates started at block 3.

        # NOTE: this calls for manual updates to be performed on `this_block - 1`
        # to avoid a condition where this coroutine AND the event watcher are
        # attempting to update the same LP helper using the same block number

        # NOTE: these generators do not copy the helper dict since the loop is designed to run completely
        # through without stopping, does not modify the dict, and does not yield to the event loop
        outdated_v2_pools = (
            pool_obj
            for pool_obj in degenbot_lp_helpers.values()
            if pool_obj.uniswap_version == 2
            if pool_obj.update_block < first_event_block
        )

        outdated_v3_pools = (
            pool_obj
            for pool_obj in degenbot_lp_helpers.values()
            if pool_obj.uniswap_version == 3
            if pool_obj.update_block < first_event_block
        )

        for lp_helper in outdated_v2_pools:
            status_pool_sync_in_progress = True
            print(f"Refreshing outdated V2 pool: {lp_helper}")
            try:
                lp_helper.update_reserves(
                    override_update_method="polling",
                    update_block=this_block - 1,
                    silent=not VERBOSE_UPDATES,
                )
            except Exception as e:
                print(f"(refresh_pools)-V2: {e}")

        for lp_helper in outdated_v3_pools:
            status_pool_sync_in_progress = True
            print(f"Refreshing outdated V3 pool: {lp_helper}")
            try:
                lp_helper.auto_update(block_number=this_block - 1)
            except Exception as e:
                print(f"(refresh_pools)-V3: {e}")

        status_pool_sync_in_progress = False


async def remove_failed_arbs():
    """
    A long-running task that monitors the arb_simulations dictionary and
    compares the failure rate of arb helper simulations against a threshold.

    If an arb is found to exceed the failure threshold and the pool states are
    current, (auto_update returns False), the arb ID is added to a blacklist
    and the arb helper is removed.

    If an arb is discovered to be outdated, the statistics are reset.
    """

    global arb_simulations
    global degenbot_cycle_arb_helpers

    while True:

        await asyncio.sleep(AVERAGE_BLOCK_TIME)

        try:
            # iterate through a copy of the arbs, since this function will modify the original
            for arb_id in degenbot_cycle_arb_helpers.copy().keys():
                if (
                    arb_simulations[arb_id]["simulations"]
                    >= SIMULATION_CUTOFF_MIN_ATTEMPTS
                    and (
                        arb_simulations[arb_id]["failures"]
                        / arb_simulations[arb_id]["simulations"]
                    )
                    >= SIMULATION_CUTOFF_FAIL_THRESHOLD
                ):
                    old_state = degenbot_cycle_arb_helpers[
                        arb_id
                    ].pool_states.copy()
                    if degenbot_cycle_arb_helpers[arb_id].auto_update(
                        override_update_method="polling",
                        block_number=newest_block,
                    ):
                        new_state = degenbot_cycle_arb_helpers[
                            arb_id
                        ].pool_states.copy()
                        print()
                        print(
                            f"CANCELLED BLACKLIST, ARB {degenbot_cycle_arb_helpers.get(arb_id)} ({arb_id}) WAS OUTDATED"
                        )
                        print(f"old state: {old_state}")
                        print(f"new state: {new_state}")
                        print()
                        arb_simulations[arb_id]["simulations"] = 0
                        arb_simulations[arb_id]["failures"] = 0
                    else:
                        print(
                            f"BLACKLISTED ARB: {degenbot_cycle_arb_helpers.get(arb_id)}, ID: {arb_id}"
                        )
                        degenbot_cycle_arb_helpers.pop(arb_id)
                        arb_simulations.pop(arb_id)
                        BLACKLISTED_ARBS.append(arb_id)
                        with open(
                            "ethereum_blacklisted_arbs.json", "w"
                        ) as file:
                            json.dump(BLACKLISTED_ARBS, file, indent=2)
        except Exception as e:
            print(f"remove_failed_arbs: {e}")


async def status_watchdog():
    """
    Tasked with monitoring other coroutines, functions, objects, etc. and
    setting bot status variables like `status_paused`

    Other coroutines should monitor the state of `status_paused` and adjust their activity as needed
    """

    global status_paused

    print("Starting status watchdog")

    while True:

        await asyncio.sleep(0)

        # our node will always be slightly delayed compared to the timestamp of the block,
        # so compare that difference on each pass through the loop
        if (
            time.time() - newest_block_timestamp
            > AVERAGE_BLOCK_TIME + LATE_BLOCK_THRESHOLD
        ):
            # if the expected block is late, set the paused flag to True
            if not status_paused:
                status_paused = not status_paused
                if VERBOSE_WATCHDOG:
                    print("WATCHDOG: paused (block late)")
        elif status_pool_sync_in_progress:
            if not status_paused:
                status_paused = not status_paused
                if VERBOSE_WATCHDOG:
                    print("WATCHDOG: paused (pool sync in progress)")
        else:
            if status_paused:
                status_paused = not status_paused
                if VERBOSE_WATCHDOG:
                    print("WATCHDOG: unpaused")


def test_onchain_arb_gas(
    arb_id,
    block_number,
):
    """
    Calculates the gas use for the specified arb against a particular block
    """

    def test_gas(
        arb: bot.Arbitrage,
        payloads: list,
        tx_params: dict,
        block_number,
        arb_id=None,
    ) -> Tuple[bool, int]:

        if VERBOSE_TIMING:
            start = time.monotonic()
            print("starting test_gas")

        global arb_simulations

        try:
            arb_simulations[arb_id]["simulations"] += 1
            gas_estimate = (
                w3.eth.contract(
                    address=arb_contract.address,
                    abi=arb_contract.abi,
                )
                .functions.execute_payloads(payloads)
                .estimate_gas(
                    tx_params,
                    block_identifier=block_number,
                )
            )
        except web3.exceptions.ContractLogicError as e:
            arb_simulations[arb_id]["failures"] += 1
            # if VERBOSE_SIMULATION:
            #     print(f"test_gas simulation error: {e}")
            success = False
        except Exception as e:
            print(f"Error: {e}")
            print(f"Type: {type(e)}")
            success = False
        else:
            success = True
            arb.gas_estimate = gas_estimate

        if VERBOSE_TIMING:
            print(f"test_gas completed in {time.monotonic() - start:0.4f}s")

        return (
            success,
            arb.gas_estimate if success else 0,
        )

    # get a pointer to the arb helper
    if not (arb_helper := degenbot_cycle_arb_helpers.get(arb_id)):
        return

    if VERBOSE_TIMING:
        start = time.monotonic()
        print("starting test_onchain_arb")

    tx_params = {
        "from": bot_account.address,
        "chainId": brownie.chain.id,
        "nonce": bot_account.nonce,
    }

    arb_payloads = arb_helper.generate_payloads(
        from_address=arb_contract.address
    )

    success, gas_estimate = test_gas(
        arb_helper,
        arb_payloads,
        tx_params,
        arb_id=arb_helper.id,
        block_number=block_number,
    )

    if success and VERBOSE_ACTIVATION:
        print(f"Gas estimate for arb {arb_helper.id}: {gas_estimate}")

    if VERBOSE_TIMING:
        print(
            f"test_onchain_arb completed in {time.monotonic() - start:0.4f}s"
        )

    if not success:
        return
    else:
        arb_helper.gas_estimate = gas_estimate


async def track_balance():

    weth_balance = 0

    while True:

        await asyncio.sleep(AVERAGE_BLOCK_TIME)

        try:
            balance = weth.balanceOf(arb_contract.address)
        except Exception as e:
            print(f"(track_balance): {e}")
        else:
            if balance != weth_balance:
                print()
                print(f"Updated balance: {balance/(10**18):.3f} WETH")
                print()
                weth_balance = balance
                for arb in degenbot_cycle_arb_helpers.copy().values():
                    arb.max_input = weth_balance


async def watch_events():

    global status_events
    global first_event_block

    status_events = False

    arbs_to_check = deque()

    received_events = 0
    processed_mints = 0
    processed_swaps = 0
    processed_burns = 0
    processed_syncs = 0

    _TIMEOUT = 0.5  # how many seconds to wait before assuming the last event was received

    print("Starting event watcher loop")

    def process_sync_event(message: dict):

        event_address = w3.toChecksumAddress(
            message.get("params").get("result").get("address")
        )
        event_block = int(
            message.get("params").get("result").get("blockNumber"),
            16,
        )
        event_data = message.get("params").get("result").get("data")

        event_reserves = eth_abi.decode(
            ["uint112", "uint112"],
            bytes.fromhex(event_data[2:]),
        )

        try:
            v2_pool_helper = degenbot_lp_helpers[event_address]
        except KeyError:
            pass
        except Exception as e:
            print(e)
            print(type(e))
        else:
            reserves0, reserves1 = event_reserves
            v2_pool_helper.update_reserves(
                external_token0_reserves=reserves0,
                external_token1_reserves=reserves1,
                silent=not VERBOSE_UPDATES,
                print_ratios=False,
                print_reserves=False,
                update_block=event_block,
            )

            # find all arbs that care about this pool
            if arbs_affected := [
                arb
                for arb in degenbot_cycle_arb_helpers.values()
                for lp_obj in arb.swap_pools
                if v2_pool_helper is lp_obj
            ]:
                arbs_to_check.extend(arbs_affected)
        finally:
            nonlocal processed_syncs
            processed_syncs += 1
            if VERBOSE_EVENTS:
                print(f"[EVENT] Processed {processed_syncs} syncs")

    def process_mint_event(message: dict):

        event_address = w3.toChecksumAddress(
            message.get("params").get("result").get("address")
        )
        event_block = int(
            message.get("params").get("result").get("blockNumber"),
            16,
        )
        event_data = message.get("params").get("result").get("data")

        try:
            v3_pool_helper = degenbot_lp_helpers[event_address]
            event_tick_lower = eth_abi.decode(
                ["int24"],
                bytes.fromhex(
                    message.get("params").get("result").get("topics")[2][2:]
                ),
            )[0]

            event_tick_upper = eth_abi.decode(
                ["int24"],
                bytes.fromhex(
                    message.get("params").get("result").get("topics")[3][2:]
                ),
            )[0]

            _, event_liquidity, _, _ = eth_abi.decode(
                ["address", "uint128", "uint256", "uint256"],
                bytes.fromhex(event_data[2:]),
            )
        except KeyError:
            pass
        except Exception as e:
            print(e)
            print(type(e))
        else:
            if event_liquidity != 0:
                v3_pool_helper.external_update(
                    updates={
                        "liquidity_change": (
                            event_liquidity,
                            event_tick_lower,
                            event_tick_upper,
                        )
                    },
                    block_number=event_block,
                )
                # find all arbs that care about this pool
                arbs_affected = [
                    arb
                    for arb in degenbot_cycle_arb_helpers.values()
                    for pool_obj in arb.swap_pools
                    if v3_pool_helper is pool_obj
                ]
                arbs_to_check.extend(arbs_affected)
        finally:
            nonlocal processed_mints
            processed_mints += 1
            if VERBOSE_EVENTS:
                print(f"[EVENT] Processed {processed_mints} mints")

    def process_burn_event(message: dict):

        event_address = w3.toChecksumAddress(
            message.get("params").get("result").get("address")
        )
        event_block = int(
            message.get("params").get("result").get("blockNumber"),
            16,
        )
        event_data = message.get("params").get("result").get("data")

        # ignore events for pools we are not tracking
        if not (v3_pool_helper := degenbot_lp_helpers.get(event_address)):
            return

        try:
            event_tick_lower = eth_abi.decode(
                ["int24"],
                bytes.fromhex(
                    message.get("params").get("result").get("topics")[2][2:]
                ),
            )[0]

            event_tick_upper = eth_abi.decode(
                ["int24"],
                bytes.fromhex(
                    message.get("params").get("result").get("topics")[3][2:]
                ),
            )[0]

            event_liquidity, _, _ = eth_abi.decode(
                ["uint128", "uint256", "uint256"],
                bytes.fromhex(event_data[2:]),
            )
            event_liquidity *= -1
        except Exception as e:
            print(e)
        else:
            if event_liquidity != 0:
                v3_pool_helper.external_update(
                    updates={
                        "liquidity_change": (
                            event_liquidity,
                            event_tick_lower,
                            event_tick_upper,
                        )
                    },
                    block_number=event_block,
                )

                # find all arbs that care about this pool
                arbs_affected = [
                    arb
                    for arb in degenbot_cycle_arb_helpers.values()
                    for pool_obj in arb.swap_pools
                    if v3_pool_helper is pool_obj
                ]
                arbs_to_check.extend(arbs_affected)
        finally:
            nonlocal processed_burns
            processed_burns += 1
            if VERBOSE_EVENTS:
                print(f"[EVENT] Processed {processed_burns} burns")

    def process_swap_event(message: dict):

        event_address = w3.toChecksumAddress(
            message.get("params").get("result").get("address")
        )
        event_block = int(
            message.get("params").get("result").get("blockNumber"),
            16,
        )
        event_data = message.get("params").get("result").get("data")

        (
            _,
            _,
            event_sqrt_price_x96,
            event_liquidity,
            event_tick,
        ) = eth_abi.decode(
            [
                "int256",
                "int256",
                "uint160",
                "uint128",
                "int24",
            ],
            bytes.fromhex(event_data[2:]),
        )

        try:
            v3_pool_helper = degenbot_lp_helpers[event_address]
            v3_pool_helper.external_update(
                updates={
                    "tick": event_tick,
                    "liquidity": event_liquidity,
                    "sqrt_price_x96": event_sqrt_price_x96,
                },
                block_number=event_block,
            )
        except KeyError:
            pass
        except Exception as e:
            print(f"update_v3_pools: {e}")
            print(type(e))
        else:
            # find all arbs that care about this pool
            arbs_affected = [
                arb
                for arb in degenbot_cycle_arb_helpers.values()
                for pool_obj in arb.swap_pools
                if v3_pool_helper is pool_obj
            ]
            arbs_to_check.extend(arbs_affected)
        finally:
            nonlocal processed_swaps
            processed_swaps += 1
            if VERBOSE_EVENTS:
                print(f"[EVENT] Processed {processed_swaps} swaps")

    TOPICS = {
        w3.keccak(text="Sync(uint112,uint112)",).hex(): {
            "name": "Uniswap V2: SYNC",
            "process_func": process_sync_event,
        },
        w3.keccak(
            text="Mint(address,address,int24,int24,uint128,uint256,uint256)"
        ).hex(): {
            "name": "Uniswap V3: MINT",
            "process_func": process_mint_event,
        },
        w3.keccak(
            text="Burn(address,int24,int24,uint128,uint256,uint256)"
        ).hex(): {
            "name": "Uniswap V3: BURN",
            "process_func": process_burn_event,
        },
        w3.keccak(
            text="Swap(address,address,int256,int256,uint160,uint128,int24)"
        ).hex(): {
            "name": "Uniswap V3: SWAP",
            "process_func": process_swap_event,
        },
    }

    async for websocket in websockets.connect(
        uri=WEBSOCKET_URI,
        ping_timeout=None,
    ):

        # reset the status and first block every time we start a new websocket connection
        status_events = False
        first_event_block = 0

        try:
            await websocket.send(
                json.dumps(
                    {
                        "id": 1,
                        "method": "eth_subscribe",
                        "params": ["logs", {}],
                    }
                )
            )
            subscribe_result = json.loads(await websocket.recv())
            print(subscribe_result)

            status_events = True

            start = time.time()

            while True:

                # message = json.loads(await websocket.recv())

                try:
                    message = json.loads(
                        await asyncio.wait_for(
                            websocket.recv(),
                            timeout=_TIMEOUT,
                        )
                    )
                    # message = json.loads(await websocket.recv())
                # if no event has been received in _TIMEOUT seconds, assume all events have been received,
                # reduce the list of arbs to check with set(), repackage and send for processing,
                # then clear the working queue
                except asyncio.exceptions.TimeoutError as e:
                    end = time.time()
                    # print(f"actual time = {end - start:0.2f}s")
                    if arbs_to_check:
                        asyncio.create_task(
                            process_onchain_arbs(
                                deque(set(arbs_to_check)),
                            )
                        )
                        arbs_to_check.clear()
                    continue
                finally:
                    start = time.time()

                if not first_event_block:
                    first_event_block = int(
                        message.get("params").get("result").get("blockNumber"),
                        16,
                    )
                    print(f"First event block: {first_event_block}")

                received_events += 1
                if VERBOSE_EVENTS and received_events % 1000 == 0:
                    print(f"[EVENTS] Received {received_events} total events")

                try:
                    topic0 = (
                        message.get("params").get("result").get("topics")[0]
                    )
                except IndexError:
                    # ignore anonymous events
                    continue
                except Exception as e:
                    print(f"(event_watcher): {e}")
                    print(type(e))
                    continue

                # process the message for the associated event
                try:
                    TOPICS[topic0]["process_func"](message)
                # skip checking for the signature in TOPICS and simply continue on untracked events
                except KeyError:
                    continue

        except Exception as e:
            print("event_watcher reconnecting...")
            print(e)


async def watch_new_blocks():
    """
    Watches the websocket for new blocks, updates the base fee for the last block, scans
    transactions and removes them from the pending tx queue, and prints various messages
    """

    print("Starting block watcher loop")

    global first_new_block
    global newest_block
    global newest_block_timestamp
    global last_base_fee
    global next_base_fee
    global status_new_blocks

    async for websocket in websockets.connect(
        uri=WEBSOCKET_URI,
        ping_timeout=None,
    ):

        # reset the first block and status every time we connect or reconnect
        status_new_blocks = False
        first_new_block = 0

        try:
            await websocket.send(
                json.dumps(
                    {
                        "id": 1,
                        "method": "eth_subscribe",
                        "params": ["newHeads"],
                    }
                )
            )

            subscribe_result = json.loads(await websocket.recv())
            print(subscribe_result)
            status_new_blocks = True

            while True:

                message = json.loads(await websocket.recv())

                if VERBOSE_TIMING:
                    print("starting watch_new_blocks")
                    start = time.monotonic()

                newest_block = int(
                    message.get("params").get("result").get("number"),
                    16,
                )
                newest_block_timestamp = int(
                    message.get("params").get("result").get("timestamp"),
                    16,
                )

                if not first_new_block:
                    first_new_block = newest_block
                    print(f"First full block: {first_new_block}")

                last_base_fee, next_base_fee = w3.eth.fee_history(
                    1, newest_block
                ).get("baseFeePerGas")

                # remove all confirmed transactions from the all_pending_tx dict
                for hash in w3.eth.get_block(newest_block).get("transactions"):
                    all_pending_tx.pop(hash.hex(), None)

                if VERBOSE_BLOCKS:
                    print(
                        f"[{newest_block}] "
                        + f"base fee: {last_base_fee/(10**9):.1f} (this) / {next_base_fee/(10**9):.1f} (next) - "
                        f"(+{time.time() - newest_block_timestamp:.2f}s)"
                    )

                if VERBOSE_TIMING:
                    print(
                        f"watch_new_blocks completed in {time.monotonic() - start:0.4f}s"
                    )

        except Exception as e:
            print("watch_new_blocks reconnecting...")
            print(e)


if not DRY_RUN:
    print(
        "\n"
        "\n***************************************"
        "\n*** DRY RUN DISABLED - BOT IS LIVE! ***"
        "\n***************************************"
        "\n"
    )
    time.sleep(10)

# Create a reusable web3 object to communicate with the node
# (no arguments to provider will default to localhost on the default port)
w3 = web3.Web3(web3.WebsocketProvider())

os.environ["ETHERSCAN_TOKEN"] = ETHERSCAN_API_KEY

try:
    brownie.network.connect(BROWNIE_NETWORK)
except:
    sys.exit(
        "Could not connect! Verify your Brownie network settings using 'brownie networks list'"
    )

try:
    bot_account = brownie.accounts.load(
        BROWNIE_ACCOUNT
    )
    flashbots_id_account = brownie.accounts.load(
        FLASHBOTS_IDENTITY_ACCOUNT
    )
except:
    sys.exit(
        "Could not load account! Verify your Brownie account settings using 'brownie accounts list'"
    )

# inject the flashbots middleware into the w3 object
flashbots.flashbot(
    w3,
    eth_account.Account.from_key(flashbots_id_account.private_key),
    FLASHBOTS_RELAY_URL,
)

arb_contract = brownie.Contract.from_abi(
    name="",
    address=ARB_CONTRACT_ADDRESS,
    abi=json.loads(
        """
        [{"stateMutability": "payable", "type": "constructor", "inputs": [], "outputs": []}, {"stateMutability": "payable", "type": "function", "name": "execute_payloads", "inputs": [{"name": "payloads", "type": "tuple[]", "components": [{"name": "target", "type": "address"}, {"name": "calldata", "type": "bytes"}, {"name": "value", "type": "uint256"}]}], "outputs": []}, {"stateMutability": "payable", "type": "function", "name": "uniswapV3SwapCallback", "inputs": [{"name": "amount0", "type": "int256"}, {"name": "amount1", "type": "int256"}, {"name": "data", "type": "bytes"}], "outputs": []}, {"stateMutability": "payable", "type": "fallback"}]
        """
    ),
)

try:
    weth = brownie.Contract(WETH_ADDRESS)
except Exception as e:
    print(e)
    try:
        weth = brownie.Contract.from_explorer(WETH_ADDRESS)
    except Exception as e:
        print(e)

# load historical submitted bundles
SUBMITTED_BUNDLES = {}
try:
    with open("submitted_bundles.json") as file:
        SUBMITTED_BUNDLES = json.load(file)
# if the file doesn't exist, create it
except FileNotFoundError:
    with open("submitted_bundles.json", "w") as file:
        json.dump(SUBMITTED_BUNDLES, file, indent=2)


# load the blacklists
BLACKLISTED_TOKENS = []
for filename in ["ethereum_blacklisted_tokens.json"]:
    try:
        with open(filename) as file:
            BLACKLISTED_TOKENS.extend(json.load(file))
    except FileNotFoundError:
        with open(filename, "w") as file:
            json.dump(BLACKLISTED_TOKENS, file, indent=2)
print(f"Found {len(BLACKLISTED_TOKENS)} blacklisted tokens")

BLACKLISTED_ARBS = []
for filename in ["ethereum_blacklisted_arbs.json"]:
    try:
        with open(filename) as file:
            BLACKLISTED_ARBS.extend(json.load(file))
    except FileNotFoundError:
        with open(filename, "w") as file:
            json.dump(BLACKLISTED_ARBS, file, indent=2)
print(f"Found {len(BLACKLISTED_ARBS)} blacklisted arbs")


last_base_fee = 100 * 10**9  # overridden on first received block
next_base_fee = 100 * 10**9  # overridden on first received block
newest_block = 0  # overridden on first received block
newest_block_timestamp = int(time.time())  # overridden on first received block
status_events = False
status_new_blocks = False
status_paused = True
status_pool_sync_in_progress = False
first_new_block = None
first_event_block = 0
all_pending_tx = {}
degenbot_lp_helpers = {}
degenbot_cycle_arb_helpers = {}
arb_simulations = {}


if __name__ == "__main__":
    asyncio.run(_main_async())

