resource "aws_ecr_repository" "pulsedesk-worker" {
    name = "pulsedesk-worker"
    force_delete = true 
}