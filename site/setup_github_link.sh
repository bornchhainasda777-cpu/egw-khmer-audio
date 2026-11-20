#!/bin/bash
# Keyless link: lets the GitHub audio job (only this repository) upload to Google Cloud Storage.
P=egw-khmer
REPO=bornchhainasda777-cpu/egw-khmer-audio
SA=egw-audio-uploader@$P.iam.gserviceaccount.com
N=$(gcloud projects describe $P --format='value(projectNumber)')
echo "Project number: $N"
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com iam.googleapis.com --project $P
gcloud iam workload-identity-pools describe github --location=global --project $P >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create github --location=global --project $P --display-name="GitHub audio"
gcloud iam workload-identity-pools providers describe github --location=global --workload-identity-pool=github --project $P >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc github --location=global --workload-identity-pool=github --project $P \
    --issuer-uri=https://token.actions.githubusercontent.com \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='$REPO'"
gcloud iam service-accounts describe $SA --project $P >/dev/null 2>&1 || \
  gcloud iam service-accounts create egw-audio-uploader --project $P --display-name="EGW audio uploader"
gcloud iam service-accounts add-iam-policy-binding $SA --project $P --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$N/locations/global/workloadIdentityPools/github/attribute.repository/$REPO" >/dev/null
echo "PROVIDER=projects/$N/locations/global/workloadIdentityPools/github/providers/github"
echo "SERVICE_ACCOUNT=$SA"
echo LINK-DONE
