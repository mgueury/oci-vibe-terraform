# OciTest.py
# Author: Ansh
from langchain.docstore.document import Document
from langchain_community.vectorstores import Qdrant
import oci
import flask
import os
from datetime import datetime
from flask import Flask, request
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OCIGenAIEmbeddings
from langchain_community.vectorstores.oraclevs import OracleVS
from langchain_community.vectorstores import oraclevs
from langchain_community.vectorstores.utils import DistanceStrategy
import oracledb
import config  # Import the configuration
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
from PyPDF2 import PdfReader
import io
from oci.generative_ai_inference import GenerativeAiInferenceClient
from oci.generative_ai_inference.models import CohereChatRequest
from oci.generative_ai_inference.models import ChatDetails, OnDemandServingMode
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
from oci.retry import NoneRetryStrategy
import uuid
from langchain.docstore.document import Document
from PyPDF2 import PdfReader

## -- check_table_embed_empty -----------------------------------------------

def check_table_embed_empty(connection):
    # At restart, skip the initialisation if the table is already populated. 
    cursor = connection.cursor()
    cursor.execute(f"SELECT count(id) FROM {config.ORACLE_TABLE_NAME}")
    row_count, = cursor.fetchone()  
    cursor.close()
    if row_count > 0:
        return False
    else:
        return True
    
## -- load_docs_from_oracle -------------------------------------------------

def load_docs_from_oracle(connection, table_name):
    documents = []
    cursor = connection.cursor()
    cursor.execute(f"SELECT id, file_name, data FROM {table_name}")
    rows = cursor.fetchall()
    for row in rows:
        doc_id, file_name, data_blob = row
        # Reading the BLOB data
        pdf_content = data_blob.read()
        # Convert the BLOB data to a PDF file in memory
        pdf_file = io.BytesIO(pdf_content)
        # Extract text from the PDF
        reader = PdfReader(pdf_file)
        full_text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                doc = Document(
                    page_content=page_text,
                    metadata={"source": file_name, "page": i}
                )
                documents.append(doc)
    cursor.close()
    return documents

## -- split_docs ------------------------------------------------------------

def split_docs(documents, chunk_size=1500, chunk_overlap=100):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    docs = text_splitter.split_documents(documents)
    return docs

## -- log -------------------------------------------------------------------
def log(s):
   dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
   print( "["+dt+"] "+ str(s), flush=True)

## -- Main ------------------------------------------------------------------

pool=None
# Initialize connection based on DB_TYPE
if config.DB_TYPE == "oracle":
    try:
        # oracledb.init_oracle_client()
        pool = oracledb.SessionPool(user=config.ORACLE_USERNAME, password=config.ORACLE_PASSWORD, dsn=config.ORACLE_TNS, min=2, max=100, increment=1, encoding="UTF-8")
        log("Connection to OracleDB successful!")
    except Exception as e:
        log("Connection to OracleDB failed! " + str(e) )
else:
    connection = None

# Get Cohere Model Name from database config table
connection = pool.acquire()
cursor = connection.cursor()
cursor.execute(f"SELECT value FROM DEMO_UK_AI_SANDBOX_SETTINGS where setting='LLM Model'")
generateModel = cursor.fetchone()[0]
cursor.close()
log(f"generateModel={generateModel}")

endpoint= config.get_endpoint()
log(f"endpoint={endpoint}")

compartment_id = os.getenv("TF_VAR_compartment_ocid")
objectStorageLink = config.OBJECT_STORAGE_LINK  # Put your own object storage link
directory = config.DIRECTORY  # directory to your documents
prompt_context = config.PROMPT_CONTEXT
embeddingModel = config.EMBEDDING_MODEL
getdataFromDB = config.ORACLE_DIRECTORY_TABLE

oci_signer = InstancePrincipalsSecurityTokenSigner()

embeddings = OCIGenAIEmbeddings(
    model_id=embeddingModel,
    service_endpoint=endpoint,
    compartment_id=compartment_id,
    auth_type="INSTANCE_PRINCIPAL",
)

# On first start, load the documents from the BLOB table
if check_table_embed_empty(connection):
    log("Indexing Files") 
    # Load documents from the Oracle table
    documents = load_docs_from_oracle(connection, getdataFromDB)
    docs = split_docs(documents)
    if config.DB_TYPE == "oracle":
        db = OracleVS.from_documents(
            docs,
            embeddings,
            client=connection,
            table_name=config.ORACLE_TABLE_NAME,
            distance_strategy=DistanceStrategy.DOT_PRODUCT,
        )
        pool.release(connection)
    else:
        db = Qdrant.from_documents(
            docs,
            embeddings,
            location=config.QDRANT_LOCATION,
            collection_name=config.QDRANT_COLLECTION_NAME,
            distance_func=config.QDRANT_DISTANCE_FUNC
        )
else:
    log("SKIP: Indexing Files") 

flask_app = Flask(__name__)

@flask_app.route('/cohere/generate', methods=['POST'])
def generate_text():
    try:    
        # print( "<data>-----------------" )
        # print( request.get_data() )
        # print( "</data>----------------" )
        request_data = request.get_json()
        text = request_data.get('text')
        previous_chat_message = request_data.get('previous_chat_message', "Hi")
        previous_chat_reply = request_data.get('previous_chat_reply', "Hello")
        userDetails = request_data.get('userDetails', "")
        max_tokens = request_data.get('max_tokens', 200)
        temperature = request_data.get('temperature', 0)
        prompt = request_data.get('prompt', prompt_context)        
        frequency_penalty = request_data.get('frequency_penalty', 1.0)
        top_p = request_data.get('top_p', 0.7)
        top_k = request_data.get('top_k', 1.0)
        model_id = request_data.get('model_id', generateModel)
    except Exception as e:
        print("Exception " + str(e) )        

    try:    
        if config.DB_TYPE == "oracle":
            connection = pool.acquire()
            db = OracleVS(
                    client=connection,
                    table_name=config.ORACLE_TABLE_NAME,
                    embedding_function=embeddings,
                    )   
        similar_docs = db.similarity_search(text, k=3)
        # similar_docs = db.similarity_search_with_score(text, k=3)

        if config.DB_TYPE == "oracle":
            pool.release(connection)
    except Exception as e:
        print("Exception" + str(e) )        
              
    print("************************context *******************")
    print(similar_docs)
    concatenated_content = ""
    sourceLinks = ""
    sourcePageNumber = ""
    unique_source_links = set()
    for document in similar_docs:
        concatenated_content += document.page_content
        source_link = document.metadata["source"]
        sourcePageNumber = int(document.metadata["page"])
        sourcePageNumber = sourcePageNumber + 1
        if source_link not in unique_source_links:
            unique_source_links.add(source_link)
            sourceLinks += "<a href='" + objectStorageLink + source_link + "#page=" + str(sourcePageNumber) + "' target='_blank'>" + source_link[source_link.rfind("/") + 1:] + " (page " + str(sourcePageNumber) + ")</a>\n"

    print("************************question *******************")
    print(text)
   
    userInfo = ""
    if userDetails!="":
      userInfo = "Logged in user info: "+userDetails
    documents = [
        {
            "title": "Oracle",
            "snippet": concatenated_content+"\n"+userInfo,
            "website": "https://www.oracle.com/database"
        }
    ]
    previous_chat_message = oci.generative_ai_inference.models.CohereUserMessage(message=previous_chat_message)
    previous_chat_reply = oci.generative_ai_inference.models.CohereChatBotMessage(message=previous_chat_reply)
    chat_history = [previous_chat_message, previous_chat_reply]
    
    # Create the Generative AI Inference client
    generative_ai_inference_client = GenerativeAiInferenceClient(config={}, signer=oci_signer, service_endpoint=endpoint, retry_strategy=NoneRetryStrategy(), timeout=(10, 240))

    # Create the chat request
    chat_request = CohereChatRequest(
        message=text,
        max_tokens=max_tokens,
        is_stream=False,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        documents = documents,
        frequency_penalty=frequency_penalty,
        chat_history = chat_history,
        preamble_override = prompt
    )

    # Create the chat details
    chat_detail = ChatDetails(
        serving_mode=OnDemandServingMode(model_id=model_id),
        compartment_id=compartment_id,
        chat_request=chat_request
    )
    print("The chat request is ---->")
    print(chat_request)
    chat_response = generative_ai_inference_client.chat(chat_detail)

    # Print result
    print("**************************Chat Result**************************")
    chat_response_text = chat_response.data.chat_response.text
    print("Extracted text:", chat_response_text)
    return oci.util.to_dict(chat_response_text + ' For more info check the below links: \n' + sourceLinks)

if __name__ == '__main__':
    from waitress import serve    
    log("Starting Flask.") 
    serve(flask_app, host="0.0.0.0", port=3000)    
