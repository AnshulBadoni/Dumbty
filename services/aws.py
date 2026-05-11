import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class AWSService:
    def __init__(self):
        self.access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.bucket_name = os.getenv("AWS_S3_BUCKET")
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region
            )
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None

    def upload_file(self, local_path, s3_key):
        """Upload a file to S3 and return the public URL"""
        if not self.s3_client:
            return None
        
        try:
            # Upload the file with public-read ACL
            self.s3_client.upload_file(
                local_path, 
                self.bucket_name, 
                s3_key,
                ExtraArgs={'ACL': 'public-read'}
            )
            
            # Generate the regional URL
            # Note: Using the s3-{region} format as suggested by AWS error messages
            url = f"https://{self.bucket_name}.s3-{self.region}.amazonaws.com/{s3_key}"
            return url
        except ClientError as e:
            logger.error(f"S3 Upload Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected S3 Error: {e}")
            return None

    def delete_file(self, s3_key):
        """Delete a file from S3"""
        if not self.s3_client:
            return False
            
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            logger.error(f"S3 Deletion Error: {e}")
            return False

    def generate_presigned_url(self, s3_key, expiration=3600):
        """Generate a presigned URL to share an S3 object"""
        if not self.s3_client:
            return None
            
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Presigned URL Error: {e}")
            return None

aws_service = AWSService()
