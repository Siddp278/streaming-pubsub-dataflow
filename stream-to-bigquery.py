#run with python streaming-beam-dataflow.py 

import apache_beam as beam
from apache_beam.io.gcp.pubsub import ReadFromPubSub
from apache_beam.io.gcp.bigquery import WriteToBigQuery
import json
from apache_beam.options.pipeline_options import PipelineOptions
from dotenv import load_dotenv
import os

load_dotenv()  # loads from .env

project_id = os.environ.GET("GCP_PROJECT_ID")
topic_name = os.environ.GET("PUBSUB_TOPIC_NAME")
dataset_id = os.environ.get("DATASET_ID")

#Define your Dataflow pipeline options
options = PipelineOptions(
    runner='DataflowRunner',   #for Dataflow job change to runner='DataflowRunner'
    project=project_id,
    region='us-central1',   
    temp_location=os.environ.get("TEMP_LOCATION"),
    staging_location=os.environ.egt("STAGING_LOCATION"),
    streaming=True,
    # Dataflow parameters that are optional
    job_name='run-streaming-conversations', 
    num_workers=3,  #Specify the number of workers
    max_num_workers=10,  #Specify the maximum number of workers
    disk_size_gb=25,  #Specify the disk size in GB per worker
    autoscaling_algorithm='THROUGHPUT_BASED',  #Specify the autoscaling algorithm
    machine_type='n1-standard-4',  #Specify the machine type for the workers
    service_account_email=os.environ.get("SERVICE_ACCOUNT")  
    #Specify the service account email, add these roles: BigQuery Admin, Dataflow Worker, Pub/Sub Admin, Storage Object Viewer 
)

#Define your Beam pipeline
with beam.Pipeline(options=options) as pipeline:
    #Read the input data from Pub/Sub
    messages = pipeline | ReadFromPubSub(subscription=os.environ.get("SUBSCRIPTIONS"))

    #Parse the JSON messages
    parsed_messages = messages | beam.Map(lambda msg: json.loads(msg))

    #Extract the desired fields for 'conversations' table
    conversations_data = parsed_messages | beam.Map(lambda data: {
        'senderAppType': data.get('senderAppType', 'N/A'),
        'courierId': data.get('courierId', None),
        'fromId': data.get('fromId', None),
        'toId': data.get('toId', None),
        'chatStartedByMessage': data.get('chatStartedByMessage', False),
        'orderId': data.get('orderId', None),
        'orderStage': data.get('orderStage', 'N/A'),
        'customerId': data.get('customerId', None),
        'messageSentTime': data.get('messageSentTime', None),
        #only elements with both fields present are processed further in the pipeline
    }) | beam.Filter(lambda data: data['orderId'] is not None and data['customerId'] is not None)

    #Extract the desired fields for 'orders' table
    orders_data = parsed_messages | beam.Map(lambda data: {
        'cityCode': data.get('cityCode', 'N/A'),
        'orderId': data.get('orderId', None),
        #only elements that satisfy both conditions (non-None 'orderId' and 'cityCode' not equal to 'N/A') will pass through the filter and continue to the subsequent steps in the pipeline
    }) | beam.Filter(lambda data: data['orderId'] is not None and data['cityCode'] != 'N/A')

    #Define the schema for the 'conversations' table
    conversations_schema = {
        'fields': [
            {'name': 'senderAppType', 'type': 'STRING'},
            {'name': 'courierId', 'type': 'INTEGER'},
            {'name': 'fromId', 'type': 'INTEGER'},
            {'name': 'toId', 'type': 'INTEGER'},
            {'name': 'chatStartedByMessage', 'type': 'BOOLEAN'},
            {'name': 'orderId', 'type': 'INTEGER'},
            {'name': 'orderStage', 'type': 'STRING'},
            {'name': 'customerId', 'type': 'INTEGER'},
            {'name': 'messageSentTime', 'type': 'TIMESTAMP'}
        ]
    }

    #Define the schema for the 'orders' table
    orders_schema = {
        'fields': [
            {'name': 'cityCode', 'type': 'STRING'},
            {'name': 'orderId', 'type': 'INTEGER'}
        ]
    }

    #Write the conversations data to the 'conversations' table in BigQuery
    conversations_data | 'Write conversations to BigQuery' >> WriteToBigQuery(
        table=f'{project_id}:{dataset_id}.conversations',
        schema=conversations_schema,
        create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
        write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND
    )

    #Write the orders data to the 'orders' table in BigQuery
    orders_data | 'Write orders to BigQuery' >> WriteToBigQuery(
        table=f'{project_id}:{dataset_id}.orders',
        schema=orders_schema,
        create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
        write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND
    )