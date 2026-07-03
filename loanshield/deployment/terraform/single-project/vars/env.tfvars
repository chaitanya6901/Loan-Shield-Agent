# Project name used for resource naming
project_name = "loanshield"

# Your Google Cloud project id
project_id = "carbon-footprint-5739"

# The Google Cloud region you will use to deploy the infrastructure
region = "us-east1"

# groq_api_key is intentionally NOT set here — do not commit secrets to a
# tfvars file. Pass it at apply-time instead, e.g.:
#   TF_VAR_groq_api_key="gsk_..." terraform apply
# or via a separate untracked *.auto.tfvars / secret-manager-backed value.
