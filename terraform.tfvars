# -- Variables ---------------------------------------------

# Prefix to all resources created by terraform
prefix="vibe"

# Min length 12 characters, 2 lowercase, 2 uppercase, 2 numbers, 2 special characters. Ex: LiveLab__12345
db_password="__TO_FILL__"

# BRING_YOUR_OWN_LICENSE or LICENSE_INCLUDED
license_model="LICENSE_INCLUDED"

# Your ssh public key (associated with your private key stored in your laptop) that will be added in .ssh/authorized host in the bastion. Goal: clone the git repository on your laptop for Vibe Coding
your_public_ssh_key="__TO_FILL__"

# Compartment
compartment_ocid="__TO_FILL__"

# Generative AI - OpenAI Compatible key
# genai_apikey = "sk-xxxxxx"

# Generative AI - Model (ex: xai.grok-code-fast-1 / xai.grok-4.20-0309-reasoning / meta.llama-4-maverick-17b-128e-instruct-fp8 / openai.gpt-oss-120b / google.gemini-2.5-flash)
# genai_model = xai.grok-code-fast-1