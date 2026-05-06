#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

# APEX Forward
sudo dnf module reset nginx -y
sudo dnf module enable nginx:1.22 -y
# sudo yum remove nginx-mod*
# sudo yum install nginx-mod-*

# ORACLE Instant Client 
if [[ "$JDBC_URL" == *"jdbc:oracle"* ]]; then
    if [[ `arch` == "aarch64" ]]; then
        sudo dnf install -y oracle-release-el8
        sudo dnf install -y oracle-instantclient19.19-basic oracle-instantclient19.19-devel
    else
        export INSTANT_VERSION=23.9.0.25.07-1
        wget -nv https://download.oracle.com/otn_software/linux/instantclient/2390000/oracle-instantclient-basic-${INSTANT_VERSION}.el8.x86_64.rpm
        wget -nv https://download.oracle.com/otn_software/linux/instantclient/2390000/oracle-instantclient-sqlplus-${INSTANT_VERSION}.el8.x86_64.rpm
        sudo dnf install -y oracle-instantclient-basic-${INSTANT_VERSION}.el8.x86_64.rpm oracle-instantclient-sqlplus-${INSTANT_VERSION}.el8.x86_64.rpm
        mv *.rpm /tmp
    fi
fi

# Python Server
sudo dnf -y install git gcc-c++
sudo dnf install -y python3.11 python3.11-pip python3-devel
sudo pip3.11 install pip --upgrade

# Install virtual env python_env
python3.11 -m venv myenv
source myenv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Get env parameters
. ./env.sh

# Get COMPARTMENT_OCID
curl -s -H "Authorization: Bearer Oracle" -L http://169.254.169.254/opc/v2/instance/ > /tmp/instance.json
export TF_VAR_compartment_ocid=`cat /tmp/instance.json | jq -r .compartmentId`
export TF_VAR_region=`cat /tmp/instance.json | jq -r .canonicalRegionName`

# XXX
# Use /usr/lib/oracle/23/client64/lib/network/admin/tnsnames.ora ?

# TNS_NAMES.ORA
cat > tnsnames.ora <<EOT
DB  = $DB_URL
EOT

# Change the env.sh
CONFIG_FILE=config.py
sed -i "s/##DB_USER##/apex_app/" $CONFIG_FILE
sed -i "s/##DB_PASSWORD##/$DB_PASSWORD/" $CONFIG_FILE
sed -i "s/##DB_URL##/DB/" $CONFIG_FILE
sed -i "s/##NAMESPACE##/$TF_VAR_namespace/" $CONFIG_FILE
sed -i "s/##PREFIX##/$TF_VAR_prefix/" $CONFIG_FILE
sed -i "s/##REGION##/$TF_VAR_region/" $CONFIG_FILE

sudo firewall-cmd --zone=public --add-port=3000/tcp --permanent
sudo firewall-cmd --zone=public --add-port=3001/tcp --permanent
sudo firewall-cmd --reload

# Upload test files from docs in DB. 
export TNS_ADMIN=.
python3 <<EOF
import oracledb
import config  
import os

def insert_blob( a_filename ):
  with open('docs/'+a_filename, 'rb') as f:
    blob_data = f.read()
  cursor.execute("insert into apex_app.demo_uk_ai_sandbox( FILE_NAME,DATA,MIME_TYPE) values (:filename, :data, 'application/pdf')",
                  filename=a_filename, data=blob_data)

oracledb.init_oracle_client()
connection = oracledb.connect(user=config.ORACLE_USERNAME, password=config.ORACLE_PASSWORD, dsn=config.ORACLE_TNS)
cursor = connection.cursor()
for filename in os.listdir('docs'):
  print( filename )
  insert_blob( filename)
connection.commit()
EOF

sqlplus APEX_APP/$DB_PASSWORD@db <<EOF
begin
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('VM Address', 'https://$APIGW_HOSTNAME/rag/generate');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Embed URL', 'https://$APIGW_HOSTNAME/rag/create_embeddings');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Text2SQL_ENDPOINT', 'https://$APIGW_HOSTNAME/text2sql/v2/handle_data_request');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Application Name', 'Oracle AI Application');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('USER_PW', '$DB_PASSWORD');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Show Available Users (Y/N)', 'Y');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('AI_DEBUG_ENABLED (Y/N)', 'N');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('LLM Model', 'cohere.command-r-plus-08-2024');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('prompt', 'You are an HR representative responsible for addressing inquiries about company Policies and Procedures, trained to give accurate and precise answers based solely on the information provided. Math is an important aspect of your role, especially when calculating leave days, compensation, benefits, and other numerical values. If someone asks about leave entitlements,loan eligibility numbers or any mathematical calculation, ensure you perform the math correctly. For example, if an employee is entitled to 20 days of leave and has already taken 7 days, they have 13 days remaining. So, if they inquire about taking 14 days off, you should respond, ''Sorry, but taking 14 days of leave would exceed your entitlement. With 20 days allotted and 7 days already taken, you have 13 days remaining.'' Always provide transparent calculations in your responses. Avoid robotic language and converse naturally. If you don''t know an answer, say so, and stick to providing information about HR policies. Be mindful of the user''s grade and personalize responses accordingly. Don''t mention that you''re a chatbot and dont add  [Your name] at the end of the answers, and maintain confidentiality. Very important to Check the logged in user info and frame the answer based on the logged in user info like the grade , number of kids , years of service');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Enable User Context (Y/N)', 'Y');

  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Welcome bot message', 'Welcome to our AI assistant chat, please, enter your question. :D');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('More info text', 'For more info check these links:');
  insert into APEX_APP.DEMO_UK_AI_SANDBOX_SETTINGS(setting,value) values('Not an answer bot message', 'I didn''t understand your request. How can I help?');
  commit;
end;
/

begin
  delete from APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS;
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','What are the company policies on remote work?');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','How much personal loan am I elegible for?');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','How much educational assistance will i get for my kids?');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','How many annual leaves am I eligible for ?');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','How much allowance will i get if I travel to Australia');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','Are the costs for school books included?');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('HR','And what is the allowance per child ?');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','Get the list of cities along with their corresponding country names');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','Get the list of countries in the ''Europe'' region along with their cities');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','List the department names and the number of employees in each department');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','Find the names and salaries of all employees who report to the manager with employee_id 100');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','List all job titles along with the number of employees currently holding each job');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','Find the average salary for each job in the company');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_HR','Get the total number of employees working in each region');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','Show all the distinct absence types that have been reported by employee');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','Show distinct absence types and the number of employees who reported them in 2017');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','Show all the employees names that have reported absence type name like ''Sick%''');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','Show all the employee name that have reported absence type like ''Sick%'' and the total number of hours reported. Order by number of hours descending');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','For every department shows the department name, the absence type name and total number of hour reported');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','Show the names of all employees who registered absences started in 2017 and the total hours for each absence type name');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('Text2SQL_EBS','Show all the employee located in US who have reported absences in 2017');
  insert into APEX_APP.DEMO_AI_SANDBOX_SAMPLE_QUESTIONS(demo_mode,question) values('RAG','What is the policy for annual leave ?');
  commit;
end;
/
exit
EOF
