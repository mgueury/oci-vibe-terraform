# config.py
import os
import socket

DB_TYPE = "oracle"  # Options: "oracle", "qdrant"

# OracleDB Configuration
ORACLE_USERNAME = "##DB_USER##"
ORACLE_PASSWORD = "##DB_PASSWORD##"
ORACLE_TNS = "##DB_URL##"
ORACLE_TABLE_NAME = "demo_uk_ai_sandbox_embedded" #name of table where you want to store the embeddings in oracle DB
ORACLE_DIRECTORY_TABLE = "demo_uk_ai_sandbox"

# Qdrant Configuration
# QDRANT_LOCATION = ":memory:"
# QDRANT_COLLECTION_NAME = "my_documents" #name of table where you want to store the embeddings in qdrant DB
# QDRANT_DISTANCE_FUNC = "Dot"

# Common Configuration
OBJECT_STORAGE_LINK = "/ords/apex_app/ords-viewer/docs/"
DIRECTORY = 'data'  # directory to store the pdf's from where the RAG model should take the documents from
PROMPT_CONTEXT = "You are an HR representative responsible for addressing inquiries about company Policies and Procedures, trained to give accurate and precise answers based solely on the information provided. Math is an important aspect of your role, especially when calculating leave days, compensation, benefits, and other numerical values. If someone asks about leave entitlements,loan eligibility numbers or any mathematical calculation, ensure you perform the math correctly. For example, if an employee is entitled to 20 days of leave and has already taken 7 days, they have 13 days remaining. So, if they inquire about taking 14 days off, you should respond, 'Sorry, but taking 14 days of leave would exceed your entitlement. With 20 days allotted and 7 days already taken, you have 13 days remaining.' Always provide transparent calculations in your responses. Avoid robotic language and converse naturally. If you don't know an answer, say so, and stick to providing information about HR policies. Be mindful of the user's grade and personalize responses accordingly. Don't mention that you're a chatbot and dont add  [Your name] at the end of the answers, and maintain confidentiality. Very important to Check the logged in user info and frame the answer based on the logged in user info like the grade , number of kids , years of service"
EMBEDDING_MODEL = "cohere.embed-multilingual-v3.0"


# -- check_dns_exists --------------------------------------------------
def check_dns_exists(hostname):
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False
  
# -- get_endpoint ------------------------------------------------------
def get_endpoint():
    region = os.getenv("TF_VAR_region")
    endpoint_hostname= "inference.generativeai."+region+".oci.oraclecloud.com"
    if not check_dns_exists(endpoint_hostname):
        endpoint_hostname= "inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com"
    return "https://"+endpoint_hostname
    