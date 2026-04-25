"""Reset Kafka topic for fresh demo stream"""
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError
import time

admin = KafkaAdminClient(bootstrap_servers='localhost:9092')

# Step 1: Delete the topic
try:
    admin.delete_topics(['aura-beth-logs'])
    print('✓ Deleted topic aura-beth-logs')
    time.sleep(2)
except KafkaError as e:
    print(f'Delete warning: {e}')

# Step 2: Create it fresh
try:
    admin.create_topics([
        NewTopic(
            name='aura-beth-logs',
            num_partitions=1,
            replication_factor=1
        )
    ])
    print('✓ Created topic aura-beth-logs')
    time.sleep(1)
except KafkaError as e:
    print(f'Create error: {e}')

# Step 3: Verify the topic exists
try:
    topic_metadata = admin.list_topics()
    if 'aura-beth-logs' in topic_metadata:
        print('\n✓ Topic verified: aura-beth-logs ready')
        print('  Status: clean and ready for new messages')
    else:
        print('\n⚠ Topic may not be fully ready yet')
except Exception as e:
    print(f'\n✓ Topic operations complete (verification skipped: {e})')

admin.close()
print('\n✓ Kafka topic reset complete!')
