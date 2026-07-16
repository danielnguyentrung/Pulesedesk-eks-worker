import json
import boto3
import os
import time
import re
import textwrap
import random 

AWS_REGION = os.environ["AWS_REGION"]

sqs = boto3.client("sqs", region_name =AWS_REGION)
QUEUE_URL = os.environ["QUEUE_URL"]

dynamodb = boto3.resource("dynamodb", region_name =AWS_REGION)
table_name = os.environ["USERS_TABLE"]
table = dynamodb.Table(table_name)
ses = boto3.client('ses', region_name =AWS_REGION)
sender_email = os.environ["SENDER_EMAIL"]
bedrock = boto3.client("bedrock-runtime", region_name =AWS_REGION)

keyword_weight = {
    # High Severity
    "data loss": 100,
    "system down": 100,
    "server down": 100,
    "fatal": 100,
    "virus": 100,
    "outage": 100,
    "failure": 100,
    "system error": 60,
    
    # Medium-High Severity
    "clients affected": 50,
    "critical": 50,
    "urgent": 50,
    
    # Medium Severity
    "offline": 20,
    "effective immediately": 20,
    "spam": 20,
    "some users": 15, 
    "end of day": 15,
    "lock out": 15,
    "lockout": 15,
    "password": 15,
    "vpn": 15,
    "locked out": 15,
    "phishing": 15,
    
    # Low-Medium Severity
    "not working": 10,
    "terminate": 10,
    "disable": 10,
    "error": 10,
    "minor bug": 10,
    "bug": 10,
    "update": 10,
    "login": 10,
    
    # Low Severity
    "question": 5,
    "reset": 5,
    "slow": 5,
    "not opening": 5,
    "new hire": 5,
    "hire": 5,
    "onboarding": 5,
    "set-up": 5,
    "set up": 5,
    "print": 5,
    "printing": 5,
    "printer": 5,
    "email": 5,
    "new": 5,
    "install": 5,
    "how do i": 5,
    "request": 5,
    "order": 5
}

ticket_category = sorted([
    "account",
    "hardware",
    "software",
    "network/connectivity",
    "security",
    "mobile",
    "bug",
    "other"
])

def email_check(body):
    email = body.get('email')
    first_name = body.get('first_name')
    last_name = body.get('last_name')

    if not email:
        raise ValueError("Missing email")

    response = table.get_item(
        Key={'email': email})

    if "Item" not in response:
        table.put_item(
            Item={
                'email': email, 
                'first_name': first_name,
                'last_name': last_name,
                'ticket_ids': []
            }
        )
    else:
        print(f"Email: {email} is already registered to an account.")

def add_original_ticket(body):
    ticket_id = body.get('ticket_id')
    created_at = body.get('created_at', int(time.time()))
    email = body.get('email')
    ticket_title = body.get('ticket_title')
    problem_type = body.get('problem_type')
    ticket_description = body.get('ticket_description')


    if not email or not ticket_id:
        raise ValueError("Missing email or Ticket_id")

    ticket_data = {
        "ticket_id": ticket_id,
        "ticket_title": ticket_title,
        "ticket_description": ticket_description,
        "problem_type": problem_type,
        "status": "OPEN",
        "created_at": created_at
    }
    
    response = table.get_item(Key={'email': email})
    user_tickets = response.get('Item', {}).get('ticket_ids', [])

    if any(ticket['ticket_id'] == ticket_id for ticket in user_tickets):
        print(f"Ticket {ticket_id} already exists for email {email}.")
        return 
    
    user_tickets.append(ticket_data)

    table.update_item(
        Key={'email': email},
        UpdateExpression="SET ticket_ids = :tickets",
        ExpressionAttributeValues={':tickets': user_tickets}
    )

    print(f"Ticket {ticket_id} has been added for email {email}.")

def bedrock_validation(body, keyword_weight, ticket_category):
    ticket_title = body.get('ticket_title')
    problem_type = body.get('problem_type')
    ticket_description = body.get('ticket_description')

    keyword_words = list(keyword_weight.keys())

    prompt = f"""
    You are an IT Specialist assisting with ticket and text normalization. 
    You will be given: 
    - A ticket title
    - A ticket description
    - A ticket category selected by the user from the options provided in the ticket_category list 

    Your task is to: 
    1. Correct grammar, spelling, and punctuation in the ticket title and description.
    2. Complete incomplete sentences or remove vagueness where possible. 
    3. Preserve the original meaning and intent of the ticket as much as possible.
    4. Validate that the correct category was selected based on the content of the ticket title and description. If the category is incorrect, change it to the correct category based on the contents. The category selected for the problem type of the ticket MUST be from the ticket category list provided.  
    5. Do NOT add new technical issues, assumptions, or urgency indicators.
    6. Do NOT remove any information provided by the user.

    Keyword handling rules: 
    - A keyword list is provided.
    - If a keyword from the list appears more than once replace all repeated occurrences with a synonym of the same meaning in IT ticket context except the first occurrence. 
    - If a keyword appears only once DO NOT MODIFY IT. 
    - Do NOT introduce new keywords from the list.
    - Do NOT change the overall severity implied by the text. 
    
    Output requirements:
    - Return only valid JSON
    - DO NOT include any explanations, comments, or analysis in your response. 
    - Use the following exact structure: 

    {"revised_ticket_title": "<revised_ticket_title>",
     "revised_ticket_description": "<revised_ticket_description>",
     "revised_problem_type": "<validated category from the allowed list>"}

    Here is the information to process from the user: 

    The ticket title submitted by the user is: {ticket_title}
    The ticket description submitted by the user is: {ticket_description}
    The problem type selected by the user is: {problem_type}
    The keyword list is: {keyword_words}
    The problem type options: {ticket_category}

    The revised ticket title, ticket description, and validated category will be used by an automated AWS lambda function to determine the ticket urgency. 
"""
    
    response = bedrock.invoke_model(
        modelId=os.environ["BEDROCK_MODEL_ID"],
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 400,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }).encode("utf-8")
    )

    raw = response["body"].read()
    model_response = json.loads(raw)

    if "content" not in model_response:
        raise ValueError(f"Unexpected Bedrock response: {model_response}")
    
    output_text = model_response["content"][0]["text"]

    #Extract text output(Bedrock Format)
    output_text = output_text.replace("```json", "").replace("```", "").strip()

    #Parse AI-generated JSON
    try:
        validated_ticket = json.loads(output_text)
    except json.JSONDecodeError: 
        raise ValueError("Bedrock returned invalid JSON")
    
    required_keys = {"revised_ticket_title", "revised_ticket_description", "revised_problem_type"}
    if not required_keys.issubset(validated_ticket.keys()):
        raise ValueError("Bedrock response missing required fields")
    if validated_ticket["revised_problem_type"] not in ticket_category:
        raise ValueError("Invalid problem type assigned by Bedrock")

    return validated_ticket

def add_bedrock_data_to_db(validated_ticket, body):
    email = body.get('email')
    ticket_id = body.get('ticket_id')

    if not email or not ticket_id:
        raise ValueError("Missing Email or Ticketid")
    
    revised_ticket_title = validated_ticket["revised_ticket_title"]
    revised_ticket_description = validated_ticket["revised_ticket_description"]
    revised_problem_type = validated_ticket["revised_problem_type"]
    
    response = table.get_item(Key={'email': email})
    user_tickets = response.get('Item', {}).get('ticket_ids', [])

    for ticket in user_tickets:
        if ticket['ticket_id'] == ticket_id:
            ticket["revised_ticket_title"] = revised_ticket_title
            ticket["revised_ticket_description"] = revised_ticket_description
            ticket["revised_problem_type"] = revised_problem_type
            print("Ticket_ID was found")
            break 
    else: 
        raise ValueError("Ticket ID not found for the user in the database.")
    
    table.update_item(
        Key={'email': email},
        UpdateExpression="SET ticket_ids = :tickets",
        ExpressionAttributeValues={
        ':tickets': user_tickets
        }
    )

    print(f"Bedrock outputs for Ticket Title, Problem Type, and Ticket Description have been updated under ticket{ticket_id} under email{email}")

def ticket_urgency(validated_ticket):
    title = validated_ticket.get('revised_ticket_title','')
    ticket_description = validated_ticket.get('revised_ticket_description', '')
    if not ticket_description or not title:
        return{"urgency": 1}

    title_lower = title.lower()
    ticket_description_lower = ticket_description.lower() 

    matched_title_keywords = set()
    matched_description_keywords = set()
    
    for keyword, score in keyword_weight.items():
        pattern = rf'\b{re.escape(keyword)}\b'
 
        if re.search(pattern, title_lower): 
            matched_title_keywords.add(keyword)
        
        if re.search(pattern, ticket_description_lower):
            matched_description_keywords.add(keyword)

    title_score = sum(keyword_weight[value] for value in matched_title_keywords)
    description_score = sum(keyword_weight[value] for value in matched_description_keywords)
        
    combined_score = title_score + (description_score / 2)
        
    if combined_score >= 100:
        urgency = 5
    elif combined_score >= 80:
        urgency = 4
    elif combined_score >= 60:
        urgency = 3
    elif combined_score >= 40:
        urgency = 2
    else: 
        urgency = 1
    
    return {"urgency": urgency}

tier_1 = ["Bob", "Jessica"]
tier_2 = ["Mary", "Ross"]
tier_3 = ["Mike", "Tony"]

def ticket_assignment(urgency):
    
    if urgency == 5:
        member_selection = random.choice(tier_3)
    elif urgency < 5 and urgency > 2: 
        member_selection = random.choice(tier_2)
    else:
        member_selection = random.choice(tier_1)

    return member_selection 

def send_ses_email(email, subject, body):
    try:
        response = ses.send_email(
            Source=sender_email,
            Destination={
                "ToAddresses": [email]
            },
            Message={
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8"
                },
                "Body": {
                    "Text": {
                        "Data": body,
                        "Charset": "UTF-8"
                    }
                }
            }
        )
        print("SES email sent:", response["MessageId"])
        return True
    except Exception as e:
        print("SES email failed:", e)
        return False
    
def process_message(body):
        email_check(body)
        add_original_ticket(body)
        validated_ticket = bedrock_validation(body, keyword_weight, ticket_category)
        add_bedrock_data_to_db(validated_ticket, body)
        urgency = ticket_urgency(validated_ticket)
        selected_team_member = ticket_assignment(urgency['urgency'])


        validated_ticket_title = validated_ticket["revised_ticket_title"]
        validated_ticket_description = validated_ticket["revised_ticket_description"]
        validated_problem_type = validated_ticket["revised_problem_type"]

        it_message = textwrap.dedent(f"""
        Hi Team, 

        Please review the IT Ticket. 
                                     
        AI Validated Ticket Summary:
        Name: {body.get('first_name')} {body.get('last_name')}
        Email: {body.get('email')}
        Ticket ID: {body.get('ticket_id')}
        Title: {validated_ticket_title}
        Ticket Description: {validated_ticket_description}
        Problem Type: {validated_problem_type}
        Urgency: {urgency['urgency']}

        Ticket has been assigned to: {selected_team_member}                         

        Original Ticket Submission: 
        Title: {body.get('ticket_title')}
        Problem Type: {body.get('problem_type')}
        Ticket Description: {body.get('ticket_description')}

        Thank you,
        Daniel 
        """).strip()

        client_message = textwrap.dedent(f"""
        Hi {body.get('first_name')}, 

        Your IT ticket has been submitted successfully. 

        Ticket Summary:
        Ticket ID: {body.get('ticket_id')}
        Assigned Team Member: {selected_team_member}
        Title: {body.get('ticket_title')}
        Ticket Description: {body.get('ticket_description')}
        Urgency: {urgency['urgency']}
    
        Please allow for 24 hours for our team to review the ticket. We will notify you once it has been resolved. 

        Thank you,
        Daniel's IT Support Team 
        """).strip()

        send_ses_email(body.get('email'), subject="Your IT Ticket has been submitted", body=client_message)
        send_ses_email(sender_email, subject=validated_ticket_title, body=it_message)

def main(): 
    while True: 
        response = sqs.receive_message(
            QueueUrl = QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20
        )

        messages = response.get("Messages", [])

        for message in messages: 
            try:
                body = json.loads(message["Body"])
                process_message(body)

                sqs.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=message["ReceiptHandle"]
                )
            except Exception as e:
                print("Failed to process message:", e)
        
if __name__ == "__main__":
    main()