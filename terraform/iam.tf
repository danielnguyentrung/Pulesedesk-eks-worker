resource "aws_iam_role" "eks_iam_role" {
    name = "eks-iam-role"

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Action = "sts:AssumeRole"
                Principal = {
                    Service = "eks.amazonaws.com"
                }
            }
        ]
    })
}

resource "aws_iam_role_policy_attachment" "eks_policy" {
    role = aws_iam_role.eks_iam_role.name
    policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "worker_node_iam_role" {
    name = "worker-node-iam-role"

    assume_role_policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow" 
                Action = "sts:AssumeRole" 
                Principal = {
                    Service = "ec2.amazonaws.com"
                }
            }
        ]
    })
}

resource "aws_iam_role_policy_attachment" "worker_node_policy" {
    role = aws_iam_role.worker_node_iam_role.name 
    policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "worker_node_cni_policy" {
    role = aws_iam_role.worker_node_iam_role.name 
    policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "worker_node_container_policy"{
    role = aws_iam_role.worker_node_iam_role.name 
    policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_openid_connect_provider" "pulsedesk_connect_provider" {
    url = aws_eks_cluster.pulsedesk_eks.identity[0].oidc[0].issuer
    client_id_list = ["sts.amazonaws.com"]
    thumbprint_list = [data.tls_certificate.eks.certificates[0].sha1_fingerprint]
}

resource "aws_iam_role" "irsa_role" {
    name = "pulsedesk-worker-irsa-role"

    assume_role_policy = jsonencode ({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Action = "sts:AssumeRoleWithWebIdentity"
                Principal = {
                    Federated = aws_iam_openid_connect_provider.pulsedesk_connect_provider.arn 
                }
                Condition = {
                    StringEquals = {
                        "${replace(aws_iam_openid_connect_provider.pulsedesk_connect_provider.url, "https://", "")}:sub" = "system:serviceaccount:default:pulsedesk-worker"
                        "${replace(aws_iam_openid_connect_provider.pulsedesk_connect_provider.url, "https://", "")}:aud" = "sts.amazonaws.com"
                    }
                }
            }
        ]
    })
}
