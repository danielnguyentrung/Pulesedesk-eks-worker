resource "aws_eks_cluster" "pulsedesk_eks" {
    name = "pulsedesk-eks"
    role_arn = aws_iam_role.eks_iam_role.arn

    vpc_config {
        subnet_ids = concat(module.vpc.private_subnets, module.vpc.public_subnets)
    }
    depends_on = [aws_iam_role_policy_attachment.eks_policy]
}

resource "aws_eks_node_group" "pulsedesk_node_group" {
    cluster_name = aws_eks_cluster.pulsedesk_eks.name
    node_role_arn = aws_iam_role.worker_node_iam_role.arn
    subnet_ids = module.vpc.private_subnets 
    instance_types = ["t3.micro"]

    scaling_config {
        desired_size = 1
        max_size = 2
        min_size = 1
    }
    
    depends_on = [
    aws_iam_role_policy_attachment.worker_node_policy, 
    aws_iam_role_policy_attachment.worker_node_cni_policy, 
    aws_iam_role_policy_attachment.worker_node_container_policy
    ]
}

