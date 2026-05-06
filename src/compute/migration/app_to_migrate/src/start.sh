#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR

export TNS_ADMIN=$SCRIPT_DIR
export TF_VAR_compartment_ocid=`curl -s -H "Authorization: Bearer Oracle" -L http://169.254.169.254/opc/v2/instance/ | jq -r .compartmentId`
export TF_VAR_region=`curl -s -H "Authorization: Bearer Oracle" -L http://169.254.169.254/opc/v2/instance/ | jq -r .region`

source myenv/bin/activate
python3 OciTest.py 2>&1 | tee OciTest.log & python3 createEmbeddingsFromDB.py 2>&1 | tee createEmbeddingsFromDB.log
