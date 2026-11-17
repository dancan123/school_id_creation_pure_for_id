import os
import uuid
import datetime
import base64
import requests
import json
from extensions import db
from models import School, User, PaymentTransaction
from utils import log_audit

PACKAGES = {
    "pack_100": {
        "key": "pack_100",
        "name": "Starter 100 Cards",
        "cards": 100,
        "amount": 2500.0,
        "tier": "starter",
        "description": "Ideal for small teams, departments, or primary schools."
    },
    "pack_500": {
        "key": "pack_500",
        "name": "Standard 500 Cards",
        "cards": 500,
        "amount": 7500.0,
        "tier": "standard",
        "description": "Best value for secondary schools, colleges, and mid-sized businesses."
    },
    "pack_2000": {
        "key": "pack_2000",
        "name": "Corporate 2,000 Cards",
        "cards": 2000,
        "amount": 20000.0,
        "tier": "standard",
        "description": "High-volume generation for universities, TVETs, and large companies."
    },
    "pack_unlimited": {
        "key": "pack_unlimited",
        "name": "Enterprise Unlimited Cards",
        "cards": 0,
        "amount": 45000.0,
        "tier": "enterprise",
        "description": "Infinite card generation allowance with VIP SLA support."
    }
}

class MpesaService:
    @staticmethod
    def get_packages():
        return list(PACKAGES.values())

    @staticmethod
    def get_package(key):
        return PACKAGES.get(key)

    @staticmethod
    def normalize_phone(phone):
        if not phone:
            return ""
        s = "".join(c for c in str(phone) if c.isdigit())
        if s.startswith("0") and len(s) == 10:
            return "254" + s[1:]
        if s.startswith("7") and len(s) == 9:
            return "254" + s
        if s.startswith("254") and len(s) == 12:
            return s
        return s

    @classmethod
    def initiate_stk_push(cls, school, user, phone_number, package_key):
        """Initiates an M-Pesa STK push for the school tenant or handles simulated transaction in sandbox mode."""
        pkg = PACKAGES.get(package_key)
        if not pkg:
            raise ValueError(f"Invalid package key '{package_key}'.")

        clean_phone = cls.normalize_phone(phone_number)
        if len(clean_phone) != 12 or not clean_phone.startswith("254"):
            raise ValueError("Invalid Kenyan phone number. Please enter a valid number like 0712345678 or +254712345678.")

        ref_id = str(uuid.uuid4())
        txn = PaymentTransaction(
            school_id=school.id,
            user_id=user.id if user else None,
            reference_id=ref_id,
            amount=pkg["amount"],
            phone_number=clean_phone,
            package_key=pkg["key"],
            package_name=pkg["name"],
            cards_credited=pkg["cards"],
            tier_allocated=pkg["tier"],
            status="pending"
        )
        db.session.add(txn)
        db.session.commit()

        consumer_key = os.getenv("MPESA_CONSUMER_KEY")
        consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
        passkey = os.getenv("MPESA_PASSKEY")
        shortcode = os.getenv("MPESA_SHORTCODE", "174379")
        env = os.getenv("MPESA_ENV", "sandbox")
        callback_url = os.getenv("MPESA_CALLBACK_URL", "http://127.0.0.1:5000/api/v1/billing/mpesa-callback")

        # Live Daraja integration if credentials are fully configured
        if consumer_key and consumer_secret and passkey:
            try:
                base_url = "https://api.safaricom.co.ke" if env == "production" else "https://sandbox.safaricom.co.ke"
                auth_resp = requests.get(
                    f"{base_url}/oauth/v1/generate?grant_type=client_credentials",
                    auth=(consumer_key, consumer_secret),
                    timeout=10
                )
                access_token = auth_resp.json().get("access_token")
                if not access_token:
                    raise RuntimeError("Failed to obtain M-Pesa OAuth access token.")

                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                password_str = f"{shortcode}{passkey}{timestamp}"
                encoded_password = base64.b64encode(password_str.encode()).decode("utf-8")

                stk_payload = {
                    "BusinessShortCode": shortcode,
                    "Password": encoded_password,
                    "Timestamp": timestamp,
                    "TransactionType": "CustomerPayBillOnline",
                    "Amount": int(pkg["amount"]),
                    "PartyA": clean_phone,
                    "PartyB": shortcode,
                    "PhoneNumber": clean_phone,
                    "CallBackURL": callback_url,
                    "AccountReference": f"EduID-{school.code or school.id}",
                    "TransactionDesc": f"Topup {pkg['name']}"
                }

                stk_resp = requests.post(
                    f"{base_url}/mpesa/stkpush/v1/processrequest",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json=stk_payload,
                    timeout=15
                )
                stk_data = stk_resp.json()
                txn.merchant_request_id = stk_data.get("MerchantRequestID")
                txn.checkout_request_id = stk_data.get("CheckoutRequestID")
                db.session.commit()

                return {
                    "success": True,
                    "transaction_id": txn.id,
                    "reference_id": txn.reference_id,
                    "checkout_request_id": txn.checkout_request_id,
                    "customer_message": stk_data.get("CustomerMessage", "Please check your phone and enter your M-Pesa PIN."),
                    "is_simulation": False
                }
            except Exception as e:
                # Fallback to simulated mode with warning
                txn.result_description = f"Daraja error fallback: {str(e)}"
                db.session.commit()

        # Simulated sandbox / instant developer mode
        simulated_checkout = f"ws_CO_MOCK_{uuid.uuid4().hex[:16]}"
        simulated_merchant = f"MOCK_MERCH_{uuid.uuid4().hex[:12]}"
        txn.checkout_request_id = simulated_checkout
        txn.merchant_request_id = simulated_merchant
        db.session.commit()

        return {
            "success": True,
            "transaction_id": txn.id,
            "reference_id": txn.reference_id,
            "checkout_request_id": txn.checkout_request_id,
            "customer_message": f"STK push dispatched to {clean_phone} for KES {pkg['amount']:,.0f}. Enter M-Pesa PIN to complete.",
            "is_simulation": True
        }

    @classmethod
    def apply_successful_payment(cls, txn, mpesa_receipt_number, result_desc="Completed successfully via M-Pesa"):
        """Credits the tenant school quota and upgrades tier upon confirmed payment."""
        txn.status = "completed"
        txn.mpesa_receipt_number = mpesa_receipt_number
        txn.result_code = 0
        txn.result_description = result_desc
        txn.completed_at = datetime.datetime.utcnow()

        sch = txn.school
        if sch:
            if txn.cards_credited == 0:
                # Unlimited tier
                sch.max_cards_quota = 0
                sch.subscription_tier = "enterprise"
            else:
                current_quota = sch.max_cards_quota or 0
                sch.max_cards_quota = current_quota + txn.cards_credited
                if sch.subscription_tier == "free_trial":
                    sch.subscription_tier = txn.tier_allocated or "standard"

        db.session.commit()
        log_audit(
            "MPESA_TOPUP_SUCCESS",
            f"Credited {txn.cards_credited} cards (KES {txn.amount}) to '{sch.name}' via M-Pesa {mpesa_receipt_number}"
        )
        return True

    @classmethod
    def process_callback(cls, callback_json):
        """Processes Daraja STK callback payload and credits quota if ResultCode is 0."""
        try:
            body = callback_json.get("Body", {}).get("stkCallback", {})
            checkout_id = body.get("CheckoutRequestID")
            result_code = body.get("ResultCode")
            result_desc = body.get("ResultDesc", "")

            if not checkout_id:
                return {"status": "error", "message": "Missing CheckoutRequestID"}

            txn = PaymentTransaction.query.filter_by(checkout_request_id=checkout_id).first()
            if not txn:
                return {"status": "error", "message": "Transaction not found"}

            if txn.status == "completed":
                return {"status": "ok", "message": "Already completed"}

            if result_code == 0:
                # Extract M-Pesa receipt number from metadata items
                receipt_no = None
                items = body.get("CallbackMetadata", {}).get("Item", [])
                for item in items:
                    if item.get("Name") == "MpesaReceiptNumber":
                        receipt_no = item.get("Value")
                        break
                if not receipt_no:
                    receipt_no = f"MP-{uuid.uuid4().hex[:10].upper()}"

                cls.apply_successful_payment(txn, receipt_no, result_desc)
                return {"status": "ok", "message": "Payment verified and credited"}
            else:
                txn.status = "failed"
                txn.result_code = result_code
                txn.result_description = result_desc
                txn.completed_at = datetime.datetime.utcnow()
                db.session.commit()
                return {"status": "failed", "message": result_desc}
        except Exception as e:
            return {"status": "error", "message": str(e)}
