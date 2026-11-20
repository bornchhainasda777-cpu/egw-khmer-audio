#!/bin/bash
# Links the open billing account to egw-khmer (Blaze plan) and adds a $1 budget alert email.
P=egw-khmer
BA=$(gcloud billing accounts list --filter='open=true' --format='value(name)' --limit=1 | sed 's|billingAccounts/||')
echo "Billing account: ${BA:0:6}…"
gcloud billing projects link $P --billing-account=$BA --format='value(billingEnabled)'
gcloud services enable billingbudgets.googleapis.com --project $P
gcloud billing budgets list --billing-account=$BA --format='value(displayName)' | grep -q 'EGW Khmer 1 dollar alert' || \
  gcloud billing budgets create --billing-account=$BA --display-name='EGW Khmer 1 dollar alert' --budget-amount=1USD \
    --threshold-rule=percent=0.5 --threshold-rule=percent=1.0 --format='value(displayName)'
echo BILLING-DONE
