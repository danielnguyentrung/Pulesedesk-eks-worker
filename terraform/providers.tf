terraform {
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 5.0"
        }

        tls = {
            source = "hashicorp/tls" 
        }
    }

    backend "s3" {
        bucket = "pulsedesk-eks-worker-tfstate-123456789012"
        key = "pulsedesk-eks-worker/terraform.tfstate"
        region = "us-east-2"
        dynamodb_table = "pulsedesk-eks-worker-tf-lock"
        encrypt = true 
    }
}

provider "aws" {
    region = "us-east-2"
}

data "tls_certificate" "eks" {
    url = aws_eks_cluster.pulsedesk_eks.identity[0].oidc[0].issuer 
}