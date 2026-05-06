import PyPDF2
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTFigure
import pdfplumber
from PIL import Image
from pdf2image import convert_from_path
import pytesseract
import os
from langchain.docstore.document import Document
from langchain_community.vectorstores import Qdrant
from langchain_community.embeddings import OCIGenAIEmbeddings
import oci
from langchain_community.vectorstores.oraclevs import OracleVS
from langchain_community.vectorstores.utils import DistanceStrategy
import oracledb
import config 
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
import io
from flask import Flask, request, jsonify
from langchain.text_splitter import RecursiveCharacterTextSplitter
from datetime import datetime

## -- log -------------------------------------------------------------------
def log(s):
   dt = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
   print( "["+dt+"] "+ str(s), flush=True)

## -- Main ------------------------------------------------------------------

oci_signer = InstancePrincipalsSecurityTokenSigner()

app = Flask(__name__)
pool=None
# Database connection setup
if config.DB_TYPE == "oracle":
    try:
        oracledb.init_oracle_client()
        pool = oracledb.SessionPool(user=config.ORACLE_USERNAME, password=config.ORACLE_PASSWORD, dsn=config.ORACLE_TNS, min=2, max=5, increment=1, encoding="UTF-8")
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
pool.release(connection)
log(f"generateModel={generateModel}")

endpoint= config.get_endpoint()
log(f"endpoint={endpoint}")

objectStorageLink = config.OBJECT_STORAGE_LINK  # Put your own object storage link
directory = config.DIRECTORY  # directory to your documents
prompt_context = config.PROMPT_CONTEXT
embeddingModel = config.EMBEDDING_MODEL
getdataFromDB = config.ORACLE_DIRECTORY_TABLE

def load_docs_from_oracle(connection, table_name, file_name):
    documents = []
    cursor = connection.cursor()
    # Select only the specific file based on the provided filename
    cursor.execute(f"SELECT id, file_name, data FROM {table_name} WHERE file_name = :file_name", [file_name])
    rows = cursor.fetchall()
    for row in rows:
        doc_id, file_name, data_blob = row
        pdf_content = data_blob.read()
        pdf_file = io.BytesIO(pdf_content)
        docs = process_pdf_from_bytesio(pdf_file, file_name)
        documents.extend(docs)
    
    cursor.close()
    return documents

def is_bold(font_name):
    bold_indicators = ['bold', 'Black', 'Heavy']
    return any(indicator.lower() in font_name.lower() for indicator in bold_indicators if isinstance(font_name, str))

def extract_bold_sentences(page_text, line_formats):
    bold_sentences = []
    for line, formats in zip(page_text, line_formats):
        if any(is_bold(font) for font in formats):
            bold_sentences.append(line.strip())
    return ', '.join(bold_sentences)

def text_extraction(element):
    line_text = element.get_text()
    line_formats = []
    for text_line in element:
        if isinstance(text_line, LTTextContainer):
            for character in text_line:
                if isinstance(character, LTChar):
                    line_formats.append(character.fontname)
    format_per_line = list(set(line_formats))
    return (line_text, format_per_line)

def extract_table(pdf_path, page_num, table_num):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num]
        table = page.extract_tables()[table_num]
    return table

def fill_missing_values(table):
    filled_table = []
    prev_row = None
    
    for row in table:
        filled_row = []
        for idx, cell in enumerate(row):
            if cell is None or cell.strip() == '':
                if prev_row and len(prev_row) > idx:
                    filled_row.append(prev_row[idx])
                else:
                    filled_row.append('None')
            else:
                filled_row.append(cell)
        filled_table.append(filled_row)
        prev_row = filled_row
    
    return filled_table

def table_converter(table):
    table = fill_missing_values(table)
    table_string = ''
    for row in table:
        cleaned_row = [item.replace('\n', ' ') if item is not None else 'None' for item in row]
        table_string += ('|' + '|'.join(cleaned_row) + '|\n')
    return table_string.strip()

def is_element_inside_any_table(element, page, tables):
    x0, y0up, x1, y1up = element.bbox
    y0 = page.bbox[3] - y1up
    y1 = page.bbox[3] - y0up
    for table in tables:
        tx0, ty0, tx1, ty1 = table.bbox
        if tx0 <= x0 <= x1 and ty0 <= y0 <= y1:
            return True
    return False

def find_table_for_element(element, page, tables):
    x0, y0up, x1, y1up = element.bbox
    y0 = page.bbox[3] - y1up
    y1 = page.bbox[3] - y0up
    for i, table in enumerate(tables):
        tx0, ty0, tx1, ty1 = table.bbox
        if tx0 <= x0 <= x1 and ty0 <= y0 <= y1:
            return i
    return None

def crop_image(element, pageObj):
    [image_left, image_top, image_right, image_bottom] = [element.x0, element.y0, element.x1, element.y1]
    pageObj.mediabox.lower_left = (image_left, image_bottom)
    pageObj.mediabox.upper_right = (image_right, image_top)
    cropped_pdf_writer = PyPDF2.PdfWriter()
    cropped_pdf_writer.add_page(pageObj)
    with open('cropped_image.pdf', 'wb') as cropped_pdf_file:
        cropped_pdf_writer.write(cropped_pdf_file)

def convert_to_images(input_file):
    images = convert_from_path(input_file)
    image = images[0]
    output_file = 'PDF_image.png'
    image.save(output_file, 'PNG')

def image_to_text(image_path):
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text

# Process PDF from BytesIO object and return documents
def process_pdf_from_bytesio(pdf_file, file_name):
    pdfReader = PyPDF2.PdfReader(pdf_file)
    text_per_page = {}
    image_flag = False

    for pagenum, page in enumerate(extract_pages(pdf_file)):
        pageObj = pdfReader.pages[pagenum]
        page_text = []
        line_format = []
        text_from_images = []
        text_from_tables = []
        page_content = []
        table_in_page = -1
        pdf = pdfplumber.open(pdf_file)
        page_tables = pdf.pages[pagenum]
        tables = page_tables.find_tables()
        if tables:
            table_in_page = 0

        for table_num in range(len(tables)):
            table = extract_table(pdf_file, pagenum, table_num)
            table_string = table_converter(table)
            text_from_tables.append(table_string)

        page_elements = [(element.y1, element) for element in page._objs]
        page_elements.sort(key=lambda a: a[0], reverse=True)

        for component in page_elements:
            element = component[1]

            if table_in_page != -1 and is_element_inside_any_table(element, page, tables):
                table_found = find_table_for_element(element, page, tables)
                if table_found == table_in_page and table_found is not None:
                    page_content.append(text_from_tables[table_in_page])
                    page_text.append('table')
                    line_format.append('table')
                    table_in_page += 1
                continue

            if isinstance(element, LTTextContainer):
                (line_text, format_per_line) = text_extraction(element)
                page_text.append(line_text)
                line_format.append(format_per_line)
                page_content.append(line_text)

        dctkey = 'Page_' + str(pagenum)
        text_per_page[dctkey] = [page_text, line_format, text_from_tables, page_content]

    docs = []
    for page_key, page_data in text_per_page.items():
        page_text = page_data[0]
        line_formats = page_data[1]
        page_content = page_data[3]
        page_content_string = ''.join(page_content).strip()  # Remove leading/trailing spaces
        if not page_content_string:  # Skip if the content is empty
            print(f"Skipping empty page content in {file_name}, {page_key}")
            continue
        
        topics = extract_bold_sentences(page_text, line_formats).strip()
        if not topics:  # Skip if the topics are empty
            print(f"Skipping empty topics in {file_name}, {page_key}")
            continue

        # Create the document if content and topics are valid
        doc = Document(
            page_content=page_content_string,
            metadata={"source": file_name, "page": page_key[5:], "topics": topics}
        )
        docs.append(doc)

    return docs

# Function to split documents into chunks based on character size
def split_documents(documents, chunk_size=1500, chunk_overlap=150):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    split_docs = text_splitter.split_documents(documents)
    return split_docs

@app.route('/create_embeddings', methods=['POST'])
def create_embeddings():
    log("<create_embeddings>")
    connection = pool.acquire()
    file_name = request.json.get('file_name')
    if not file_name:
        return jsonify({"error": "file_name parameter is required"}), 400
    
    if connection is None:
        return jsonify({"error": "No valid database connection"}), 500

    documents = load_docs_from_oracle(connection, getdataFromDB, file_name)

    # Filter out any documents with empty content
    valid_documents = [doc for doc in documents if doc.page_content.strip()]
    
    if not valid_documents:
        return jsonify({"error": "No valid content to embed"}), 404
    
    # Split documents into smaller chunks of maximum 1000 characters with 150 characters overlap
    split_docs = split_documents(valid_documents, chunk_size=1500, chunk_overlap=150)

    embeddings = OCIGenAIEmbeddings(
        model_id=config.EMBEDDING_MODEL,
        service_endpoint=endpoint,
        compartment_id=os.getenv("TF_VAR_compartment_ocid"),
        auth_type="INSTANCE_PRINCIPAL",
    )
    
    if config.DB_TYPE == "oracle":
        v_store = OracleVS(
                client=connection,
                table_name=config.ORACLE_TABLE_NAME,
                embedding_function=embeddings,
            )
        db = v_store.add_documents(split_docs)
    else:
        db = Qdrant.from_documents(
            split_docs,
            embeddings,
            location=config.QDRANT_LOCATION,
            collection_name=config.QDRANT_COLLECTION_NAME,
            distance_func=config.QDRANT_DISTANCE_FUNC
        )
    pool.release(connection)
    log("</create_embeddings>")
    
    return jsonify({"message": "Embeddings created successfully!"})

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=3001)
