import os
import time
import requests
import csv
import json
from sp_api.api import Reports, ProductFees
from sp_api.base import Marketplaces, ReportType, ProcessingStatus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Credentials = dict(
    refresh_token=os.getenv("REFRESH_TOKEN"),
    lwa_app_id=os.getenv("LWA_APP_ID"),  # ✅ Fixed variable names
    lwa_client_secret=os.getenv("LWA_CLIENT_SECRET"),  # ✅ Fixed variable names
)

# Ensure credentials are set
if not Credentials["lwa_app_id"] or not Credentials["lwa_client_secret"]:
    raise Exception("Amazon SP-API credentials are missing. Check your .env file.")

marketPlace = Marketplaces.MX

def getOrders():
    print('🛒 Fetching Orders...')
    report_type = ReportType.GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
    res = Reports(credentials=Credentials, marketplace=marketPlace)
    data = res.create_report(reportType=report_type, dataStartTime="2025-01-04")
    reportId = data.payload['reportId']
    report_status = res.get_report(reportId)

    while report_status.payload.get('processingStatus') not in [ProcessingStatus.DONE, ProcessingStatus.FATAL, ProcessingStatus.CANCELLED]:
        time.sleep(2)
        report_status = res.get_report(reportId)
        print(f"⏳ Report Status: {report_status.payload.get('processingStatus')}")

    if report_status.payload.get('processingStatus') in [ProcessingStatus.FATAL, ProcessingStatus.CANCELLED]:
        raise Exception('❌ Report Failed')

    # ✅ Fetch the report document from URL
    reportData = res.get_report_document(report_status.payload['reportDocumentId'], decrypt=True)
    report_url = reportData.payload.get("url")

    res = requests.get(report_url)
    decoded_content = res.content.decode('utf-8')

    reader = csv.DictReader(decoded_content.splitlines(), delimiter='\t')
    data_list = []

    for row in reader:
        data = {
            "sku": row['sku'],
            "price": row['item-price'],
            "currency": row['currency'],
            "orderStatus": row['order-status'],
            "title": row['product-name']
        }
        data_list.append(data)

    return data_list

def getFees(asin, price):
    fees = ProductFees(credentials=Credentials, marketplace=marketPlace)
    try:
        r = fees.get_product_fees_estimate_for_asin(asin, float(price), currency="USD", is_fba=True)
        return r.payload['FeesEstimatedResult']['FeesEstimate']['TotalFeesEstimate']['Amount']
    except Exception as e:
        print(f"⚠️ Error fetching fees for ASIN {asin}: {e}")
        return None  # ✅ Return None instead of 0
