"""
M-Pesa (Safaricom Daraja) STK Push adapter.

Status
------
* `MpesaDarajaAdapter` follows Safaricom's documented STK Push (Lipa Na M-Pesa Online) request and
  callback formats. It has NOT been exercised against Safaricom from this repo's CI: that requires your
  Daraja credentials, a registered shortcode/passkey and a public HTTPS callback URL. Run the Daraja
  sandbox end-to-end before taking real money (see docs/DEPLOYMENT.md, "Go-live checklist").
* `MockMpesaAdapter` fakes a successful payment. It is only reachable when settings.DEBUG is true or
  ALLOW_MOCK_PAYMENTS is explicitly enabled (see payments/views.py) so production cannot use it by accident.
"""
from __future__ import annotations

import base64
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE_URL = "https://api.safaricom.co.ke"
HTTP_TIMEOUT_SECONDS = 20


class PaymentError(Exception):
    """A payment could not be initiated. `user_message` is safe to show to the buyer."""

    def __init__(self, user_message: str, *, detail: str = ""):
        super().__init__(detail or user_message)
        self.user_message = user_message


@dataclass
class STKPushResult:
    checkout_request_id: str
    merchant_request_id: str
    message: str


@dataclass
class CallbackResult:
    checkout_request_id: str
    success: bool
    result_description: str
    receipt_number: str = ""
    amount: Optional[Decimal] = None


def normalize_msisdn(raw: str) -> str:
    """Accepts 07XXXXXXXX, 01XXXXXXXX, +2547XXXXXXXX, 2547XXXXXXXX -> 2547XXXXXXXX / 2541XXXXXXXX."""
    digits = re.sub(r"[^\d]", "", raw or "")
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    elif len(digits) == 9 and digits[0] in "71":
        digits = "254" + digits
    if not re.fullmatch(r"254[17]\d{8}", digits):
        raise PaymentError("Enter a valid Safaricom number, e.g. 0712 345 678.")
    return digits


class PaymentAdapter(ABC):
    @abstractmethod
    def initiate(self, *, phone: str, amount: int, account_reference: str, callback_url: str) -> STKPushResult: ...

    @abstractmethod
    def parse_callback(self, payload: dict) -> CallbackResult: ...


class MockMpesaAdapter(PaymentAdapter):
    """Pretends to charge. NEVER reachable in production unless explicitly overridden (see settings)."""

    def initiate(self, *, phone, amount, account_reference, callback_url) -> STKPushResult:
        return STKPushResult(
            checkout_request_id=f"MOCK-{uuid.uuid4().hex[:12]}",
            merchant_request_id=f"MOCK-{uuid.uuid4().hex[:12]}",
            message="[MOCK] No money was charged.",
        )

    def parse_callback(self, payload: dict) -> CallbackResult:
        raise NotImplementedError("The mock adapter completes payments inline; it has no callback.")


class MpesaDarajaAdapter(PaymentAdapter):
    def __init__(self, config: dict):
        required = ["CONSUMER_KEY", "CONSUMER_SECRET", "SHORTCODE", "PASSKEY"]
        missing = [k for k in required if not config.get(k)]
        if missing:
            raise PaymentError(
                "Payments are temporarily unavailable.",
                detail=f"M-Pesa config incomplete, missing: {', '.join(missing)}",
            )
        self.config = config
        self.base_url = PRODUCTION_BASE_URL if config.get("ENV") == "production" else SANDBOX_BASE_URL

    def _token(self) -> str:
        try:
            resp = requests.get(
                f"{self.base_url}/oauth/v1/generate",
                params={"grant_type": "client_credentials"},
                auth=(self.config["CONSUMER_KEY"], self.config["CONSUMER_SECRET"]),
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.error("Daraja OAuth failed: %s", exc)
            raise PaymentError("Could not reach M-Pesa. Please try again shortly.", detail=str(exc))

    def initiate(self, *, phone, amount, account_reference, callback_url) -> STKPushResult:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.config['SHORTCODE']}{self.config['PASSKEY']}{timestamp}".encode()
        ).decode()
        body = {
            "BusinessShortCode": self.config["SHORTCODE"],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": self.config.get("TRANSACTION_TYPE") or "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": self.config.get("TILL_OR_SHORTCODE") or self.config["SHORTCODE"],
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": "GetbyFarm",
        }
        try:
            resp = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=body,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.error("Daraja STK push request failed: %s", exc)
            raise PaymentError("Could not reach M-Pesa. Please try again shortly.", detail=str(exc))

        if resp.status_code != 200 or str(data.get("ResponseCode")) != "0":
            logger.error("Daraja rejected STK push: status=%s body=%s", resp.status_code, data)
            raise PaymentError("M-Pesa could not start the payment. Check the phone number and try again.",
                               detail=str(data))
        return STKPushResult(
            checkout_request_id=data["CheckoutRequestID"],
            merchant_request_id=data["MerchantRequestID"],
            message=data.get("CustomerMessage", "Check your phone to enter your M-Pesa PIN."),
        )

    def parse_callback(self, payload: dict) -> CallbackResult:
        """Daraja posts {"Body": {"stkCallback": {..., "ResultCode": 0, "CallbackMetadata": {"Item": [...]}}}}."""
        try:
            cb = payload["Body"]["stkCallback"]
            items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
            return CallbackResult(
                checkout_request_id=cb["CheckoutRequestID"],
                success=int(cb["ResultCode"]) == 0,
                result_description=str(cb.get("ResultDesc", ""))[:255],
                receipt_number=str(items.get("MpesaReceiptNumber", "")),
                amount=Decimal(str(items["Amount"])) if "Amount" in items else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PaymentError("Malformed callback", detail=str(exc))


def get_payment_adapter(settings_module) -> PaymentAdapter:
    """Real Daraja when enabled; the mock only if DEBUG or ALLOW_MOCK_PAYMENTS permits it; else refuse."""
    cfg = settings_module.MPESA_CONFIG
    if cfg.get("ENABLED"):
        return MpesaDarajaAdapter(cfg)
    if settings_module.DEBUG or settings_module.ALLOW_MOCK_PAYMENTS:
        return MockMpesaAdapter()
    raise PaymentError("Payments are not enabled on this site yet.", detail="MPESA_ENABLED is false")
