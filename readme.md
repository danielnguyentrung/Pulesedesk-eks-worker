# PulseDesk EKS Worker 

A containerized version of PulseDesk's core ticket-processing Lambda, rebuilt on Amazon EKS with Docker and Kubernetes using SQS, DynamoDB, Bedrock, and SES.


## Tech Stack 

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-%235835CC.svg?style=for-the-badge&logo=terraform&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-%23326CE5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%232496ED.svg?style=for-the-badge&logo=docker&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-%230F1689.svg?style=for-the-badge&logo=helm&logoColor=white)
![Python](https://img.shields.io/badge/Python-%233776AB.svg?style=for-the-badge&logo=python&logoColor=white)

**AWS services used:** EKS · IAM (IRSA) · VPC · SQS · DynamoDB · Bedrock · SES · ECR · S3 (remote Terraform state) · DynamoDB (state locking)

## Objective 

PulseDesk was originally built as a fully serverless application, with a Lambda function handling ticket validation and processing. I extracted that core logic and rebuilt it as a containerized worker running on EKS; partly to gain the scalability, cost efficiency, and availability that come with autoscaling on Kubernetes, and partly as a deliberate way to learn how to run and operate Kubernetes in a real production-shaped environment.

## Solution Overview 

For this revision of PulseDesk, I introduced a few changes to the core function:

#### IRSA for AWS access
 
- Pods authenticate via short-lived, per-workload IAM roles, zero static credentials 

#### KEDA-driven autoscaling 

- Workers scale from 0 to 2 based on the SQS queue depth, not a fixed replica count. I had deliberately allowed for the maximum pod scaling to be 2. 

#### Remote Terraform state (S3 + DynamoDB)

- Shared, locked state instead of a local file, to safely work from multiple machines

#### Least-privilege IAM scoped per component 

- The worker's role and KEDA's role are deliberately separate and narrow.

#### Cost-conscious node sizing 

- I deliberately stayed on the free-tier-eligible t3.micro, sizing node count against real pod-capacity math rather than guessing 

### Workflow 

1. KEDA polls the ticket queue every 30 seconds, authorized via IRSA to check SQS's queue attributes. 
2. If tickets are waiting, KEDA scales the worker up to 1 or 2 pods depending on how many are in the queue. 
3. The ticket title, description, and problem type are sent to Bedrock, using Claude Sonnet 4.6, for data cleansing. 
4. The AI-organized ticket details are returned to the worker pod, which classifies urgency using a keyword list, assigns the ticket to a team member via the random module to promote fairness, and emails the IT team both the AI-generated details and the original submission, in case the AI made a mistake. The client receives a separate email confirming their ticket receipt and who it's assigned to. 
5. KEDA checks the SQS queue depth again. Once no tickets remain, it scales the worker pods back down to 0. 


## Lessons Learned

- Hands-on experience with creating YAML files, VPC, EKS, IRSA, KEDA, Helm, and Docker. 
- Troubleshooting a stuck deployment. During my first deployment, the pods stayed in a Pending state. I found that the node group's instance type had never been explicitly set, so AWS defaulted to `t3.medium`, which wasn't eligible on my free-tier account. I fixed that by specifying `t3.micro` in my Terraform code, but the pods still stayed in a Pending state afterward. Running `kubectl describe pod` showed a FailedScheduling error: the node was already out of room. I learned that a node's pod capacity isn't limited by CPU or memory, but by the number of available IP addresses per node (`t3.micro` caps at 4, tied to the VPC CNI's ENI limits), and required system pods like `kube-proxy`, `aws-node`, and CoreDNS (2 replicas by default) were already using that capacity before my own pod could schedule. I fixed it by scaling the CoreDNS deployment down to 1 replica, freeing exactly enough room. Two lessons from this: always explicitly set instance type instead of relying on AWS's default, and node capacity in EKS is a networking constraint, not a compute one. 
- While working on this project, I kept running into the problem of two different Terraform state files existing between my laptop and my desktop. I figured this could be optimized, and realized the solution was moving the state file to a shared S3 bucket, so running `terraform init` on either machine connects to the same backend and reads the current state from there instead of a stale local file. Thinking further about how organizations manage this at scale, I added a DynamoDB table as a lock, so two people can't run `terraform apply` at the same time and corrupt the state. Now, switching devices is seamless. I just run `terraform init` to pick up the latest state, from wherever it was last updated. 
- After completing this project, I'll now be able to consciously choose between Lambda and Kubernetes for future work, instead of defaulting to serverless out of habit. It taught me a lot about autoscaling, setting up pods and nodes, writing Terraform/YAML, and building Docker images, along with the real value each of those brings. I'll definitely use an S3 bucket and DynamoDB for remote state on future projects, for a much easier time managing Terraform state files. 