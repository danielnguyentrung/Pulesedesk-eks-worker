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
}


provider "aws" {
    region = "us-east-1"
}

data "tls_certificate" "eks" {
    url = aws_eks_cluster.pulsedesk_eks.identity[0].oidc[0].issuer 
}