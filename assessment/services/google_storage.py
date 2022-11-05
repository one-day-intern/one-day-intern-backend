from google.cloud import storage
import os


def setup_google_storage_credentials():
    google_application_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIAL_VALUES')
    google_application_credentials = google_application_credentials.replace('\\\\', '\\')
    with open('storage-credentials.json', mode='w') as google_storage_credential_file:
        google_storage_credential_file.write(google_application_credentials)

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'storage-credentials.json'


def upload_file_to_google_bucket(destination_file_name, bucket_name, file):
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(destination_file_name)
    blob.upload_from_file(file_obj=file, rewind=True)
