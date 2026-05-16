#!/usr/bin/env bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR/..

. starter.sh env -silent

get_ui_url

echo 
echo "Build done"

# Extract host value
DB_HOST=$(echo "$DB_URL" | sed -n 's/.*(host=\([^)]*\)).*/\1/p')
# Replace host with localhost
DB_URL_LOCALHOST=$(echo "$DB_URL" | sed 's/(host=[^)]*)/(host=localhost)/')

# Do not show the Done URLs if after_build.sh exists 
if [ "$UI_URL" != "" ]; then
    echo "-----------------------------------------------------------------------"  > $FILE_DONE
    append_done "URL:"
    append_done "- User Interface: $UI_URL/"     
    if [ "$UI_HTTP" != "" ]; then
        append_done "- HTTP : $UI_HTTP/"
    fi
    if [ "$TF_VAR_ui_type" == "langgraph" ]; then
        append_done "- REST: $UI_URL/app/threads"
    else
        append_done "- REST: $UI_URL/app/dept"
        append_done "- REST: $UI_URL/app/info"    
    fi
    append_done "-----------------------------------------------------------------------"
    append_done "Vibe Coding:"
    append_done
    if [ "$TF_VAR_your_public_ssh_key" != "" ]; then
        append_done "1. Check that you can login from your laptop to the bastion using the private key associated with your_public_ssh_key in terraform.tfvars"
        append_done "> ssh opc@$BASTION_IP"
    else
        append_done "1. Be sure that you can login from your laptop to the bastion by adding your SSH key to the bastion"
        append_done "   - or add the private key created in target/ssh_key_starter in your laptop"
        append_done "   - or login to the bastion (./starter.sh ssh bastion and add your own public key in $HOME/.ssh/authorized_keys)"
    fi
    append_done "2. Clone the git repo of the starter app in your laptop"
    append_done "> git clone opc@$BASTION_IP:~/app.git app"
    append_done "> cd app"
    append_done "3. Do some changes with your favorite editor."
    append_done "4. Check what git_push.sh does and run it."
    append_done "> ./git_push.sh"
    append_done "The build will start automatically in the bastion and redeploy the app."
    append_done
    append_done "5. If you want to see the log. ssh opc@$BASTION_IP"
    append_done "> cat compute/rebuild.log"
    append_done "> cd app/xxxx" 
    append_done "> cat xxxx.log" 
    append_done
    append_done "-----------------------------------------------------------------------"
    append_done "Database:"
    append_done
    append_done "DB_USER=$DB_USER"
    append_done "DB_PASSWORD=$DB_PASSWORD"
    append_done "DB_URL=$DB_URL"
    append_done 
    append_done "In terminal 1, open the ssh tunnel"
    append_done "  ssh -L1521:$DB_HOST:1521 opc@$BASTION_IP"
    append_done "In terminal 2, save the connection to the database."
    append_done "  \$HOME/oracle/sqlcl/bin/sql /nolog"
    append_done "  conn -savepwd -save adb $DB_USER@$DB_URL_LOCALHOST"
    append_done "  $DB_PASSWORD"
    append_done "  select * from dept;"
    append_done "  exit"

elif [ ! -f $FILE_DONE ]; then
    echo "-" > $FILE_DONE  
fi
cat $FILE_DONE  