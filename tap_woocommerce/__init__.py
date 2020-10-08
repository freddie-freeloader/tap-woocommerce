#!/usr/bin/env python3
import itertools
import os
import sys
import time
import re
import json
import attr
import singer
import singer.metrics as metrics
from singer import utils
import datetime
from datetime import datetime
import dateutil
from dateutil import parser
from woocommerce import API


REQUIRED_CONFIG_KEYS = ["url", "consumer_key", "consumer_secret", "start_date"]
LOGGER = singer.get_logger()

CONFIG = {
    "url": None,
    "consumer_key": None,
    "consumer_secret": None,
    "start_date":None
}

def get_start(STATE, tap_stream_id, bookmark_key):
    current_bookmark = singer.get_bookmark(STATE, tap_stream_id, bookmark_key)
    if current_bookmark is None:
        start_date = CONFIG["start_date"]
    else:
        start_date = current_bookmark
    return datetime.strptime(start_date, '%Y-%m-%d').isoformat()

def load_schema(entity):
    '''Returns the schema for the specified source'''
    schema = utils.load_json(get_abs_path("schemas/{}.json".format(entity)))

    return schema

def filter_items(item):
    filtered = {
        "id":int(item["id"]),
        "name":str(item["name"]),
        "product_id":int(item["product_id"]),
        "variation_id":int(item["variation_id"]),
        "quantity":int(item["quantity"]),
        "subtotal":float(item["subtotal"]),
        "subtotal_tax":float(item["subtotal_tax"]),
        "total":float(item["total"]),
        "sku":str(item["sku"]),
        "price":float(item["price"])
    }
    return filtered

def filter_coupons(coupon):
    filtered = {
        "id":int(coupon["id"]),
        "code":str(coupon["code"]),
        "discount":float(coupon["discount"])
    }
    return filtered

def filter_shipping(ship):
    filtered = {
        "id":int(ship["id"]),
        "method_title":str(ship["method_title"]),
        "method_id":str(ship["method_id"]),
        "total":float(ship["total"])
    }
    return filtered

def filter_order(order):
    tzinfo = parser.parse(CONFIG["start_date"]).tzinfo
    if "line_items" in order and len(order["line_items"])>0:
        line_items = [filter_items(item) for item in order["line_items"]]
    else:
        line_items = None
    if "coupon_lines" in order and len(order["coupon_lines"])>0:
        coupon_lines = [filter_coupons(coupon) for coupon in order["coupon_lines"]]
    else:
        coupon_lines = None
    if "shippng_lines" in order and len(order["shipping_lines"])>0:
        shipping_lines = [filter_shipping(ship) for ship in order["shipping_lines"]]
    else:
        shipping_lines = None

    filtered = {
        "order_id":int(order["id"]),
        "order_key":str(order["order_key"]),
        "status":str(order["status"]),
        "date_created":parser.parse(order["date_created"]).replace(tzinfo=tzinfo).isoformat(),
        "date_modified":parser.parse(order["date_modified"]).replace(tzinfo=tzinfo).isoformat(),
        "discount_total":float(order["discount_total"]),
        "shipping_total":float(order["shipping_total"]),
        "total":float(order["total"]),
        "line_items":line_items
    }
    return filtered

def sync_orders(STATE, catalog):

    woocommerce_api = API(
        url="https://salufast.com",
        consumer_key=CONFIG["consumer_key"],
        consumer_secret=CONFIG["consumer_secret"],
        version="wc/v3",
        timeout=60,
        query_string_auth=True
    )

    def get_orders_by_page(start_date, page_number):
        response = woocommerce_api.get("orders",
                                   params={"per_page": 100,
                                           "page": page_number,
                                           "orderby": "date",
                                           "order": "asc",
                                           "after": start_date})
        if response.status_code is not 200:
            LOGGER.critical("Got non 200 status code")
            try:
                LOGGER.critical(response.json())
            except:
                pass
            response.raise_for_status()
        LOGGER.info("Successful fetch")
        return response.json()

    schema = load_schema("orders")
    singer.write_schema("orders", schema, ["order_id"])

    start_date = get_start(STATE, "orders", "last_update")

    LOGGER.info("Only syncing orders updated since " + start_date)
    last_update = start_date
    page_number = 1
    with metrics.record_counter("orders") as counter:
        while True:
            orders = get_orders_by_page(start_date, page_number)
            for order in orders:
                counter.increment()
                order = filter_order(order)
                if("date_created" in order) and (parser.parse(order["date_created"]) > parser.parse(last_update)):
                    last_update = order["date_created"]
                singer.write_record("orders", order)
            if len(orders) < 100:
                break
            else:
                page_number +=1
    STATE = singer.write_bookmark(STATE, 'orders', 'last_update', last_update) 
    singer.write_state(STATE)
    LOGGER.info("Completed Orders Sync")
    return STATE

@attr.s
class Stream(object):
    tap_stream_id = attr.ib()
    sync = attr.ib()

STREAMS = [
    Stream("orders", sync_orders)
]

def get_streams_to_sync(streams, state):
    '''Get the streams to sync'''
    current_stream = singer.get_currently_syncing(state)
    result = streams
    if current_stream:
        result = list(itertools.dropwhile(
            lambda x: x.tap_stream_id != current_stream, streams))
    if not result:
        raise Exception("Unknown stream {} in state".format(current_stream))
    return result


def get_selected_streams(remaining_streams, annotated_schema):
    selected_streams = []

    for stream in remaining_streams:
        tap_stream_id = stream.tap_stream_id
        for stream_idx, annotated_stream in enumerate(annotated_schema.streams):
            if tap_stream_id == annotated_stream.tap_stream_id:
                schema = annotated_stream.schema
                if (hasattr(schema, "selected")) and (schema.selected is True):
                    selected_streams.append(stream)

    return selected_streams

def do_sync(STATE, catalogs):
    '''Sync the streams that were selected'''
    remaining_streams = get_streams_to_sync(STREAMS, STATE)
    selected_streams = get_selected_streams(remaining_streams, catalogs)
    if len(selected_streams) < 1:
        LOGGER.info("No Streams selected, please check that you have a schema selected in your catalog")
        return

    LOGGER.info("Starting sync. Will sync these streams: %s", [stream.tap_stream_id for stream in selected_streams])

    for stream in selected_streams:
        LOGGER.info("Syncing %s", stream.tap_stream_id)
        singer.set_currently_syncing(STATE, stream.tap_stream_id)
        singer.write_state(STATE)

        try:
            catalog = [cat for cat in catalogs.streams if cat.stream == stream.tap_stream_id][0]
            STATE = stream.sync(STATE, catalog)
        except Exception as e:
            LOGGER.critical(e)
            raise e

def get_abs_path(path):
    '''Returns the absolute path'''
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)

def load_discovered_schema(stream):
    '''Attach inclusion automatic to each schema'''
    schema = load_schema(stream.tap_stream_id)
    for k in schema['properties']:
        schema['properties'][k]['inclusion'] = 'automatic'
    return schema

def discover_schemas():
    '''Iterate through streams, push to an array and return'''
    result = {'streams': []}
    for stream in STREAMS:
        LOGGER.info('Loading schema for %s', stream.tap_stream_id)
        result['streams'].append({'stream': stream.tap_stream_id,
                                  'tap_stream_id': stream.tap_stream_id,
                                  'schema': load_discovered_schema(stream)})
    return result

def do_discover():
    '''JSON dump the schemas to stdout'''
    LOGGER.info("Loading Schemas")
    json.dump(discover_schemas(), sys.stdout, indent=4)

@utils.handle_top_exception(LOGGER)
def main():
    '''Entry point'''
    args = utils.parse_args(REQUIRED_CONFIG_KEYS)

    CONFIG.update(args.config)
    STATE = {}

    if args.state:
        STATE.update(args.state)
    if args.discover:
        do_discover()
    elif args.catalog:
        do_sync(STATE, args.catalog)
    else:
        LOGGER.info("No Streams were selected")

if __name__ == "__main__":
    main()
