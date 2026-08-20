terraform {
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
        }
    }
}

provider "aws" {
    region = "us-east-2"
}

resource "aws_s3_bucket" "tfstate" {
    bucket = "pulsedesk-eks-worker-tfstate-123456789012"
}

resource "aws_s3_bucket_versioning" "tfstate" {
    bucket = aws_s3_bucket.tfstate.id

    versioning_configuration {
        status = "Enabled"
    }
}

resource "aws_dynamodb_table" "tf_lock" {
    name = "pulsedesk-eks-worker-tf-lock"
    billing_mode = "PAY_PER_REQUEST"
    hash_key = "LockID"

    attribute {
        name = "LockID"
        type = "S" 
    }
}