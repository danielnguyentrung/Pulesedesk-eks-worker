resource "aws_iam_role" "keda_operator_irsa_role"  {
    name = "keda-operator-irsa-role"

    assume_role_policy = jsonencode({
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
                        "${replace(aws_iam_openid_connect_provider.pulsedesk_connect_provider.url, "https://", "")}:sub" = "system:serviceaccount:keda:keda-operator"
                        "${replace(aws_iam_openid_connect_provider.pulsedesk_connect_provider.url, "https://", "")}:aud" = "sts.amazonaws.com"
                    }
                }
            }
        ]
    })
}

resource "aws_iam_policy" "keda_operator_policy" {
    name = "keda-operator-policy"
    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
            {
                Effect = "Allow"
                Action = ["sqs:GetQueueAttributes"]
                Resource = "*"
            }
        ]
    })
}

resource "aws_iam_role_policy_attachment" "keda_irsa_role_attachment" {
    role = aws_iam_role.keda_operator_irsa_role.name
    policy_arn = aws_iam_policy.keda_operator_policy.arn
}