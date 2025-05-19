# Run this script in gcp cloud shell to push messages into the topic

from google.cloud import pubsub_v1
from google.cloud import storage
import time
from dotenv import load_dotenv
import os

load_dotenv()  # loads from .env

project_id = os.environ.GET("GCP_PROJECT_ID")
topic_name = os.environ.GET("PUBSUB_TOPIC_NAME")

#Create a publisher client
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_name)

topic = publisher.get_topic(request={"topic": topic_path})
#Check if the topic exists
if topic is None:
    print('Topic does not exist:', topic_path)
    exit()

#Create a storage client
storage_client = storage.Client()
bucket_name = os.environ.get("BUCKET_NAME")
file_name = 'conversations.json'

#Get the bucket and blob
bucket = storage_client.bucket(bucket_name)
blob = bucket.blob(file_name)

#Read the file line by line
with blob.open("r") as f_in:
    for line in f_in:
        #Data must be a bytestring
        data = line.encode('utf-8')
        #Publish the data to the topic
        future = publisher.publish(topic=topic.name, data=data)
        print(future.result())
        time.sleep(1)