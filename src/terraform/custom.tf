variable genai_api_key {
  default=null
  description= "OpenAI Compatible API Key"   
}

variable genai_model {
    default="OCI GenAI Model ID"
}

resource "null_resource" "custom_dependency" {
    provisioner "local-exec" {
        command = <<-EOT
        cd ${local.project_dir}
        ENV_FILE=target/tf_env.sh
        append() {
            echo "$1" >> $ENV_FILE
        }    
        append_export() {
            if [ "$2" != "" ] && [ "$2" != "-" ]; then
                echo "export $1=\"$2\"" >> $ENV_FILE
            fi 
        }
        append "# Custom"
        append_export "TF_VAR_genai_api_key" "${local.genai_api_key}"
        append_export "TF_VAR_genai_model" "${local.genai_model}"
        EOT
    }
    depends_on = [ null_resource.tf_env ]
}